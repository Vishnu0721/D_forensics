import networkx as nx
from typing import List, Dict, Any
import hashlib
from datetime import datetime

def detect_suspicious_activity(graph: nx.MultiDiGraph) -> List[Dict[str, Any]]:
    """
    Evaluates the graph (nodes and relationships) against suspicious activity rules.
    Returns a list of suspicious activities with deterministically calculated scores.
    """
    suspicious_activities = []
    seen_activities = set()
    
    # We iterate over edges to find pattern matches
    for u, v, key, data in graph.edges(keys=True, data=True):
        
        # Rule 1 & 2: Unusual Directory Execution & Rapid Execution
        if key == 'EXECUTED_AS':
            file_node_id = u
            process_node_id = v
            
            # The correlation engine currently just uses basename for File ID,
            # but we can check if reasons contain path info or if node data has it.
            reasons = data.get("reasons", [])
            reasons_str = " ".join(reasons).lower()
            
            is_unusual_dir = "appdata" in reasons_str or "temp" in reasons_str or "downloads" in reasons_str
            
            if is_unusual_dir:
                act_id = f"SUSP-DIR-{process_node_id}"
                if act_id not in seen_activities:
                    suspicious_activities.append({
                        "activity_id": act_id,
                        "score": 0.70,
                        "rule_name": "Unusual Directory Execution",
                        "reason": "Process executed from a user-writable or temporary directory.",
                        "timestamp": datetime.utcnow().isoformat() + "Z",
                        "evidence_ids": list(data.get("evidence_ids", [])),
                        "relationships": [{"source": u, "target": v, "type": key, "confidence": data.get("confidence", 0.0)}],
                        "nodes": [u, v]
                    })
                    seen_activities.add(act_id)
            else:
                # Standard rapid execution (created and executed)
                act_id = f"SUSP-EXEC-{process_node_id}"
                if act_id not in seen_activities:
                    suspicious_activities.append({
                        "activity_id": act_id,
                        "score": 0.40,
                        "rule_name": "Rapid Execution",
                        "reason": "Executable file was created and executed shortly afterward.",
                        "timestamp": datetime.utcnow().isoformat() + "Z",
                        "evidence_ids": list(data.get("evidence_ids", [])),
                        "relationships": [{"source": u, "target": v, "type": key, "confidence": data.get("confidence", 0.0)}],
                        "nodes": [u, v]
                    })
                    seen_activities.add(act_id)
                    
        # Rule 3: Network Execution
        if key == 'CONNECTED_TO':
            process_node_id = u
            ip_node_id = v
            
            # Check if this process was recently executed from a file (has incoming EXECUTED_AS)
            executed_edges = [edge for edge in graph.in_edges(process_node_id, keys=True, data=True) if edge[2] == 'EXECUTED_AS']
            
            if executed_edges:
                file_node_id = executed_edges[0][0]
                exec_data = executed_edges[0][3]
                
                # Combine evidence
                evidence = list(set(data.get("evidence_ids", []) + exec_data.get("evidence_ids", [])))
                
                act_id = f"SUSP-NET-{process_node_id}-{ip_node_id}"
                if act_id not in seen_activities:
                    suspicious_activities.append({
                        "activity_id": act_id,
                        "score": 0.85,
                        "rule_name": "Network Execution",
                        "reason": "A newly created or dropped file was executed and established an outbound network connection.",
                        "timestamp": datetime.utcnow().isoformat() + "Z",
                        "evidence_ids": evidence,
                        "relationships": [
                            {"source": file_node_id, "target": process_node_id, "type": "EXECUTED_AS", "confidence": exec_data.get("confidence", 0.0)},
                            {"source": process_node_id, "target": ip_node_id, "type": key, "confidence": data.get("confidence", 0.0)}
                        ],
                        "nodes": [file_node_id, process_node_id, ip_node_id]
                    })
                    seen_activities.add(act_id)
                    
    # Sort by score descending
    suspicious_activities.sort(key=lambda x: x["score"], reverse=True)
    return suspicious_activities
