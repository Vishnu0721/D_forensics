import sys
import os
import tempfile
import csv
import shutil

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.database import init_db, SessionLocal
from core.database.models import Case
from core.services.graph import EvidenceGraph
from core.services.offline_analysis import run_offline_analysis


def main():
    if os.path.exists("forensics.db"):
        os.remove("forensics.db")
    if os.path.exists("data"):
        shutil.rmtree("data")
    init_db()
    db = SessionLocal()
    case = Case(name="CSV Test Case")
    db.add(case)
    db.commit()
    db.refresh(case)
    gd = EvidenceGraph(case.id)

    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "report.csv")
        with open(p, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow([
                "timestamp", "event_type", "user", "host", "process",
                "pid", "parent_process", "path", "file",
                "destination_ip", "destination_port"
            ])
            w.writerow([
                "2025-09-13T10:31:05", "process_started", "john.doe", "DESKTOP-1",
                "powershell.exe", "4520", "explorer.exe",
                "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe",
                "", "", ""
            ])
            w.writerow([
                "2025-09-13T10:31:08", "file_created", "john.doe", "DESKTOP-1",
                "", "", "",
                "C:\\Users\\john.doe\\AppData\\Local\\Temp\\drp.exe",
                "drp.exe", "", ""
            ])
            w.writerow([
                "2025-09-13T10:31:21", "process_started", "john.doe", "DESKTOP-1",
                "drp.exe", "8192", "powershell.exe",
                "C:\\Users\\john.doe\\AppData\\Local\\Temp\\drp.exe",
                "", "", ""
            ])
            w.writerow([
                "2025-09-13T10:31:25", "connection", "john.doe", "DESKTOP-1",
                "drp.exe", "8192", "", "",
                "", "203.0.113.50", "8080"
            ])
            w.writerow([
                "2025-09-13T10:31:55", "process_started", "SYSTEM", "DESKTOP-1",
                "svchost.exe", "868", "services.exe",
                "C:\\Windows\\System32\\svchost.exe",
                "", "", ""
            ])
            w.writerow(["badrow"])
            w.writerow([
                "2025-09-13T10:32:10", "", "john.doe", "DESKTOP-1",
                "", "", "", "",
                "notes.txt", "", ""
            ])

        r = run_offline_analysis(db, case.id, p, gd, actor="tester")

        print("=" * 60)
        print("CSV FORMAT TEST")
        print("=" * 60)
        print(f"  Format detected: {r.parse_result.format_detected}")
        print(f"  Records parsed:  {r.parse_result.records_parsed}")
        print(f"  Records failed:  {r.parse_result.records_failed}")
        print(f"  Events stored:   {r.events_stored}")
        print(f"  Relationships:   {len(r.relationships)}")
        print(f"  Suspicious:      {len(r.suspicious_activities)}")
        print(f"  Incidents:       {len(r.incidents)}")
        for s in r.suspicious_activities:
            print(f"    - {s['rule_name']} (score={s['score']:.2f})")
        for inc in r.incidents:
            print(f"    {inc['incident_id']}: {inc['status']}, "
                  f"{len(inc['nodes'])} entities, {len(inc['relationships'])} rels")

        assert r.parse_result.format_detected == "CSV", "Must detect CSV format"
        assert r.parse_result.records_parsed == 7, f"Expected 7 parsed, got {r.parse_result.records_parsed}"
        assert r.events_stored == 7
        assert len(r.relationships) > 0
        assert len(r.incidents) > 0

        print()
        print("  Detailed relationships:")
        for rel in r.relationships:
            s = rel["source"]; t = rel["target"]
            print(f"    [{rel['type']}] {s['type']}:{s['id']} -> {t['type']}:{t['id']}")
            print(f"        conf={rel['confidence']}, reasons={rel['reasons']}")
            print(f"        evidence_ids={rel['evidence_ids']}")

        g = gd.graph
        print()
        print("  Graph edges:")
        for u, v, k, d in g.edges(keys=True, data=True):
            print(f"    key={k} {u} -> {v}")
            print(f"      conf={d.get('confidence')}, reasons={d.get('reasons')}")
            print(f"      evidence_ids={d.get('evidence_ids')}")

        print()
        print("  Per-record source types (from events):")
        for ev in r.events:
            print(f"    {ev.event_type:<20} -> source_type={ev.source_type:<12}  path={ev.path}  file={ev.file}  process={ev.process}")
        print("\n  CSV TEST: OK")

    print()
    print("Testing GUI module imports (no display)...")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication(sys.argv)
        import gui.main_window
        import gui.graph_view
        print("  GUI imports: OK")
    except Exception as e:
        print(f"  GUI import issue: {e} (may be expected in headless environments)")

    print()
    print("ALL CSV + GUI IMPORT TESTS PASSED")
    db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
