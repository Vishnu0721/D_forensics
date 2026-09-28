# Digital Forensics Monitoring and Correlation Platform

A Python desktop application for **local** live forensic monitoring, evidence integrity, graph-based correlation, and offline evidence analysis.

It captures process, filesystem, and network activity **on this computer only** (not a remote agent), stores hashed evidence artifacts, correlates related events, and presents findings in plain language for investigation and research.

## What’s new (current desktop)

Clarity and stability improvements on top of the original pipeline:

- **Single Start / Stop button** with a clear **LIVE** or **STOPPED** banner and next-step guidance
- **Plain-language activity stream** (e.g. “Chrome contacted GitHub”) instead of raw jargon
- **Needs attention** and **Activity** tabs with readable filters and empty states
- **Evidence Graph** with Simple/Detailed views, fit-to-view layout, friendly service names, and a short “story” on node click
- **Incident Summary** as activity stories (Informational vs Review recommended)
- **Evidence Integrity** tab with human labels (Unchanged / Changed on disk / File missing) and auto-verify on Stop
- **Quick tour** (Help → Quick tour) for first-time users
- Performance hardening: interruptible collectors, SQLite WAL, debounced graph updates, layout off the UI thread
- **Expanded suspicious-activity detection**: 13 rules (was 3), covering malicious document launches, disguised system programs, built-in tools abused for downloads, obfuscated PowerShell, startup persistence, disguised files and attack ports (see [Suspicious Activity Rules](#suspicious-activity-rules))
- **Reliable Evidence Graph filters**: each link records who caused it (user app, background service or unknown), so *User actions*, *Background noise* and *Unclear* show the right links, also after a restart (see [Evidence Graph Filters](#evidence-graph-filters))

> A separate **light-theme web app** is planned (same repo, later). The desktop app remains the supported UI today.

## Overview

Forensic evidence pipeline:

1. Collect raw telemetry from the local machine  
2. Persist evidence artifacts to disk with deterministic SHA-256 hashing  
3. Normalize events into a common schema  
4. Correlate related events with rule-based logic  
5. Build a relationship graph and reconstruct incidents  
6. Classify activity and present findings in the desktop dashboard  

**Stack:** Python 3.10+, PySide6 (GUI), SQLAlchemy (SQLite), NetworkX (graphs), psutil + watchdog (collectors).

## Key Features

### Live Monitoring
- Process start/stop collection (`psutil`)
- Filesystem watching on Downloads, Desktop, Documents (including OneDrive copies) and the Startup folder (`watchdog`), with noise filtering and a per-second rate limit. AppData, TEMP and System32 are not watched because their constant background churn made the system unresponsive.
- Live network connection monitoring
- Real-time evidence JSON on disk + database events
- Clear LIVE/STOPPED status and collector feedback

### Evidence Handling
- One evidence artifact per captured event
- SHA-256 fingerprint of the saved file
- Traceability from event → evidence → integrity status
- Verify Integrity (manual) and automatic check when monitoring stops

### Analysis and Correlation
- Normalization of process, filesystem, network (and offline) sources
- Rule-based correlation into a multi-relationship graph
- Suspicious pattern detection (“Needs attention”) using graph and per-event rules
- Incident reconstruction as connected activity stories
- Event classification (user / background / correlated / etc.)

### Offline Investigation
- Import preserved evidence (JSON, CSV, logs, Sysmon/Winlogbeat JSON, and related formats)
- Offline parse → normalize → graph → incidents
- Same dashboard views for imported cases

### Desktop Interface
- Monitor controls and status banner
- Activity stream with plain-language filters
- Needs attention list (severity in plain English)
- Evidence Graph (Simple view by default)
- Incident Summary and Event Details
- Evidence Integrity tab with status legend
- First-run quick tour

## Suspicious Activity Rules

Findings appear under **Needs attention**. Severity: **High** (score ≥ 0.8), **Medium** (≥ 0.5), otherwise Low. Rules are deterministic (no machine learning) and live in `core/services/suspicious.py`.

**Graph rules** (use links between files, programs and addresses):

| Rule | Score | Triggers when |
|------|-------|---------------|
| Network Execution | 0.85 | A newly created file is run and then connects to the network |
| Unusual Directory Execution | 0.70 | A new file is run from `AppData`, `Temp`, `Tmp`, `Downloads`, `$Recycle.Bin` or `Users\Public` |
| Rapid Execution | 0.40 | A new file is run within 5 minutes of being created (elsewhere) |
| Built-in Tool Contacting Internet | 0.60–0.75 | certutil, bitsadmin, mshta, rundll32, regsvr32, wscript/cscript or PowerShell connects to a public IP |
| Renamed Program Copy | 0.70 | The same executable (identical SHA-256) runs under two different names |

**Event rules** (use details of a single event):

| Rule | Score | Triggers when |
|------|-------|---------------|
| Suspicious Program Launch | 0.70–0.85 | Office, a PDF reader, a browser or a script host starts cmd, PowerShell, mshta, certutil, etc. |
| Disguised System Program | 0.80 | `svchost.exe`, `lsass.exe`, `explorer.exe` etc. run from outside the Windows folder |
| Obfuscated PowerShell | 0.60–0.95 | Encoded command, download-and-run, or Base64 decoding; hidden window + policy bypass only counts when both appear |
| Startup Persistence / Autorun Registry Change | 0.75 | A file is added to the Startup folder, or a Run/RunOnce/Winlogon/IFEO registry key changes |
| Disguised Executable | 0.75 | Double extension (`invoice.pdf.exe`) or right-to-left-override file names |
| Risky Script File | 0.55 | `.js`, `.vbs`, `.hta`, `.scr` and similar files appear in Downloads or Desktop |
| Suspicious Network Port | 0.60 | Non-loopback connection on a known attack/backdoor port (4444, 1337, 31337, IRC, Tor, …) |

Common legitimate activity is deliberately excluded, e.g. Explorer starting cmd, `-ExecutionPolicy Bypass` on its own, genuine `C:\Windows\System32` programs, scripts in project folders, and local-network connections by built-in tools.

**What is not detected:** the app sees which program connects to which IP address and port, not web pages, URLs or domain names (HTTPS traffic is encrypted). Visiting a suspicious website is only flagged if it leads to activity on the PC, for example a disguised or script file landing in Downloads, the browser starting cmd/PowerShell, or a downloaded file being run.

## Evidence Graph Filters

| Filter | Shows |
|--------|-------|
| All links | Everything in the graph |
| Needs attention | Programs, files and addresses involved in a suspicious finding |
| Part of an incident | Members of a reconstructed incident |
| User actions | Links caused by interactive apps running as the user (browsers, Explorer, Office, shells), e.g. Chrome contacting a website |
| Background noise | Links caused by background services or system accounts (svchost, SYSTEM, …) |
| Unclear | Links whose cause cannot be attributed reliably (e.g. apps not on the interactive list) |

- The origin is stored on each link when it is created and saved with the graph. Graphs saved by older versions fall back to the labels assigned during the current session.
- **Simple view** merges all processes of one program into a single circle, so links *between* processes of the same program (e.g. Chrome's helper processes sharing one executable) are hidden; the graph says so and suggests **Detailed** view.
- There is no "Linked activity" graph filter: every link is linked activity, so it would equal *All links*. The Activity tab keeps that filter, where it is meaningful.

## System Architecture

```text
Collectors (process / filesystem / network)
        ↓
Persistence (JSON on disk + SHA-256 + ForensicEvent)
        ↓
Correlation + EvidenceGraph (NetworkX)
        ↓
Suspicious rules + Incident reconstruction
        ↓
PySide6 GUI (plain-language presentation)
```

Layers:

- **Database** — cases, evidence, events, audit log (`forensics.db`, WAL mode)
- **Monitoring** — local collectors + persistence worker
- **Services** — normalization, correlation, graph, integrity, offline analysis
- **GUI** — dashboard, graph view, language helpers

## Project Structure

```text
.
├── core/
│   ├── database/          # SQLAlchemy engine + models
│   ├── monitoring/        # Live collectors + manager
│   └── services/          # Correlation, graph, integrity, offline, …
├── gui/
│   ├── main_window.py     # Main dashboard
│   ├── graph_view.py      # Interactive evidence graph
│   ├── event_language.py  # Plain-language event text
│   ├── incident_language.py
│   ├── integrity_ui.py
│   ├── quick_tour.py
│   └── offline_analysis_window.py
├── data/
│   └── evidence/          # Runtime evidence (usually gitignored)
├── evaluation/
├── main.py
├── requirements.txt
└── README.md
```

## Requirements

Python **3.10+** recommended.

```bash
pip install -r requirements.txt
```

### Main dependencies

| Package | Role |
|---------|------|
| PySide6 | Desktop GUI |
| SQLAlchemy | ORM / SQLite |
| networkx | Evidence graph |
| psutil | Process & network telemetry |
| watchdog | Filesystem events |
| pandas / pydantic | Parsing & validation |
| pywin32 | Windows helpers (installed on Windows only) |

`neo4j` is listed for optional future use; the current graph engine is **NetworkX**.

**Platform:** built and tested on **Windows 10/11**, where all collectors and detection rules apply. It also starts on Linux/macOS (the filesystem collector watches `~/Downloads`, `~/Desktop` and `~/Documents`), but most detection rules target Windows behaviour.

## Installation and Setup

```bash
git clone https://github.com/Vishnu0721/D_forensics.git
cd D_forensics
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/macOS:
# source venv/bin/activate
pip install -r requirements.txt
python main.py
```

## Running the Application

```bash
python main.py
```

Typical workflow:

1. Click **Start Monitoring** (banner turns LIVE)  
2. Open **Activity** — generate events by opening a browser or saving a file  
3. Open **Evidence Graph** — red = program, blue = internet destination  
4. Review **Incident Summary** and **Needs attention** if anything stands out  
5. Click **Stop Monitoring** — evidence stays saved; integrity is re-checked  

Optional: **Offline Evidence (Advanced)** to import preserved files.  
**Help → Quick tour** for a 30-second walkthrough.

## Evidence Workflow

```text
Collect raw events
    ↓
Persist artifact to disk
    ↓
Compute SHA-256 hash
    ↓
Normalize into forensic schema
    ↓
Store in SQLite
    ↓
Correlate and graph related events
    ↓
Classify / flag suspicious activity
    ↓
Reconstruct incident stories
```

Live evidence path: `data/evidence/<case_id>/<evidence_id>.json`  
Graph cache: `data/<case_id>_graph.json`

These paths (and `forensics.db`) are always relative to the project folder, not the folder you launch from. Set `FORENSICS_DATA_DIR` to store runtime data elsewhere (the tests use a temporary folder), and `FORENSICS_DEBUG=1` to print per-event diagnostics.

All runtime data (`forensics.db` and its `-wal`/`-shm` files, `data/evidence/`, graph caches) is git-ignored and created automatically on first start. To start from a clean slate, close the app and delete `forensics.db` and the `data/` folder.

## Data Model

| Table | Purpose |
|-------|---------|
| Case | Investigation container |
| EvidenceArtifact | Saved file + hash + integrity status |
| ForensicEvent | Normalized event linked to evidence |
| AuditLog | Investigator / system actions |

## Testing

The test scripts are the full suite. Each uses a temporary data folder, so your real `forensics.db` and evidence are never touched (`test_fs.py` briefly creates files in `scratch/`, which is git-ignored):

```bash
python test_phase1.py
python test_fs.py
python test_offline_analysis.py
python test_sysmon_adapter.py
python test_csv_and_imports.py
python test_suspicious_rules.py   # detection rules + false-positive checks
python test_graph_filters.py      # Evidence Graph filters (User actions / Background / Unclear)
python evaluation/run_evaluation.py
```

`python -m pytest` also works (install `pytest` separately), but it only collects the `test_*` functions; the scripts above cover more.

## Known Notes and Limitations

- Research / academic prototype — use only where you are authorized to monitor  
- Live precision depends on polling intervals; short-lived processes may be missed  
- Full network PID mapping on Windows may require elevated privileges  
- Large graphs can be heavy; Simple view and debouncing reduce UI freeze risk  
- Collectors watch **this PC only** — not remote endpoints  
- Live event-rule findings are kept in memory (up to 2,000) and are not restored after restart; offline analysis recomputes them  
- Some findings (e.g. a registry key or Startup file) have no graph node, so they appear in **Needs attention** but not in the graph filter  
- "Renamed Program Copy" relies on same-hash links, which only live monitoring creates (within a 2-minute window); offline imports do not produce them  
- Web pages, URLs and domain names are not monitored (see [Suspicious Activity Rules](#suspicious-activity-rules))  
- Rule-based detection flags known patterns only; it is not antivirus and can miss novel techniques  

## Roadmap (planned)

- Light-theme **web app** in the same repository (`api/` + `web/`), reusing `core/`  
- Separate DB/data paths so desktop and web do not clash when both are developed  

## Related Documentation

- [technical_audit_report.md](technical_audit_report.md) — earlier technical observations (some items may be outdated vs current GUI)
- [evaluation/run_evaluation.py](evaluation/run_evaluation.py) — evaluation helpers

## Responsible Use

Use this software only in environments where you have proper authorization. Preserve originals before reprocessing, and maintain chain-of-custody discipline for real investigations.

---

Contributions and refinements for academic and forensic experimentation are welcome.
