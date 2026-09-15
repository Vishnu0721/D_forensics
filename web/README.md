# Digital Forensics — Web UI

Light **white + blue** investigation interface.  
One job per screen. Plain language first. Import-first workflow.

Works with the FastAPI backend in `../api/`.  
**Testers:** follow this file end-to-end.

| Doc | Purpose |
|-----|---------|
| [../README.md](../README.md) | Full project + desktop + architecture |
| [../api/README.md](../api/README.md) | API install, endpoints, smoke |
| [../docs/webapp/PHASE_A.md](../docs/webapp/PHASE_A.md) | Glossary & clarity rules |

---

## Architecture (UI)

```text
 Home  →  New investigation
              │
              ▼
         Case shell
    ┌─────┼──────┐
    ▼     ▼      ▼
 Overview Timeline Connections     ← Primary
    │
    └─ Import · Findings · Integrity · Settings   ← More

 Overview: “What next?” + plain cards + Analyze / Export / Live
 Import:   upload file  OR  copy from desktop data/evidence/
 Analyze:  same core/ pipeline as desktop offline analysis
```

Vite proxies `/api` and `/health` to `http://127.0.0.1:8000`.

---

## Prerequisites

- Node.js **18+**
- API running (see below)

---

## Run (two terminals)

### Terminal 1 — API (required)

```powershell
cd D:\D_forensics
$env:PYTHONPATH = (Get-Location).Path
pip install -r api/requirements.txt
uvicorn api.main:app --reload --app-dir .
```

Confirm: http://127.0.0.1:8000/health → `"phase": "P7"`

### Terminal 2 — UI

```powershell
cd D:\D_forensics\web
npm install
npm run dev
```

Open: **http://127.0.0.1:5173**

---

## Manual test plan (for reviewers)

Use a **new investigation** so you are not confused by old smoke-test cases on Home.

### A. Happy path (fixture)

1. Open http://127.0.0.1:5173  
2. Click **New investigation** → name it (e.g. `Demo`) → create  
3. You should see **Overview** with a clear **What next?** line  
4. Go to **Import** → upload:

   `web/fixtures/sample_evidence.json`

   (story: login → PowerShell → temp payload → outbound connection)

5. Click **Analyze** (Import or Overview) — wait until it finishes  
6. Check:

| Page | Expect |
|------|--------|
| **Overview** | Activity / Needs a look / Links / Saved records cards; next-step text updates |
| **Timeline** | Several plain-language rows; click one → drawer; expand technical details |
| **Connections** | Graph (Simple); click a node → short story |
| **Findings** | Rule findings and/or activity stories |
| **Integrity** | Row shows **Unchanged** (or similar) first; hash is secondary; **Verify now** works |
| **Export** | Overview → Markdown and HTML download |

### B. Filters & clarity

7. **Timeline** filters: All · User actions · Background noise · Needs a look · Linked · Unclear  
8. **Connections**: toggle Simple / Detailed; optional Network / Execution filters  
9. Confirm UI uses everyday labels (see glossary below), not desktop jargon

### C. Optional — live watch

10. Overview → **Start live watch** → open an app or browse briefly  
11. Event count rises → **Stop live watch**  
12. Run **Analyze** again (Analyze is disabled while live is on — by design)

### D. Optional — desktop bridge

13. Run the desktop app (`python main.py`), capture some activity, stop  
14. Web **Import** → **From desktop capture** → pick a folder under `data/evidence/`  
15. Import → **Analyze** → Timeline / Connections update  

If the bridge list is empty, desktop has not written evidence yet (or `data/evidence/` is empty).

### E. Settings

16. **Settings** → optional dark toggle (light remains the product default)

---

## Glossary (what you’ll see in the UI)

| Web label | Desktop / old jargon |
|-----------|----------------------|
| Saved records | Evidence artifacts |
| Links | Relationships |
| Needs a look | Suspicious / Needs attention |
| Activity stories | Potential incidents / Incident summary |
| Import evidence | Offline Evidence (Advanced) |
| User actions | User activities |
| Background noise | Background |
| Connections | Evidence graph |

---

## Screens (routes)

| Route | Job |
|-------|-----|
| `/` | List investigations |
| `/cases/new` | Name a new case |
| `/cases/:id` | Overview — what next? |
| `/cases/:id/timeline` | One chronological activity feed |
| `/cases/:id/connections` | Who/what is linked |
| `/cases/:id/import` | Bring evidence in |
| `/cases/:id/findings` | Needs a look + stories |
| `/cases/:id/integrity` | Are files still intact? |
| `/cases/:id/settings` | About / theme |

---

## Clean Home (remove smoke cases)

Stop the API, then from repo root:

```powershell
Remove-Item -Force .\web_data\forensics_web.db* -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force .\web_data\evidence, .\web_data\graphs, .\web_data\cases -ErrorAction SilentlyContinue
```

Restart API + refresh browser.

---

## Stack

- React 19 + Vite 6 + TypeScript  
- react-router-dom 7  
- cytoscape (Connections page)

Scripts: `npm run dev` · `npm run build` · `npm run preview`

---

## UI polish (responsive + interaction)

- **Breakpoints:** ~960px (stat grid / graph stack), ~800px (collapsible investigation menu + stacked home rows), ~520px (single-column stats, full-width buttons)
- **Cards:** panels, overview stats, investigation list cards, timeline rows, findings, and bridge items lift slightly and deepen shadow on hover (respects `prefers-reduced-motion`)
- **Tables:** Integrity / Import wrap in `.table-wrap` so wide hash columns scroll horizontally on small screens
- **Mobile nav:** Case shell shows **Investigation menu** toggle; menu closes on route change

---

## Not included (by design)

- User login / multi-user auth  
- Direct read of desktop `forensics.db` (bridge **copies** files only)  
- Remote agents / multi-machine monitoring  

---

## Responsible use

Local / authorized testing only. Live watch records activity on **this PC**. Keep the API on localhost.
