# Digital Forensics — Web UI

Light-theme React shell (Phase 0). Talks to the FastAPI app in `../api/`.

## Setup

```bash
cd web
npm install
npm run dev
```

UI: http://127.0.0.1:5173  

API (separate terminal, from repo root):

```powershell
cd D:\D_forensics
$env:PYTHONPATH = "D:\D_forensics"
pip install -r api/requirements.txt
uvicorn api.main:app --reload --app-dir .
```

Vite proxies `/api` and `/health` to port 8000.

## Manual UI check (Phase 2)

1. Open http://127.0.0.1:5173  
2. Click **New investigation** → create a case  
3. On Overview, **Choose evidence file** → pick `web/fixtures/sample_evidence.json`  
4. Wait for analysis → stats and top findings should populate  

## Design tokens

See `src/styles/tokens.css` — light surfaces, slate-teal accent, status colors with plain-language labels.

## Phase

- **0–7 complete** on `feature/webapp` (tour, export, live agent, hardening)
- Data isolation: `web_data/` only — do not mix with desktop `main` data paths
