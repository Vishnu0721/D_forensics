import networkx as nx
from typing import List, Dict, Any, Optional
import json
import os
import threading
import time

from core.paths import DATA_DIR


def make_process_entity(host: Optional[str], pid: Any, process: Optional[str]) -> Dict[str, Any]:
    host = host or "localhost"
    process_name = str(process) if process else "unknown"
    pid_str = str(pid) if pid not in (None, "", "Unavailable") else "?"
    return {
        "type": "Process",
        "id": f"{host}_{pid_str}_{process_name}",
        "label": process_name,
        "subtitle": f"PID {pid_str}",
        "host": host,
        "pid": pid_str,
        "process": process_name,
    }


def make_ip_entity(ip: Optional[str]) -> Dict[str, Any]:
    address = str(ip) if ip else "unknown"
    return {
        "type": "IP",
        "id": address,
        "label": address,
        "subtitle": "Remote IP",
        "ip": address,
    }


def make_file_entity(host: Optional[str], filename: Optional[str]) -> Dict[str, Any]:
    host = host or "localhost"
    name = str(filename) if filename else "unknown"
    return {
        "type": "File",
        "id": f"{host}_{name}",
        "label": name,
        "subtitle": "File",
        "host": host,
        "file": name,
    }


def make_user_entity(user: Optional[str]) -> Dict[str, Any]:
    name = str(user) if user else "unknown"
    return {
        "type": "User",
        "id": name,
        "label": name,
        "subtitle": "User",
        "user": name,
    }


def make_device_entity(host: Optional[str], user: Optional[str] = None) -> Dict[str, Any]:
    host = host or "localhost"
    who = user or "unknown"
    return {
        "type": "Device",
        "id": f"{host}_USB_{who}",
        "label": "USB device",
        "subtitle": who,
        "host": host,
        "user": who,
    }


class EvidenceGraph:
    """In-memory evidence graph shared by the GUI, correlation and offline threads.

    NetworkX is not thread-safe: mutate only via populate_from_correlations /
    add_relationship, and read from other threads via snapshot().
    """

    def __init__(self, case_id: str, storage_dir: str = None):
        self.case_id = case_id
        self.graph = nx.MultiDiGraph()
        self.lock = threading.RLock()
        self._save_lock = threading.Lock()
        self._revision = 0
        self._saved_revision = 0
        self.storage_dir = storage_dir or DATA_DIR
        os.makedirs(self.storage_dir, exist_ok=True)
        self.file_path = os.path.join(self.storage_dir, f"{case_id}_graph.json")
        self.load()

    def snapshot(self) -> nx.MultiDiGraph:
        """Independent copy safe to read while other threads keep correlating."""
        with self.lock:
            snap = nx.MultiDiGraph()
            snap.graph.update(self.graph.graph)
            snap.add_nodes_from((n, dict(d)) for n, d in self.graph.nodes(data=True))
            for u, v, k, d in self.graph.edges(keys=True, data=True):
                attrs = dict(d)
                for list_key in ("evidence_ids", "reasons", "file_paths"):
                    if list_key in attrs:
                        attrs[list_key] = list(attrs[list_key])
                snap.add_edge(u, v, key=k, **attrs)
            return snap

    def _upsert_node(self, entity: Dict[str, Any]):
        node_id = entity["id"]
        attrs = {k: v for k, v in entity.items() if k != "id" and v not in (None, "")}
        if "label" not in attrs:
            attrs["label"] = node_id
        if self.graph.has_node(node_id):
            existing = self.graph.nodes[node_id]
            for key, value in attrs.items():
                if key in ("label", "subtitle", "hostname", "type") or not existing.get(key):
                    existing[key] = value
        else:
            self.graph.add_node(node_id, **attrs)

    def add_relationship(self, rel: Dict[str, Any]):
        """Adds a relationship and its backing evidence to the graph."""
        with self.lock:
            self._revision += 1
            self._add_relationship_locked(rel)

    def _add_relationship_locked(self, rel: Dict[str, Any]):
        source = rel["source"]
        target = rel["target"]
        self._upsert_node(source)
        self._upsert_node(target)
        
        # Deduplicate edges using relationship_type as the MultiDiGraph edge key
        edge_key = rel["type"]
        if self.graph.has_edge(source["id"], target["id"], key=edge_key):
            edge_data = self.graph[source["id"]][target["id"]][edge_key]
            
            # Preserve provenance by extending evidence_ids without duplicating within the list
            existing_evidence = set(edge_data.get("evidence_ids", []))
            new_evidence = set(rel.get("evidence_ids", []))
            
            existing_reasons = set(edge_data.get("reasons", []))
            new_reasons = set(rel.get("reasons", []))
            
            # Safety-net deduplication: skip if no new info
            if new_evidence.issubset(existing_evidence) and new_reasons.issubset(existing_reasons) and rel.get("confidence", 0.0) <= edge_data.get("confidence", 0.0):
                return
                
            for eid in new_evidence:
                if eid not in existing_evidence:
                    edge_data.setdefault("evidence_ids", []).append(eid)
                    
            # Extend reasons
            for reason in new_reasons:
                if reason not in existing_reasons:
                    edge_data.setdefault("reasons", []).append(reason)
                    
            # Update confidence to the maximum seen
            edge_data["confidence"] = max(edge_data.get("confidence", 0.0), rel.get("confidence", 0.0))
            self._merge_edge_details(edge_data, rel)
        else:
            self.graph.add_edge(
                source["id"],
                target["id"],
                key=edge_key,
                relationship_type=rel["type"],
                confidence=rel["confidence"],
                evidence_ids=list(rel.get("evidence_ids", [])),
                reasons=list(rel.get("reasons", []))
            )
            self._merge_edge_details(self.graph[source["id"]][target["id"]][edge_key], rel)

    @staticmethod
    def _merge_edge_details(edge_data: Dict[str, Any], rel: Dict[str, Any]):
        """Structured details used by detection rules (instead of parsing reason text)."""
        path = rel.get("file_path")
        if path:
            paths = edge_data.setdefault("file_paths", [])
            if path not in paths:
                paths.append(path)
        diff = rel.get("time_diff_seconds")
        if diff is not None:
            current = edge_data.get("min_time_diff_seconds")
            edge_data["min_time_diff_seconds"] = diff if current is None else min(current, diff)

    def populate_from_correlations(self, relationships: List[Dict[str, Any]]):
        with self.lock:
            self._revision += 1
            for rel in relationships:
                self._add_relationship_locked(rel)
        # self.save() is debounced to main_window.py to avoid I/O bottlenecks

    def get_all_nodes(self) -> List[Dict[str, Any]]:
        with self.lock:
            return [{"id": n, **d} for n, d in self.graph.nodes(data=True)]

    def get_all_edges(self) -> List[Dict[str, Any]]:
        with self.lock:
            return [{"source": u, "target": v, **d} for u, v, d in self.graph.edges(data=True)]

    def save(self, force: bool = False) -> bool:
        """Persists the in-memory graph to disk (zero-cost DB alternative)."""
        with self._save_lock:
            with self.lock:
                if not force and self._revision == self._saved_revision:
                    return True
                revision = self._revision
                try:
                    data = nx.node_link_data(self.graph, edges="links")
                except TypeError:
                    data = nx.node_link_data(self.graph)
                payload = json.dumps(data)
            # Write to a temp file then swap, so a crash mid-write cannot corrupt the graph.
            tmp_path = self.file_path + ".tmp"
            try:
                with open(tmp_path, "w", encoding="utf-8") as f:
                    f.write(payload)
                # Antivirus/indexers can briefly lock the target on Windows.
                for attempt in range(5):
                    try:
                        os.replace(tmp_path, self.file_path)
                        break
                    except PermissionError:
                        if attempt == 4:
                            raise
                        time.sleep(0.1)
            except OSError as e:
                print(f"Failed to save graph: {e}")
                return False
            with self.lock:
                self._saved_revision = max(self._saved_revision, revision)
            return True

    def load(self):
        """Loads the graph from disk if it exists."""
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                try:
                    graph = nx.node_link_graph(data, edges="links")
                except TypeError:
                    graph = nx.node_link_graph(data)
                with self.lock:
                    self.graph = graph
            except Exception as e:
                print(f"Failed to load graph: {e}")
                try:
                    os.replace(self.file_path, self.file_path + ".corrupt")
                    print(f"Unreadable graph kept as {self.file_path}.corrupt")
                except OSError:
                    pass
