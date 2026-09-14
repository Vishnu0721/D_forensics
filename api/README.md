# Digital Forensics — Web API

Phase 0 skeleton. Reuses shared `core/` from the repo root.

## Setup

From the **repository root** (so `core` and `api` import correctly):

```bash
pip install -r api/requirements.txt
# Optional: also install root requirements.txt if you need full core collectors later
$env:PYTHONPATH = "D:\D_forensics"   # PowerShell — or set permanently
uvicorn api.main:app --reload --app-dir .
```

Open:

- API docs: http://127.0.0.1:8000/docs  
- Health: http://127.0.0.1:8000/health  
- Meta: http://127.0.0.1:8000/api/v1/meta  

## Smoke tests

```powershell
cd D:\D_forensics
$env:PYTHONPATH = "D:\D_forensics"
python api/smoke_phase1.py
python api/smoke_phase5_7.py
```

Phases 0–7 on `feature/webapp`. Uses `web_data/` only.

## Data isolation

| App | Database | Evidence |
|-----|----------|----------|
| Desktop | `forensics.db` | `data/evidence/` |
| Web | `web_data/forensics_web.db` | `web_data/evidence/` |

Override with env prefix `FORENSICS_WEB_` (see `api/config.py`).

## Contract

See [openapi.yaml](openapi.yaml) for the API draft (implemented through Phase 1).
