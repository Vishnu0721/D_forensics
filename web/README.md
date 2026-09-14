# Digital Forensics — Web App

Light-theme investigation UI (React + Vite) with a FastAPI backend.  
**Branch:** `feature/webapp`  
**Data:** `web_data/` only (does **not** use the desktop `forensics.db` / `data/`)

---

## Prerequisites

- Python **3.10+**
- Node.js **18+** (npm)
- Git

---

## Get the code

```bash
git clone https://github.com/Vishnu0721/D_forensics.git
cd D_forensics
git checkout feature/webapp
```

---

## Run (two terminals)

### Terminal 1 — API

**Windows (PowerShell):**

```powershell
cd D:\D_forensics
$env:PYTHONPATH = (Get-Location).Path
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r api/requirements.txt
uvicorn api.main:app --reload --app-dir .
```

**macOS / Linux:**

```bash
cd D_forensics
export PYTHONPATH="$(pwd)"
python3 -m venv .venv
source .venv/bin/activate
pip install -r api/requirements.txt
uvicorn api.main:app --reload --app-dir .
```

Check:

- Health: http://127.0.0.1:8000/health → `"phase": 7`
- Docs: http://127.0.0.1:8000/docs

### Terminal 2 — UI

```bash
cd web
npm install
npm run dev
```

Open: **http://127.0.0.1:5173**

Vite proxies `/api` and `/health` to port **8000**. Keep the API running while testing the UI.

---

## Manual test plan (for reviewers)

1. Open http://127.0.0.1:5173 — you should see **Home** with header (Home / New investigation / Dark).
2. Optional: finish or **Skip** the Quick tour (Esc or click outside also closes it).
3. Click **New investigation** → create a named case (do not rely on `Phase1 Smoke` cards; those are leftover API smoke tests).
4. Open the case → **Import** → use fixture:  
   `web/fixtures/sample_evidence.json`
5. After analysis, check:
   - **Overview** — stats / top findings  
   - **Timeline** — click an event (drawer opens)  
   - **Findings** — rules + activity stories  
   - **Connections** — graph (Simple / Detailed)  
   - **Integrity** — **Verify now**  
6. Optional: **Export Markdown** / **Export HTML** from Overview.
7. Optional: **Start live monitoring** (this PC only) → generate activity → **Stop** before re-analysis.
8. **Settings** — switch Light / Dark theme.

---

## Automated smoke tests (API)

From the **repo root** (API deps installed, `PYTHONPATH` set):

**Windows:**

```powershell
$env:PYTHONPATH = (Get-Location).Path
python api/smoke_phase1.py
python api/smoke_phase5_7.py
```

**macOS / Linux:**

```bash
export PYTHONPATH="$(pwd)"
python api/smoke_phase1.py
python api/smoke_phase5_7.py
```

Both should print `OK` / `OK phase 5–7`.  
Note: smoke tests **create temporary cases** named like `Phase1 Smoke` — safe to ignore or delete by removing `web_data/forensics_web.db*` and restarting the API.

---

## Data isolation

| App | Database | Evidence |
|-----|----------|----------|
| **Web** (`feature/webapp`) | `web_data/forensics_web.db` | `web_data/evidence/` |
| **Desktop** (`main`) | `forensics.db` | `data/evidence/` |

Do not mix the two while testing.

---

## Project layout

```text
api/          FastAPI (cases, import, analyze, live, export)
web/          React UI
web_data/     Web-only DB + evidence (gitignored contents)
core/         Shared forensic pipeline (reused by API)
gui/          Desktop app only (not required for web testing)
```

More detail: [docs/webapp/PHASE0.md](../docs/webapp/PHASE0.md), [docs/webapp/PHASE5_6_7.md](../docs/webapp/PHASE5_6_7.md), [api/README.md](../api/README.md)

---

## Responsible use

Use only where you are authorized to monitor or analyze evidence. Live monitoring captures activity on **this computer only**.
