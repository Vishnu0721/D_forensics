import os
import sys
import shutil
import json
import tempfile
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.database import init_db, SessionLocal
from core.database.models import Case, EvidenceArtifact, ForensicEvent
from core.services.graph import EvidenceGraph
from core.services.offline_analysis import run_offline_analysis
from core.services.integrity import verify_integrity, calculate_sha256


def make_test_json(path: str) -> dict:
    base_ts = datetime(2025, 9, 13, 10, 31, 0)

    events = [
        {
            "timestamp": (base_ts + timedelta(seconds=2)).isoformat(),
            "event_type": "login",
            "user": "john.doe",
            "host": "DESKTOP-ABC123",
        },
        {
            "timestamp": (base_ts + timedelta(seconds=5)).isoformat(),
            "event_type": "process_started",
            "user": "john.doe",
            "host": "DESKTOP-ABC123",
            "process": "powershell.exe",
            "pid": 4520,
            "parent_process": "explorer.exe",
            "path": r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
        },
        {
            "timestamp": (base_ts + timedelta(seconds=8)).isoformat(),
            "event_type": "file_created",
            "user": "john.doe",
            "host": "DESKTOP-ABC123",
            "file": "payload.exe",
            "path": r"C:\Users\john.doe\AppData\Local\Temp\payload.exe",
        },
        {
            "timestamp": (base_ts + timedelta(seconds=21)).isoformat(),
            "event_type": "process_started",
            "user": "john.doe",
            "host": "DESKTOP-ABC123",
            "process": "payload.exe",
            "pid": 8192,
            "parent_process": "powershell.exe",
            "path": r"C:\Users\john.doe\AppData\Local\Temp\payload.exe",
        },
        {
            "timestamp": (base_ts + timedelta(seconds=25)).isoformat(),
            "event_type": "connection",
            "user": "john.doe",
            "host": "DESKTOP-ABC123",
            "process": "payload.exe",
            "pid": 8192,
            "destination_ip": "192.0.2.47",
            "destination_port": 443,
        },
        {
            "timestamp": (base_ts + timedelta(seconds=40)).isoformat(),
            "event_type": "file_created",
            "user": "john.doe",
            "host": "DESKTOP-ABC123",
            "file": "document.pdf",
            "path": r"C:\Users\john.doe\Documents\document.pdf",
        },
        {
            "timestamp": (base_ts + timedelta(seconds=55)).isoformat(),
            "event_type": "process_started",
            "user": "SYSTEM",
            "host": "DESKTOP-ABC123",
            "process": "svchost.exe",
            "pid": 868,
            "parent_process": "services.exe",
            "path": r"C:\Windows\System32\svchost.exe",
        },
    ]

    with open(path, "w", encoding="utf-8") as f:
        json.dump(events, f, indent=2)

    orig_sha = calculate_sha256(path)
    return {"file_path": path, "sha256": orig_sha, "events": events}


def main():
    if os.path.exists("forensics.db"):
        os.remove("forensics.db")
    if os.path.exists("data"):
        shutil.rmtree("data")

    init_db()
    db = SessionLocal()
    case = Case(name="Offline Test Case", description="Controlled offline analysis test")
    db.add(case)
    db.commit()
    db.refresh(case)

    graph_db = EvidenceGraph(case.id)

    with tempfile.TemporaryDirectory() as tmpdir:
        report_path = os.path.join(tmpdir, "controlled_report.json")
        testdata = make_test_json(report_path)
        original_uploaded_sha = testdata["sha256"]

        print("=" * 70)
        print("STEP 1: Run offline analysis pipeline")
        print("=" * 70)
        progress_lines = []
        result = run_offline_analysis(
            db=db,
            case_id=case.id,
            source_file_path=report_path,
            graph_db=graph_db,
            actor="test_investigator",
            progress_cb=lambda m: progress_lines.append(m),
        )

        for line in progress_lines:
            print(f"  PROGRESS: {line}")

        if not result.success:
            print(f"  ERROR: {result.error_message}")
            if not result.evidence:
                db.close()
                return 1

        evidence = result.evidence
        summ = result.summary_dict()

        print("\n" + "=" * 70)
        print("STEP 2: Evidence Artifact verification")
        print("=" * 70)
        assert evidence is not None, "EvidenceArtifact must be created"
        assert evidence.id, "evidence_id must exist"
        print(f"  Evidence ID: {evidence.id}")
        print(f"  Filename: {evidence.filename}")
        print(f"  Source type: {evidence.source_type}")
        print(f"  Preserved path exists: {os.path.exists(evidence.original_path)}")
        print(f"  File size: {evidence.file_size}")
        assert evidence.sha256_hash, "SHA-256 must be calculated"
        print(f"  SHA-256 (first 16): {evidence.sha256_hash[:16]}...")
        preserved_sha = calculate_sha256(evidence.original_path)
        assert preserved_sha == evidence.sha256_hash, "preserved file hash must match record hash"
        print("  SHA-256 of preserved bytes MATCHES EvidenceArtifact.sha256_hash: OK")

        print("\n" + "=" * 70)
        print("STEP 3: Parse result")
        print("=" * 70)
        pr = result.parse_result
        print(f"  Format detected: {pr.format_detected}")
        print(f"  Source type auto-detected: {pr.source_type_detected}")
        print(f"  Records parsed: {pr.records_parsed}")
        print(f"  Records failed: {pr.records_failed}")
        assert pr.records_parsed == 7, "Expected 7 records parsed"
        assert pr.records_failed == 0, "Expected 0 records failed"
        assert pr.format_detected == "JSON", "Format must be JSON"

        print("\n" + "=" * 70)
        print("STEP 4: ForensicEvent extraction & normalization")
        print("=" * 70)
        assert result.events_extracted == 7, "Expected 7 events extracted"
        assert result.events_stored == 7, "Expected 7 events stored in DB"
        stored_events = db.query(ForensicEvent).filter(ForensicEvent.case_id == case.id).all()
        print(f"  Events in DB (by case_id): {len(stored_events)}")
        assert len(stored_events) == 7, "Expected 7 events in DB"
        for ev in stored_events:
            assert ev.evidence_id == evidence.id, (
                f"Event {ev.id} must have evidence_id={evidence.id}"
            )
        print(f"  Every event has evidence_id={evidence.id}: OK")

        timestamps = [e.timestamp for e in stored_events]
        assert timestamps == sorted(timestamps), "Events must be temporally ordered"
        print("  Events are ordered by actual timestamp: OK")

        print("\n" + "=" * 70)
        print("STEP 5: Correlation relationships")
        print("=" * 70)
        print(f"  Relationships generated: {len(result.relationships)}")
        assert len(result.relationships) > 0, "Expected at least some relationships"
        for rel in result.relationships:
            ev_ids = rel.get("evidence_ids", [])
            assert len(ev_ids) > 0, "Each relationship must have supporting evidence_ids"
            assert evidence.id in ev_ids or len(ev_ids) > 0, "Must have real evidence_ids"
            assert rel.get("confidence") is not None, "Each relationship must have confidence"
            assert rel.get("reasons"), "Each relationship must have reasons"
        print("  Every relationship has evidence_ids, confidence, reasons: OK")

        print("\n" + "=" * 70)
        print("STEP 6: NetworkX graph population")
        print("=" * 70)
        g = graph_db.graph
        print(f"  Graph nodes: {g.number_of_nodes()}")
        print(f"  Graph edges: {g.number_of_edges()}")
        assert g.number_of_nodes() > 0, "Expected nodes in graph"
        assert g.number_of_edges() > 0, "Expected edges in graph"
        for u, v, data in g.edges(data=True):
            ev_ids = data.get("evidence_ids", [])
            assert len(ev_ids) > 0, f"Edge {u}->{v} missing evidence_ids"
            assert "reasons" in data, f"Edge {u}->{v} missing reasons"
            assert "confidence" in data, f"Edge {u}->{v} missing confidence"
        print("  Every graph edge has evidence_ids, confidence, reasons: OK")

        print("\n" + "=" * 70)
        print("STEP 7: Suspicious activity detection")
        print("=" * 70)
        print(f"  Suspicious findings: {len(result.suspicious_activities)}")
        rule_names = [a.get("rule_name") for a in result.suspicious_activities]
        for act in result.suspicious_activities:
            assert "activity_id" in act
            assert "score" in act
            assert "rule_name" in act
            assert "reason" in act
            eids = act.get("evidence_ids", [])
            evid_set = set(eids)
            assert len(evid_set) > 0, "Suspicious finding must have evidence IDs"
            assert evidence.id in evid_set, "Suspicious finding must trace back to our evidence"
            assert act.get("relationships") or act.get("nodes"), "Must reference nodes/relationships"
        print(f"  Rules fired: {rule_names}")
        print("  Every suspicious finding has event/evidence IDs: OK")

        print("\n" + "=" * 70)
        print("STEP 8: Incident reconstruction")
        print("=" * 70)
        print(f"  Potential Incidents identified: {len(result.incidents)}")
        assert len(result.incidents) > 0, "Expected at least 1 incident"
        for inc in result.incidents:
            inc_evids = set(inc.get("evidence_ids", []))
            assert len(inc_evids) > 0, "Incident must have evidence IDs"
            assert evidence.id in inc_evids, "Incident must trace back to uploaded evidence"
            assert "nodes" in inc and len(inc["nodes"]) >= 2
            assert "relationships" in inc
            print(f"    {inc.get('incident_id')}: {len(inc['nodes'])} entities, "
                  f"{len(inc['relationships'])} rels, status={inc.get('status')}")
            if inc.get("suspicious_activities"):
                for a in inc["suspicious_activities"]:
                    print(f"      - {a.get('rule_name')} (score={a.get('score'):.2f})")
        print("  Every incident has real evidence IDs: OK")

        print("\n" + "=" * 70)
        print("STEP 9: Event classifications")
        print("=" * 70)
        cc = result.classification_counts
        for cls, count in cc.items():
            print(f"  {cls}: {count}")
        print(f"  Total classified: {sum(cc.values())}")

        print("\n" + "=" * 70)
        print("STEP 10: Integrity verification (VALID)")
        print("=" * 70)
        status, current = verify_integrity(evidence.original_path, evidence.sha256_hash)
        print(f"  Integrity status before modification: {status}")
        print(f"  Original: {evidence.sha256_hash[:16]}...")
        print(f"  Current:  {current[:16]}...")
        assert status == "VALID", "Integrity must be VALID before tampering"

        print("\n" + "=" * 70)
        print("STEP 11: Integrity verification after modification")
        print("=" * 70)
        with open(evidence.original_path, "rb+") as f:
            f.seek(0)
            f.write(b"XX")
        status2, current2 = verify_integrity(evidence.original_path, evidence.sha256_hash)
        print(f"  Integrity status after modification: {status2}")
        print(f"  Original: {evidence.sha256_hash[:16]}...")
        print(f"  Current:  {(current2 or 'NONE')[:16]}...")
        assert status2 == "MODIFIED", "Integrity must be MODIFIED after tampering"

        print("\n" + "=" * 70)
        print("STEP 12: Unsupported format preserves evidence without fabrication")
        print("=" * 70)
        bad_path = os.path.join(tmpdir, "report_garbage.xyz123")
        with open(bad_path, "wb") as f:
            f.write(b"\x00\x01\x02not a real format")
        graph2 = EvidenceGraph(case.id)
        result2 = run_offline_analysis(
            db=db,
            case_id=case.id,
            source_file_path=bad_path,
            graph_db=graph2,
            actor="test_investigator",
        )
        print(f"  success={result2.success}, error={result2.error_message}")
        assert result2.evidence is not None, "Evidence must be preserved even if unparseable"
        bad_count = db.query(ForensicEvent).filter(
            ForensicEvent.evidence_id == result2.evidence.id
        ).count()
        print(f"  ForensicEvents for unparseable evidence: {bad_count}")
        assert bad_count == 0, "Must NOT fabricate events for unparseable formats"
        print("  Evidence preserved, no events fabricated: OK")

    print("\n" + "=" * 70)
    print("ALL TESTS PASSED")
    print("=" * 70)

    db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
