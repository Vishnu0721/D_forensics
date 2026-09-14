# Digital Forensics — Web API

FastAPI backend for the web app on branch **`feature/webapp`**. Reuses shared `core/` from the repo root.  
Writes only to **`web_data/`** (never desktop `forensics.db` / `data/`).

**Full tester guide (UI + API):** [web/README.md](../web/README.md)

## Setup

From the **repository root**:

**Windows (PowerShell):**

```powershell
$env:PYTHONPATH = (Get-Location).Path
pip install -r api/requirements.txt
uvicorn api.main:app --reload --app-dir .
```

**macOS / Linux:**

```bash
export PYTHONPATH="$(pwd)"
pip install -r api/requirements.txt
uvicorn api.main:app --reload --app-dir .
```

| URL | Purpose |
|-----|---------|
| http://127.0.0.1:8000/health | Liveness (`phase` should be `7`) |
| http://127.0.0.1:8000/docs | Interactive OpenAPI |
| http://127.0.0.1:8000/api/v1/meta | Feature flags / nav |

## Smoke tests

```powershell
$env:PYTHONPATH = (Get-Location).Path
python api/smoke_phase1.py
python api/smoke_phase5_7.py
```

Creates temporary cases (`Phase1 Smoke`, etc.) — not required for manual UI testing.

## Data isolation

| App | Database | Evidence |
|-----|----------|----------|
| Desktop | `forensics.db` | `data/evidence/` |
| Web | `web_data/forensics_web.db` | `web_data/evidence/` |

Env overrides use prefix `FORENSICS_WEB_` (see `api/config.py`).

## Contract

See [openapi.yaml](openapi.yaml).
