# Digital Forensics — Web UI

Light white/blue investigation UI for the FastAPI backend. One job per screen, plain language, import-first workflow.

## Run

Keep the API running first (see `api/README.md`).

```powershell
# Terminal 1 — API (repo root)
cd D:\D_forensics
$env:PYTHONPATH = (Get-Location).Path
uvicorn api.main:app --reload --app-dir .
```

```powershell
# Terminal 2 — UI
cd D:\D_forensics\web
npm install
npm run dev
```

Open http://127.0.0.1:5173

Vite proxies `/api` and `/health` to port **8000**.

## Manual test steps

1. **Home** — `/` lists investigations from `GET /api/v1/cases`. Click **New investigation**.
2. **Create** — name a case; you land on Overview with a plain **What next?** step.
3. **Import** — upload `web/fixtures/sample_evidence.json` (login → PowerShell → payload → connection). Optionally use **From desktop capture** if `data/evidence/` folders exist.
4. **Analyze** — from Overview or Import; progress polls `GET /api/v1/jobs/:id`.
5. **Timeline** — filter All / User actions / Background noise / Needs a look / Linked / Unclear; click a row for the drawer (technical details collapsed).
6. **Connections** — Simple/Detailed Cytoscape graph; click a node for its story; try Network / Execution filters.
7. **Findings** — Needs a look + Activity stories sections.
8. **Integrity** — status label first, hash secondary; **Verify now**.
9. **Export** — Overview Markdown / HTML download links.
10. **Live** — Overview Start/Stop live watch (local PC only). Stop before Analyze.
11. **Settings** — light/dark toggle (dark is optional; light remains default).

## Glossary (UI)

| Prefer | Avoid (desktop jargon) |
|--------|-------------------------|
| Saved records | Evidence artifacts |
| Links | Relationships |
| Needs a look | Suspicious |
| Activity stories | Potential incidents |
| Import evidence | Offline evidence (advanced) |
| User actions | User activities |
| Connections | Evidence graph |

## Stack

- React 19 + Vite 6 + TypeScript
- react-router-dom 7
- cytoscape (Connections)

## Not included

- Auth
- Desktop DB access (bridge copies files into `web_data/` only)
