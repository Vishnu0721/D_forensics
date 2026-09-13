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

class ClassificationEngine:
    def __init__(self):
        self._cache = {}

    def clear_cache(self):
        self._cache.clear()

    def classify_event(self, event: ForensicEvent, graph: nx.MultiDiGraph = None, all_suspicious: List[Dict[str, Any]] = None, graph_version: int = 0) -> Dict[str, str]:
        """
        Classifies a forensic event.
        Returns a dict: {"classification": "...", "reason": "...", "attribution": "..."}
        """
        cache_key = f"{event.evidence_id}_{graph_version}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        if graph is None:
            graph = nx.MultiDiGraph()
        if all_suspicious is None:
            all_suspicious = []

        # 1. Check Suspicious Activity (Highest Priority)
        for act in all_suspicious:
            if event.evidence_id in act.get("evidence_ids", []):
                result = {
                    "classification": CLASSIFICATION_SUSPICIOUS,
                    "reason": f"Event satisfies detection rule: {act.get('rule_name', 'Unknown')}",
                    "attribution": "Detection Engine"
                }
                self._cache[cache_key] = result
                return result

        # 2. Check Correlated Activity
        # Iterate over edges in graph to see if this evidence_id is a supporting evidence
        is_correlated = False
        rel_types = set()
        for u, v, data in graph.edges(data=True):
            if event.evidence_id in data.get("evidence_ids", []):
                is_correlated = True
                rel_types.add(data.get("type", data.get("relationship_type", "Unknown")))

        if is_correlated:
            rels_str = ", ".join(rel_types)
            result = {
                "classification": CLASSIFICATION_CORRELATED,
                "reason": f"Event participates in a correlation relationship generated from observed telemetry ({rels_str}).",
                "attribution": "Correlation Engine"
            }
            self._cache[cache_key] = result
            return result

        # 3. Check User Activity vs Background Activity
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

        # Determine if it's a background activity
        if is_system_user or is_background_process or (is_storage_ext and is_appdata) or (is_storage_ext and is_system_dir):
            result = {
                "classification": CLASSIFICATION_BACKGROUND,
                "reason": "Event originated from an application storage directory or background service and could not be attributed to a direct user action.",
                "attribution": "System/Background"
            }
            self._cache[cache_key] = result
            return result

        # Determine if it's user activity
        is_user_dir = "downloads" in path_lower or "desktop" in path_lower or "documents" in path_lower
        is_user_app = process_lower in ["explorer.exe", "chrome.exe", "msedge.exe", "firefox.exe", "notepad.exe", "cmd.exe", "powershell.exe", "word.exe", "excel.exe"]

        if has_real_user:
            # We have a real user, let's ensure it's an interactive action
            if event.event_type in ["login", "usb_connected", "download", "file_moved"]:
                result = {
                    "classification": CLASSIFICATION_USER,
                    "reason": f"Event ({event.event_type}) is an explicitly interactive user action.",
                    "attribution": event.user
                }
                self._cache[cache_key] = result
                return result
                
            # If a user explicitly modifies or creates a document in a user dir, that's likely them
            if is_user_dir and event.event_type in ["file_created", "file_modified"]:
                # Limit to documents to be conservative, avoiding background app files
                if file_lower.endswith((".txt", ".pdf", ".docx", ".xlsx", ".png", ".jpg")):
                    result = {
                        "classification": CLASSIFICATION_USER,
                        "reason": f"Interactive file event ({event.event_type}) in a user directory on a user-facing file type.",
                        "attribution": event.user
                    }
                    self._cache[cache_key] = result
                    return result
                
            if is_user_app and event.event_type == "process_started":
                result = {
                    "classification": CLASSIFICATION_USER,
                    "reason": "Interactive application process spawned under user context.",
                    "attribution": event.user
                }
                self._cache[cache_key] = result
                return result
                
            # If the user is present but it doesn't clearly match an interactive pattern, it's safer to mark as unknown
            # to avoid false claims.

        # 4. Fallback to UNKNOWN
        result = {
            "classification": CLASSIFICATION_UNKNOWN,
            "reason": "Available telemetry is insufficient for reliable attribution.",
            "attribution": "Unavailable"
        }
        self._cache[cache_key] = result
        return result
