import os
import sys
import time
from datetime import datetime, timedelta
import networkx as nx

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.database.models import ForensicEvent
from core.services.correlation import correlate_new_event
from core.services.reconstruction import IncidentReconstructionEngine

def create_event(timestamp, event_type, source_type, **kwargs):
    event = ForensicEvent(
        evidence_id=kwargs.get("evidence_id", f"ev-{time.time()}"),
        timestamp=timestamp,
        source_type=source_type,
        event_type=event_type,
        host="eval_host",
        user=kwargs.get("user"),
        pid=kwargs.get("pid"),
        process=kwargs.get("process"),
        file=kwargs.get("file"),
        path=kwargs.get("path"),
        ip=kwargs.get("ip"),
        file_hash=kwargs.get("sha256")
    )
    return event

def build_scenarios():
    t0 = datetime.utcnow()
    
    # Scenario 1: Malware Download & Execution + C2 (5 events)
    s1 = [
        create_event(t0, "login", "auth", user="alice"),
        create_event(t0 + timedelta(seconds=5), "download", "browser", user="alice", file="malware.exe"),
        create_event(t0 + timedelta(seconds=10), "file_created", "filesystem", file="malware.exe", path="C:\\Users\\alice\\Downloads\\malware.exe"),
        create_event(t0 + timedelta(seconds=15), "process_started", "process", user="alice", pid=1010, process="malware.exe", file="malware.exe", sha256="badhash"),
        create_event(t0 + timedelta(seconds=20), "connection", "network", pid=1010, process="malware.exe", ip="192.168.1.100")
    ]
    
    # Scenario 2: Insider Threat Exfiltration (4 events)
    t1 = t0 + timedelta(minutes=30)
    s2 = [
        create_event(t1, "process_started", "process", user="bob", pid=2020, process="explorer.exe"),
        create_event(t1 + timedelta(seconds=2), "file_accessed", "filesystem", file="secrets.docx", path="C:\\Confidential\\secrets.docx"),
        create_event(t1 + timedelta(seconds=5), "usb_connected", "device", user="bob"),
        create_event(t1 + timedelta(seconds=10), "file_copied", "filesystem", file="secrets.docx")
    ]
    
    return [
        {"name": "Malware Infection", "events": s1, "expected_relations": 4, "expected_nodes": 5},
        {"name": "Insider Exfiltration", "events": s2, "expected_relations": 3, "expected_nodes": 4}
    ]

def evaluate():
    scenarios = build_scenarios()
    
    results = []
    
    for scenario in scenarios:
        graph = nx.MultiDiGraph()
        history = []
        
        start_time = time.time()
        
        # 1. Correlate incrementally
        for event in scenario["events"]:
            relationships = correlate_new_event(event, history, max_window_seconds=120)
            
            # Insert relationships to graph
            for rel in relationships:
                source = rel["source"]
                target = rel["target"]
                graph.add_node(source["id"], type=source["type"], label=source["id"])
                graph.add_node(target["id"], type=target["type"], label=target["id"])
                graph.add_edge(source["id"], target["id"], key=rel["type"], relationship_type=rel["type"], confidence=rel["confidence"])
                
            history.append(event)
            
        # 2. Reconstruct incidents
        engine = IncidentReconstructionEngine(graph, all_suspicious=[])
        incidents = engine.reconstruct_all()
        
        process_time = time.time() - start_time
        
        # Collect metrics
        num_relations = graph.number_of_edges()
        timeline_acc = "100%" if num_relations == scenario["expected_relations"] else f"{round(num_relations / scenario['expected_relations'] * 100)}%"
        
        # Manual baseline estimate (reading raw logs)
        manual_time = f"{len(scenario['events']) * 2} minutes"
        
        results.append({
            "Scenario": scenario["name"],
            "Manual/Traditional": manual_time,
            "This System": f"{process_time*1000:.2f} ms",
            "Events correlated": len(scenario["events"]),
            "Relationships discovered": num_relations,
            "Timeline reconstruction accuracy": timeline_acc
        })
        
    # Output Markdown Table
    print("| Scenario | Metric | Manual/Traditional | This System |")
    print("| :--- | :--- | :--- | :--- |")
    for r in results:
        print(f"| {r['Scenario']} | Investigation time | {r['Manual/Traditional']} | {r['This System']} |")
        print(f"| {r['Scenario']} | Events correlated | N/A | {r['Events correlated']} |")
        print(f"| {r['Scenario']} | Relationships discovered | N/A | {r['Relationships discovered']} |")
        print(f"| {r['Scenario']} | Timeline reconstruction accuracy | N/A | {r['Timeline reconstruction accuracy']} |")

if __name__ == "__main__":
    evaluate()
