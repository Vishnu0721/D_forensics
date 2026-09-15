# Digital Forensics Monitoring and Correlation Platform

Local forensic monitoring and investigation toolkit for **authorized research / academic use**.

It captures process, filesystem, and network activity **on this computer only**, stores hashed evidence, correlates related events, and presents findings in plain language.

There are **two UIs** that share the same analysis engine (`core/`):

| UI | Role | Data location |
|----|------|----------------|
| **Desktop** (PySide6) | Live capture + offline analysis on one screen | `forensics.db`, `data/` |
| **Web** (React + FastAPI) | Clear light-theme investigation (import-first) | `web_data/` only |

> **Testers (web):** start at **[web/README.md](web/README.md)**  
> **API:** **[api/README.md](api/README.md)**  
> **Web design decisions:** [docs/webapp/PHASE_A.md](docs/webapp/PHASE_A.md) · [docs/webapp/PHASE_B_J.md](docs/webapp/PHASE_B_J.md)

---

## Architecture

### Shared forensic pipeline

```text
 Collectors / Import
         │
         ▼
 Persist evidence JSON + SHA-256
         │
         ▼
 Normalize → ForensicEvent (SQLite)
         │
         ▼
 Correlate → EvidenceGraph (NetworkX)
         │
         ▼
 Suspicious rules → Incident / activity stories
         │
         ▼
 Classify (user / background / needs a look / …)
         │
    ┌────┴────┐
    ▼         ▼
 Desktop    Web API + React UI
 (PySide6)  (plain-language screens)
```

### Desktop vs web (data isolation)

```text
 Desktop                         Web
 ─────────                       ───
 forensics.db                    web_data/forensics_web.db
 data/evidence/                  web_data/evidence/
 data/<case>_graph.json          web_data/graphs/

        optional bridge (copy files only)
 data/evidence/<folder>  ──copy──►  web case → Analyze
```

The web app **never opens** the desktop database. To reuse desktop captures, use **Import → From desktop capture** (copies into `web_data/`).

### Repository layout

```text
.
├── main.py                 # Desktop entry
├── requirements.txt        # Desktop dependencies
├── core/                   # Shared pipeline (DB models, collectors, analysis)
│   ├── database/
│   ├── monitoring/
│   └── services/
├── gui/                    # PySide6 desktop UI
├── api/                    # FastAPI web backend
├── web/                    # React + Vite web frontend
├── web_data/               # Web runtime DB/evidence (gitignored contents)
├── data/                   # Desktop runtime evidence (gitignored)
├── docs/webapp/            # Web phase docs
└── evaluation/             # Evaluation helpers
```

---

## Prerequisites

| Tool | Needed for |
|------|------------|
| Python **3.10+** | Desktop + API |
| Node.js **18+** (npm) | Web UI only |
| Windows recommended | Live collectors (psutil / watchdog / pywin32) |

### Get the code

```powershell
git clone https://github.com/Vishnu0721/D_forensics.git
cd D_forensics
git checkout feature/webapp
```

(Upstream academic fork may also exist as `Kamalika-k/digital_forensics`.)

---

## 1. Desktop app

### Install

```powershell
cd D:\D_forensics
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

macOS / Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Run

```powershell
python main.py
```

### Manual test (desktop)

1. **Help → Quick tour** (optional)
2. Click **Start Monitoring** — banner shows LIVE
3. Open a browser or save a file — check **Activity**
4. Open **Evidence Graph** (Simple view) — click a node for a short story
5. Check **Incident Summary** and **Needs attention**
6. Click **Stop Monitoring** — integrity re-checks
7. Optional: **Offline Evidence (Advanced)** to import a JSON/CSV/log

### Desktop stack

| Package | Role |
|---------|------|
| PySide6 | GUI |
| SQLAlchemy | SQLite ORM |
| networkx | Evidence graph |
| psutil | Process & network |
| watchdog | Filesystem events |
| pandas / pydantic | Parsing & validation |

Graph engine is **NetworkX** (not Neo4j).

---

## 2. Web app (for other testers)

Branch: `feature/webapp` (if you are not already on it: `git checkout feature/webapp`).

You need **two terminals**. Keep both running while testing.

### Terminal 1 — API

```powershell
cd D:\D_forensics
$env:PYTHONPATH = (Get-Location).Path
pip install -r api/requirements.txt
uvicorn api.main:app --reload --app-dir .
```

Check:

- http://127.0.0.1:8000/health → `"phase": "J"`
- http://127.0.0.1:8000/docs → interactive API docs

### Terminal 2 — UI

```powershell
cd D:\D_forensics\web
npm install
npm run dev
```

Open: **http://127.0.0.1:5173**

### Automated API smoke

```powershell
cd D:\D_forensics
$env:PYTHONPATH = (Get-Location).Path
python api/smoke_phase_b_j.py
```

Expect lines ending with `OK phase B–J smoke`.  
Note: smoke creates cases named like `Smoke B-J` on the Home page (safe to ignore or delete by clearing `web_data/` — see below).

### Manual test (web) — short checklist

| Step | What to do | Pass if |
|------|------------|---------|
| 1 | Home → **New investigation** | Case Overview opens with “What next?” |
| 2 | **Import** → upload `web/fixtures/sample_evidence.json` | File listed as a saved record |
| 3 | **Analyze** (Overview or Import) | Progress finishes; activity count &gt; 0 |
| 4 | **Timeline** | Plain sentences; click opens drawer |
| 5 | **Connections** | Graph with Simple view; node click shows story |
| 6 | **Findings** | “Needs a look” and/or activity stories |
| 7 | **Integrity** → **Verify now** | Status like “Unchanged” (hash secondary) |
| 8 | Overview **Export** Markdown/HTML | File downloads |
| 9 | Optional: **Live watch** Start → activity → **Stop** | Counts rise; stop before Analyze |
| 10 | Optional: Import **From desktop capture** | Folders under `data/evidence/` appear after desktop capture |

Full UI guide: **[web/README.md](web/README.md)**

### Pass desktop data into the web app

1. Run the **desktop** app, capture or import evidence → files under `data/evidence/<folder>/`
2. In the **web** app, open a case → **Import** → **From desktop capture**
3. Pick the folder → import → **Analyze**

Or upload any `.json` / `.csv` / `.log` / `.txt` / `.evtx` on the Import page.

### Clear web test data (fresh Home page)

Stop the API, then:

```powershell
Remove-Item -Force D:\D_forensics\web_data\forensics_web.db* -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force D:\D_forensics\web_data\evidence, D:\D_forensics\web_data\graphs, D:\D_forensics\web_data\cases -ErrorAction SilentlyContinue
```

Restart the API and refresh the browser.

### Web phases (A–J)

| Phase | Focus | Status |
|-------|--------|--------|
| A | Foundations, IA, glossary, light tokens | Done |
| B | Case shell & home | Done |
| C | Import + analysis jobs | Done |
| D | Timeline | Done |
| E | Connections (graph) | Done |
| F | Findings + Integrity | Done |
| G | Overview + export | Done |
| H | Optional live watch | Done |
| I | Desktop evidence bridge | Done |
| J | Hardening & smoke | Done |

---

## Data model (shared)

| Table | Purpose |
|-------|---------|
| Case | Investigation container |
| EvidenceArtifact | Saved file + SHA-256 + integrity status |
| ForensicEvent | Normalized event linked to evidence |
| AuditLog | Investigator / system actions |

Live evidence (desktop): `data/evidence/<case_id>/…`  
Web evidence: `web_data/evidence/<case_id>/…`

---

## Desktop unit / script tests

```powershell
python -m pytest
python test_phase1.py
python test_fs.py
python test_offline_analysis.py
python test_sysmon_adapter.py
```

---

## Limitations

- Academic / research prototype — **authorized use only**
- Live capture is **this PC only** (not a remote agent)
- Short-lived processes may be missed (polling)
- Full network PID mapping on Windows may need elevated privileges
- Large graphs can be heavy — use Simple view
- Web API has **no login** — keep it on `127.0.0.1`

---

## Safety note

This is a **local forensics tool**, not remote malware. With monitoring on, it records process / network / (desktop) file activity on your machine and stores it locally. Use only where you are allowed to monitor. Stop monitoring when finished. Do not expose the API to the public internet.

---

## Related docs

- [api/README.md](api/README.md) — API run, endpoints overview, smoke  
- [web/README.md](web/README.md) — UI run + manual test plan  
- [docs/webapp/PHASE_A.md](docs/webapp/PHASE_A.md) — clarity contract & glossary  
- [docs/webapp/PHASE_B_J.md](docs/webapp/PHASE_B_J.md) — implementation notes  
- [technical_audit_report.md](technical_audit_report.md) — older audit (may be outdated)

---

## Responsible use

Use only with proper authorization. Preserve originals before reprocessing. Maintain chain-of-custody discipline for real investigations.
