# Digital Forensics — Web API

FastAPI backend for the light-theme investigation UI.  
Reuses the same forensic pipeline as the desktop app (`core/`).  
**All web data stays under `web_data/`** — never writes desktop `forensics.db` / `data/`.

| Doc | Purpose |
|-----|---------|
| [../README.md](../README.md) | Full project overview |
| [../web/README.md](../web/README.md) | Frontend + manual UI tests |
| [../docs/webapp/PHASE_A.md](../docs/webapp/PHASE_A.md) | Product / clarity contract |
| [../docs/webapp/PHASE_B_J.md](../docs/webapp/PHASE_B_J.md) | Phases B–J notes |

---

## Architecture

```text
  Browser (React)          This API                 Shared core/
  ───────────────          ────────                 ────────────
  Import / Live    ──►  FastAPI routes
                              │
                              ├─► ingest + SHA-256     (ingestion)
                              ├─► analyze job thread   (offline_analysis,
                              │                         correlation, graph,
                              │                         suspicious, reconstruction)
                              ├─► timeline / findings / graph / integrity
                              └─► optional live watch  (psutil → web_data/)

  Storage: web_data/forensics_web.db
           web_data/evidence/
           web_data/graphs/
           web_data/cases/<id>/last_analysis.json
```

Desktop captures can be **copied** in via the bridge (`data/evidence/` → ingest). The desktop SQLite DB is not opened.

---

## Prerequisites

- Python **3.10+**
- From repo root, set `PYTHONPATH` so `api` and `core` import correctly

---

## Install & run

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

| URL | Expect |
|-----|--------|
| http://127.0.0.1:8000/health | `"status": "ok"`, `"phase": "P7"`, `"version": "0.3.0"` (paths hidden by default) |
| http://127.0.0.1:8000/docs | Swagger UI |
| http://127.0.0.1:8000/api/v1/meta | Glossary, nav, feature flags |

Keep the API on **localhost**. There is no authentication.

---

## Main endpoints (for testers)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | Liveness + phase |
| GET | `/api/v1/meta` | Product meta / glossary |
| GET/POST | `/api/v1/cases` | List / create investigations |
| GET | `/api/v1/cases/{id}` | Overview (counts, `next_step`, top findings) |
| GET/POST | `/api/v1/cases/{id}/evidence` | List / upload evidence |
| POST | `/api/v1/cases/{id}/analyze` | Start analysis job (202) |
| GET | `/api/v1/jobs/{job_id}` | Poll job status |
| GET | `/api/v1/cases/{id}/events` | Timeline (`?filter=all\|user\|…`) |
| GET | `/api/v1/cases/{id}/findings` | Needs a look + activity stories |
| GET | `/api/v1/cases/{id}/graph` | Connections (`?view=simple\|detailed`) |
| GET/POST | `/api/v1/cases/{id}/integrity` | List / verify fingerprints |
| GET | `/api/v1/cases/{id}/export` | Report (`?format=markdown\|html`) |
| GET/POST | `/api/v1/cases/{id}/live/...` | Live status / start / stop |
| GET | `/api/v1/bridge/desktop` | List `data/evidence/` folders |
| POST | `/api/v1/cases/{id}/bridge/desktop` | Copy desktop folder into web case |

OpenAPI sketch (including draft history): `openapi.yaml`.

---

## Automated smoke test

Creates a temporary case, uploads `web/fixtures/sample_evidence.json`, analyzes, and checks timeline / findings / graph / integrity / export.

```powershell
cd D:\D_forensics
$env:PYTHONPATH = (Get-Location).Path
python api/smoke_phase_b_j.py
```

Success ends with: `OK phase B–J smoke`.

Smoke cases appear on the web Home page as names like `Smoke B-J`. To wipe web data:

```powershell
# Stop uvicorn first
Remove-Item -Force .\web_data\forensics_web.db* -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force .\web_data\evidence, .\web_data\graphs, .\web_data\cases -ErrorAction SilentlyContinue
```

---

## Data isolation

| App | Database | Evidence |
|-----|----------|----------|
| Desktop | `forensics.db` (repo root) | `data/evidence/` |
| Web | `web_data/forensics_web.db` | `web_data/evidence/` |

---

## Dependencies

See `requirements.txt` in this folder: FastAPI, uvicorn, SQLAlchemy, networkx, pandas, psutil, python-multipart, pydantic-settings.

Optional for EVTX: `python-evtx` (used by `core` report parser when installed).

---

## Responsible use

Local academic / authorized monitoring only. Live endpoints record activity on **this PC**. Do not bind the server to a public interface without access control.
