import re
from typing import Dict, Any, List
import networkx as nx
from core.database.models import ForensicEvent
from functools import lru_cache

# Constants for classifications
CLASSIFICATION_USER = "USER_ACTIVITY"
CLASSIFICATION_BACKGROUND = "BACKGROUND_ACTIVITY"
CLASSIFICATION_SUSPICIOUS = "SUSPICIOUS_ACTIVITY"
CLASSIFICATION_CORRELATED = "CORRELATED_ACTIVITY"
CLASSIFICATION_UNKNOWN = "UNKNOWN"

MAX_CACHED_EVENTS = 20000


class ClassificationEngine:
    def __init__(self):
        # event_key -> (graph_version, result); one entry per event, bounded.
        self._cache = {}
        self._index_graph = None
        self._index_suspicious = None
        self._index_version = None
        self._suspicious_rule_by_evidence = {}
        self._rel_types_by_evidence = {}

    def clear_cache(self):
        self._cache.clear()

    def classification_counts(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for _version, result in self._cache.values():
            cls = result["classification"]
            counts[cls] = counts.get(cls, 0) + 1
        return counts

    def _store(self, event_key: str, graph_version: int, result: Dict[str, str]) -> Dict[str, str]:
        if event_key not in self._cache and len(self._cache) >= MAX_CACHED_EVENTS:
            self._cache.pop(next(iter(self._cache)))
        self._cache[event_key] = (graph_version, result)
        return result

    def _ensure_index(self, graph: nx.MultiDiGraph, all_suspicious: List[Dict[str, Any]], graph_version: int):
        """Build evidence_id lookups once per graph/suspicious snapshot instead of scanning per event."""
        if (
            graph is self._index_graph
            and all_suspicious is self._index_suspicious
            and graph_version == self._index_version
        ):
            return
        rules: Dict[str, str] = {}
        for act in all_suspicious:
            rule = act.get("rule_name", "Unknown")
            for eid in act.get("evidence_ids", []):
                rules.setdefault(eid, rule)
        rel_types: Dict[str, set] = {}
        for _u, _v, data in graph.edges(data=True):
            rel = data.get("type", data.get("relationship_type", "Unknown"))
            for eid in data.get("evidence_ids", []):
                rel_types.setdefault(eid, set()).add(rel)
        self._suspicious_rule_by_evidence = rules
        self._rel_types_by_evidence = rel_types
        self._index_graph = graph
        self._index_suspicious = all_suspicious
        self._index_version = graph_version

    def classify_event(self, event: ForensicEvent, graph: nx.MultiDiGraph = None, all_suspicious: List[Dict[str, Any]] = None, graph_version: int = 0) -> Dict[str, str]:
        """
        Classifies a forensic event.
        Returns a dict: {"classification": "...", "reason": "...", "attribution": "..."}
        """
        # Per-event key (not evidence_id): one file can hold many events with different classes.
        event_key = event.id or f"{event.evidence_id}:{event.timestamp}:{event.event_type}:{event.process}:{event.path}"
        cached = self._cache.get(event_key)
        if cached is not None and cached[0] == graph_version:
            return cached[1]

        if graph is None:
            graph = nx.MultiDiGraph()
        if all_suspicious is None:
            all_suspicious = []
        self._ensure_index(graph, all_suspicious, graph_version)

        # 1. Check Suspicious Activity (Highest Priority)
        rule_name = self._suspicious_rule_by_evidence.get(event.evidence_id)
        if rule_name is not None:
            result = {
                "classification": CLASSIFICATION_SUSPICIOUS,
                "reason": f"Event satisfies detection rule: {rule_name}",
                "attribution": "Detection Engine"
            }
            return self._store(event_key, graph_version, result)

        # 2. Check Correlated Activity
        rel_types = self._rel_types_by_evidence.get(event.evidence_id)
        is_correlated = bool(rel_types)

        if is_correlated:
            rels_str = ", ".join(rel_types)
            result = {
                "classification": CLASSIFICATION_CORRELATED,
                "reason": f"Event participates in a correlation relationship generated from observed telemetry ({rels_str}).",
                "attribution": "Correlation Engine"
            }
            return self._store(event_key, graph_version, result)

        # 3./4. User vs Background vs Unknown
        return self._store(event_key, graph_version, classify_origin(event))


def classify_origin(event: ForensicEvent, include_connections: bool = False) -> Dict[str, str]:
    """Who caused the event (user, background or unknown), ignoring correlation and detection results.

    include_connections attributes connections made by interactive apps to the user; it is only
    used for graph links so the Activity tab labels and counters keep their existing meaning.
    """
    sys_users = ["system", "local service", "network service", "window manager"]
    user_lower = (event.user or "").lower()

    is_system_user = any(u in user_lower for u in sys_users)
    has_real_user = bool(user_lower) and not is_system_user

    path_lower = (event.path or "").lower()
    file_lower = (event.file or "").lower()
    process_lower = (event.process or "").lower()

    # Heuristics for background
    is_appdata = "appdata" in path_lower or "programdata" in path_lower or "local settings" in path_lower
    is_system_dir = "system32" in path_lower or "syswow64" in path_lower
    is_background_process = process_lower in ["svchost.exe", "dllhost.exe", "lsass.exe", "csrss.exe", "services.exe", "wininit.exe", "smss.exe", "taskhostw.exe", "searchindexer.exe"]
    is_storage_ext = any(file_lower.endswith(ext) for ext in [".ldb", ".log", ".tmp", ".wal", ".shm", ".db", ".sqlite", ".cache"])

    if is_system_user or is_background_process or (is_storage_ext and is_appdata) or (is_storage_ext and is_system_dir):
        return {
            "classification": CLASSIFICATION_BACKGROUND,
            "reason": "Event originated from an application storage directory or background service and could not be attributed to a direct user action.",
            "attribution": "System/Background"
        }

    is_user_dir = "downloads" in path_lower or "desktop" in path_lower or "documents" in path_lower
    is_user_app = process_lower in ["explorer.exe", "chrome.exe", "msedge.exe", "firefox.exe", "notepad.exe", "cmd.exe", "powershell.exe", "word.exe", "winword.exe", "excel.exe"]

    if has_real_user:
        if event.event_type in ["login", "usb_connected", "download", "file_moved"]:
            return {
                "classification": CLASSIFICATION_USER,
                "reason": f"Event ({event.event_type}) is an explicitly interactive user action.",
                "attribution": event.user
            }

        # Limit to documents to be conservative, avoiding background app files
        if is_user_dir and event.event_type in ["file_created", "file_modified"]:
            if file_lower.endswith((".txt", ".pdf", ".docx", ".xlsx", ".png", ".jpg")):
                return {
                    "classification": CLASSIFICATION_USER,
                    "reason": f"Interactive file event ({event.event_type}) in a user directory on a user-facing file type.",
                    "attribution": event.user
                }

        if is_user_app and event.event_type == "process_started":
            return {
                "classification": CLASSIFICATION_USER,
                "reason": "Interactive application process spawned under user context.",
                "attribution": event.user
            }

        if include_connections and is_user_app and event.event_type == "connection":
            return {
                "classification": CLASSIFICATION_USER,
                "reason": "Network connection made by an interactive application running as the user.",
                "attribution": event.user
            }

        # A user is present but no interactive pattern matched: unknown avoids false claims.

    return {
        "classification": CLASSIFICATION_UNKNOWN,
        "reason": "Available telemetry is insufficient for reliable attribution.",
        "attribution": "Unavailable"
    }


def annotate_origins(relationships: List[Dict[str, Any]], events) -> None:
    """Record on each relationship who caused its underlying events (used by the graph filters)."""
    origin_by_evidence: Dict[str, str] = {}
    for event in events:
        if event.evidence_id and event.evidence_id not in origin_by_evidence:
            origin_by_evidence[event.evidence_id] = classify_origin(event, include_connections=True)["classification"]
    for rel in relationships:
        origins = {origin_by_evidence[e] for e in rel.get("evidence_ids", []) if e in origin_by_evidence}
        if origins:
            rel["origins"] = sorted(origins)
