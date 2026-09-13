import networkx as nx
from typing import List, Dict, Any
import json
import os

class EvidenceGraph:
    def __init__(self, case_id: str, storage_dir: str = "data"):
        self.case_id = case_id
        self.graph = nx.MultiDiGraph()
        self.storage_dir = storage_dir
        os.makedirs(self.storage_dir, exist_ok=True)
        self.file_path = os.path.join(self.storage_dir, f"{case_id}_graph.json")
        self.load()

    def add_relationship(self, rel: Dict[str, Any]):
        """Adds a relationship and its backing evidence to the graph."""
        source = rel["source"]
        target = rel["target"]
        
        # Ensure nodes exist
        self.graph.add_node(source["id"], type=source["type"], label=source["id"])
        self.graph.add_node(target["id"], type=target["type"], label=target["id"])
        
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
