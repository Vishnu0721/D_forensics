import networkx as nx
from typing import List, Dict, Any
from datetime import datetime

from core.services.suspicious import detect_suspicious_activity

class IncidentReconstructionEngine:
    def __init__(self, graph: nx.MultiDiGraph, all_suspicious: List[Dict[str, Any]] = None):
        self.graph = graph
        self.all_suspicious = all_suspicious if all_suspicious is not None else detect_suspicious_activity(graph)

    def _sort_events_causally(self, subgraph: nx.MultiDiGraph) -> List[Dict[str, Any]]:
        """
        Attempts to sort events causally based on edge direction and time.
        Uses topological sort if acyclic, otherwise falls back to a time-based heuristic.
        """
        # Try topological sort first (ideal causal chain)
        try:
            nodes_sorted = list(nx.topological_sort(subgraph))
            return [{"id": node_id, **subgraph.nodes[node_id]} for node_id in nodes_sorted]
        except nx.NetworkXUnfeasible:
            # Graph has cycles, fallback to a heuristic scoring (degree-based or temporal if available)
            # Since our nodes are entities (Process, File) rather than raw events, 
            # we sort by in-degree (root causes have lower in-degree).
            nodes_with_degrees = list(subgraph.in_degree())
            nodes_with_degrees.sort(key=lambda x: x[1])
            return [{"id": node_id, **subgraph.nodes[node_id]} for node_id, _ in nodes_with_degrees]

    def _generate_human_timeline(self, ordered_nodes: List[Dict[str, Any]], subgraph: nx.MultiDiGraph) -> str:
        """
        Generates a readable step-by-step text timeline based on the causal order of entities.
        """
        timeline = []
        for i, node in enumerate(ordered_nodes):
            step = f"Step {i+1}: {node.get('type', 'Unknown')} '{node['id']}'"
            timeline.append(step)
            
            # Check outgoing edges from this node to subsequent nodes to describe the action
            out_edges = []
            for j in range(i+1, len(ordered_nodes)):
                target_id = ordered_nodes[j]['id']
                if subgraph.has_edge(node['id'], target_id):
                    # For MultiDiGraph, there could be multiple edges
                    edge_data_dict = subgraph.get_edge_data(node['id'], target_id)
                    for key, edge_data in edge_data_dict.items():
                        rel_type = edge_data.get('relationship_type', key)
                        out_edges.append(f"  -> {rel_type} -> {target_id}")
            
            if out_edges:
                timeline.extend(out_edges)
                
        return "\n".join(timeline)

    def query_related(self, node_id: str) -> Dict[str, Any]:
        """
        Given a specific node, traverse the graph and return the connected subgraph 
        with the same causal ordering and timeline.
        """
        if node_id not in self.graph:
            return None
            
        undirected_graph = self.graph.to_undirected()
        component = nx.node_connected_component(undirected_graph, node_id)
        subgraph = self.graph.subgraph(component)
        
        ordered_nodes = self._sort_events_causally(subgraph)
        timeline_text = self._generate_human_timeline(ordered_nodes, subgraph)
        
        return {
            "root_node": node_id,
            "nodes": ordered_nodes,
            "timeline": timeline_text
        }

    def reconstruct_all(self) -> List[Dict[str, Any]]:
        incidents = []
        undirected_graph = self.graph.to_undirected()
        components = list(nx.connected_components(undirected_graph))
        
        for idx, component in enumerate(components):
            if len(component) < 2:
                continue
                
            incident = {
                "incident_id": f"INC-{idx+1:03d}",
                "nodes": [],
                "relationships": [],
                "suspicious_activities": [],
                "status": "Normal",
                "evidence_ids": set(),
                "timeline": "",
                "start_time": "Available in Event Details",
                "end_time": "Available in Event Details",
                "reconstruction_reason": "Correlated activity chain discovered via deterministic rules."
            }
            
            for act in self.all_suspicious:
                if any(n in component for n in act["nodes"]):
                    incident["suspicious_activities"].append(act)
                    incident["status"] = "Requires Investigation"
                    for eid in act.get("evidence_ids", []):
                        incident["evidence_ids"].add(eid)
                        
            subgraph = self.graph.subgraph(component)
            
            # Causal Ordering
            ordered_nodes = self._sort_events_causally(subgraph)
            incident["nodes"] = ordered_nodes
            
            # Generate Timeline Text
            incident["timeline"] = self._generate_human_timeline(ordered_nodes, subgraph)
                
            # Retrieve edges within this component
            for u, v, data in subgraph.edges(data=True):
                incident["relationships"].append({"source": u, "target": v, **data})
                for eid in data.get("evidence_ids", []):
                    incident["evidence_ids"].add(eid)
                    
            incident["evidence_ids"] = list(incident["evidence_ids"])
            incidents.append(incident)
            
        return incidents

# For backward compatibility with existing code that calls this function directly:
def reconstruct_incidents(graph: nx.MultiDiGraph, all_suspicious: List[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    engine = IncidentReconstructionEngine(graph, all_suspicious)
    return engine.reconstruct_all()
