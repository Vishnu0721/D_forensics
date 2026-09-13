import json
from core.services.report_parser import parse_json
from core.services.normalization import normalize_records
from core.services.correlation import correlate_events
from core.services.reconstruction import reconstruct_incidents
from core.services.suspicious import detect_suspicious_activity
import networkx as nx
from typing import List, Dict, Any

# Mock Sysmon Data
SYSMON_DATA = {
    "events": [
        {
            "@timestamp": "2019-04-29T20:59:14.000Z",
            "winlog": {
                "event_id": 11,
                "computer_name": "WORKSTATION-01",
                "event_data": {
                    "UtcTime": "2019-04-29 20:59:14.000",
                    "TargetFilename": "C:\\Users\\jdoe\\AppData\\Local\\Temp\\update_svc.exe",
                    "User": "CORP\\jdoe"
                }
            }
        },
        {
            "@timestamp": "2019-04-29T20:59:15.000Z",
            "winlog": {
                "event_id": 1,
                "computer_name": "WORKSTATION-01",
                "event_data": {
                    "UtcTime": "2019-04-29 20:59:15.000",
                    "ProcessId": "4104",
                    "Image": "C:\\Users\\jdoe\\AppData\\Local\\Temp\\update_svc.exe",
                    "ParentImage": "C:\\Program Files\\Microsoft Office\\Office16\\WINWORD.EXE",
                    "ParentProcessId": "1024",
                    "Hashes": "MD5=44D88612FEA8A8F36DE82E1278ABB02F,SHA256=7A1E2B3C1234567890ABCDEF1234567890ABCDEF1234567890ABCDEF12345678,IMPHASH=A6",
                    "User": "CORP\\jdoe"
                }
            }
        },
        {
            "@timestamp": "2019-04-29T20:59:16.000Z",
            "winlog": {
                "event_id": 3,
                "computer_name": "WORKSTATION-01",
                "event_data": {
                    "UtcTime": "2019-04-29 20:59:16.000",
                    "ProcessId": "4104",
                    "Image": "C:\\Users\\jdoe\\AppData\\Local\\Temp\\update_svc.exe",
                    "DestinationIp": "192.168.1.100",
                    "DestinationPort": "443"
                }
            }
        },
        {
            "@timestamp": "2019-04-29T20:59:20.000Z",
            "winlog": {
                "event_id": 5,
                "computer_name": "WORKSTATION-01",
                "event_data": {
                    "UtcTime": "2019-04-29 20:59:20.000",
                    "ProcessId": "4104",
                    "Image": "C:\\Users\\jdoe\\AppData\\Local\\Temp\\update_svc.exe"
                }
            }
        },
        {
            "@timestamp": "2019-04-29T21:00:00.000Z",
            "winlog": {
                "event_id": 11,
                "computer_name": "WORKSTATION-01",
                "event_data": {
                    "UtcTime": "2019-04-29 21:00:00.000",
                    "TargetFilename": "D:\\Tools\\rapid.exe",
                    "User": "CORP\\jdoe"
                }
            }
        },
        {
            "@timestamp": "2019-04-29T21:00:01.000Z",
            "winlog": {
                "event_id": 1,
                "computer_name": "WORKSTATION-01",
                "event_data": {
                    "UtcTime": "2019-04-29 21:00:01.000",
                    "ProcessId": "5500",
                    "Image": "D:\\Tools\\rapid.exe",
                    "ParentImage": "C:\\Windows\\explorer.exe",
                    "ParentProcessId": "888"
                }
            }
        }
    ]
}

def run_test():
    with open("test_sysmon.json", "w") as f:
        json.dump(SYSMON_DATA, f)
        
    records, failed = parse_json("test_sysmon.json")
    print(f"Parsed {len(records)} records, {failed} failed")
    
    events_gen = normalize_records(records, source_type="process", case_id="1", evidence_id="1")
    events = list(events_gen)
    print(f"Normalized {len(events)} events")
    
    # Just checking if fields exist
    for ev in events:
        print(f"Event: {ev.event_type} | PID: {ev.pid} | Process: {ev.process} | File: {ev.file} | Path: {ev.path}")

    relationships = correlate_events(events)
    graph = nx.MultiDiGraph()
    for r in relationships:
        u, v = r["source"]["id"], r["target"]["id"]
        graph.add_node(u, type=r["source"]["type"])
        graph.add_node(v, type=r["target"]["type"])
        graph.add_edge(u, v, key=r["type"], **r)
    print(f"Correlated {len(relationships)} relationships")
    
    suspicious = detect_suspicious_activity(graph)
    rules_triggered = [s.get("rule_name") for s in suspicious]
    print("Suspicious activities triggered:")
    for rule in rules_triggered:
        print(f"- {rule}")
        
    incidents = reconstruct_incidents(graph, suspicious)
    print(f"Reconstructed {len(incidents)} incidents")
    
    # Assertions
    assert "Unusual Directory Execution" in rules_triggered, "Expected 'Unusual Directory Execution' rule to fire"
    assert "Network Execution" in rules_triggered, "Expected 'Network Execution' rule to fire"
    assert "Rapid Execution" in rules_triggered, "Expected 'Rapid Execution' rule to fire"

    # Also assert the hash logic worked properly
    hash_record = [r for r in records if r.get('event_type') == 'process_started' and r.get('process') == 'update_svc.exe'][0]
    assert hash_record['file_hash'] == '7A1E2B3C1234567890ABCDEF1234567890ABCDEF1234567890ABCDEF12345678', "Hash parsing failed"
    
    print("All assertions passed. Sysmon Adapter works!")

if __name__ == "__main__":
    run_test()
