# Digital Forensics — Web API

Phases **A–J**. FastAPI over shared `core/`. Data: **`web_data/` only**.

See [docs/webapp/PHASE_A.md](../docs/webapp/PHASE_A.md) and [docs/webapp/PHASE_B_J.md](../docs/webapp/PHASE_B_J.md).

## Run

```powershell
cd D:\D_forensics
$env:PYTHONPATH = (Get-Location).Path
pip install -r api/requirements.txt
uvicorn api.main:app --reload --app-dir .
```

- Health: http://127.0.0.1:8000/health → `"phase": "J"`
- Docs: http://127.0.0.1:8000/docs

## Smoke

```powershell
$env:PYTHONPATH = (Get-Location).Path
python api/smoke_phase_b_j.py
```

## Isolation

| App | Database | Evidence |
|-----|----------|----------|
| Desktop | `forensics.db` | `data/evidence/` |
| Web | `web_data/forensics_web.db` | `web_data/evidence/` |

Desktop bridge **copies** files from `data/evidence/` into `web_data/` — it does not open the desktop DB.
