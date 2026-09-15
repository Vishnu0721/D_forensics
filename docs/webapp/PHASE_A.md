# Phase A — Foundations & clarity contract

Status: **locked — Phases B–J implemented on top**  
Branch: `feature/webapp`  
Date: 2026-09-15

This phase defines **what** the web app is and **how** it must feel.  
It does **not** implement cases, import, analysis, timeline, graph, live monitoring, or export.

---

## Problem we are solving

The desktop PySide6 UI shows useful forensic data, but puts **controls, metrics, logs, graph, and integrity** on one crowded screen. Users see jargon and competing panels.

The web app must present the **same pipeline data** in a **light, white + blue** UI where each screen has **one job** and language is clear to non-experts.

---

## Locked product decisions

| Decision | Choice |
|----------|--------|
| MVP focus | **Import-first** investigation in the browser |
| Live monitoring | **Later phase** (optional local watch) — not Phase A |
| Desktop app | Remains supported for capture; web is the clear investigation UI |
| Auth (v1) | **None** — local academic use |
| Theme | **Light-first** white + blue; dark mode optional later |
| Graph engine | Keep **NetworkX** via `core/` when analysis is built |
| Data isolation | Web uses **`web_data/`** + `forensics_web.db` only — never desktop `forensics.db` / `data/` |
| Stack | FastAPI (`api/`) + React/Vite (`web/`) + shared `core/` |

---

## Clarity principles

1. **One job per screen** — no desktop-style all-in-one dashboard.
2. **Plain language first** — IDs, hashes, PIDs behind “Technical details”.
3. **No dual activity lists** — one Timeline only (when built).
4. **No hash-first tables** — Integrity shows human status first (when built).
5. **Overview answers “what next?”** — not seven equal jargon counters.
6. **Light white + blue** — calm lab UI, not dark SOC chrome.

---

## Information architecture

### Primary nav (always visible in a case)

| Route (planned) | Label | One job |
|-----------------|-------|---------|
| `/cases/:id` | Overview | What happened? What should I do next? |
| `/cases/:id/timeline` | Timeline | Activity in order, as plain sentences |
| `/cases/:id/connections` | Connections | Who/what is linked (Simple graph by default) |

### Secondary nav (“More”)

| Route (planned) | Label | One job |
|-----------------|-------|---------|
| `/cases/:id/import` | Import | Bring evidence files into this case |
| `/cases/:id/findings` | Findings | What needs a look + activity stories |
| `/cases/:id/integrity` | Integrity | Are preserved files still intact? |
| `/cases/:id/settings` | Settings | About / theme notes |

### Outside a case

| Route | Label | One job |
|-------|-------|---------|
| `/` | Home | List investigations / start new |
| `/cases/new` | New investigation | Name a case (later phase) |

---

## Glossary (UI copy)

| Desktop / internal term | Web UI label |
|-------------------------|--------------|
| Evidence Artifacts | Saved records |
| Relationships | Links |
| Potential Incidents | Activity stories |
| Suspicious / Needs attention | Needs a look |
| Offline Evidence (Advanced) | Import evidence |
| User Activities | User actions |
| Background | Background noise |
| Evidence Graph | Connections |
| Incident Summary | Activity stories (under Findings) |
| LIVE / STOPPED (stacked banners) | One status + one next step |

**Do not show in default UI copy:** raw enum names (`SUSPICIOUS_ACTIVITY`, `VALID`, etc.).

---

## Repo layout (Phase A)

```text
api/                 # FastAPI — health + meta only in Phase A
web/                 # React + Vite — tokens + IA shell only
web_data/            # Web-only runtime (gitignored contents)
docs/webapp/         # Planning docs (this file)
core/                # Shared forensic pipeline (unchanged)
gui/                 # Desktop only (unchanged)
```

---

## What Phase A ships

| Deliverable | Status |
|-------------|--------|
| This decisions document | Yes |
| `web_data/` isolation config | Yes |
| API: `GET /health`, `GET /api/v1/meta` | Yes |
| OpenAPI draft (future paths marked, not implemented) | Yes |
| Web: light white/blue tokens + IA placeholder shell | Yes |
| Cases / import / analysis / live / export | **No — later phases** |

---

## Explicit non-goals (Phase A)

- No SQLite case writes from the API yet  
- No evidence upload or analysis jobs  
- No Cytoscape / timeline / findings pages wired to data  
- No desktop DB bridge  
- No auth  

---

## Exit criteria

- [x] Old Phase 0–7 feature webapp code removed  
- [x] `docs/webapp/PHASE_A.md` written  
- [x] API starts and returns `phase: "A"`  
- [x] Meta endpoint returns IA + glossary + feature flags off  
- [x] Web shows light theme and IA placeholders only  
- [ ] **Reviewer lock** — you approve glossary, IA, and principles  

**Next (only after your OK):** Phase B — case shell & home (still no analysis).

---

## How to verify Phase A

```powershell
# Terminal 1 — API
cd D:\D_forensics
$env:PYTHONPATH = (Get-Location).Path
pip install -r api/requirements.txt
uvicorn api.main:app --reload --app-dir .

# Check
# http://127.0.0.1:8000/health
# http://127.0.0.1:8000/api/v1/meta
# http://127.0.0.1:8000/docs
```

```powershell
# Terminal 2 — UI
cd D:\D_forensics\web
npm install
npm run dev
# http://127.0.0.1:5173
```
