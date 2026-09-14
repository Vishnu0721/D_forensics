import networkx as nx
from typing import List, Dict, Any, Optional
import json
import os


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
    def __init__(self, case_id: str, storage_dir: str = "data"):
        self.case_id = case_id
        self.graph = nx.MultiDiGraph()
        self.storage_dir = storage_dir
        os.makedirs(self.storage_dir, exist_ok=True)
        self.file_path = os.path.join(self.storage_dir, f"{case_id}_graph.json")
        self.load()

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

    def populate_from_correlations(self, relationships: List[Dict[str, Any]]):
        for rel in relationships:
            self.add_relationship(rel)
        # self.save() is debounced to main_window.py to avoid I/O bottlenecks

    def get_all_nodes(self) -> List[Dict[str, Any]]:
        return [{"id": n, **d} for n, d in self.graph.nodes(data=True)]

    def get_all_edges(self) -> List[Dict[str, Any]]:
        return [{"source": u, "target": v, **d} for u, v, d in self.graph.edges(data=True)]

    def save(self):
        """Persists the in-memory graph to disk (zero-cost DB alternative)."""
        data = nx.node_link_data(self.graph)
        with open(self.file_path, "w") as f:
            json.dump(data, f, indent=2)

    def load(self):
        """Loads the graph from disk if it exists."""
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, "r") as f:
                    data = json.load(f)
                    self.graph = nx.node_link_graph(data)
            except Exception as e:
                print(f"Failed to load graph: {e}")
