# Phase 0 — Foundations & decisions

Status: **locked for implementation** (2026-09-14)  
Branch: `feature/webapp`

## Product decisions

| Decision | Choice |
|----------|--------|
| MVP scope | **Offline / import-first** investigation web app |
| Live monitoring | **Deferred** to Phase 6 (optional local agent) |
| Desktop app | Remains supported; web developed in parallel |
| Auth (v1) | **None** — local academic use only |
| Theme | **Light-first** (clean lab UI, not dark SOC) |
| Graph backend | Keep **NetworkX** via `core/`; Neo4j not required for web |
| Data isolation | Web uses `web_data/` + `forensics_web.db` only |

## Information architecture (web)

Primary nav (max early):

1. **Overview** — case status, import CTA, top findings  
2. **Timeline** — single chronological activity feed  
3. **Connections** — evidence graph (Simple by default)

Secondary:

- **Findings** — unified “needs attention” + activity stories  
- **Integrity** — preserved-file fingerprint checks  
- **Settings** — paths / about

Renames vs desktop:

- “Suspicious” / “Needs attention” → **Findings**  
- “Incident Summary” → **Activity stories** (under Findings)  
- “Offline Evidence (Advanced)” → **Import evidence** wizard  

## Repo layout

```text
api/                 # FastAPI; wraps core/
web/                 # React + Vite light UI
web_data/            # Web-only DB, evidence, graphs (gitignored contents)
docs/webapp/         # Webapp planning docs
core/                # Shared forensic pipeline (unchanged ownership)
gui/                 # Desktop only
```

## Exit criteria (Phase 0)

- [x] Branch `feature/webapp` created  
- [x] `api/` + `web/` + `web_data/` + docs present  
- [x] Separate web data paths configured  
- [x] OpenAPI contract draft published  
- [x] Light design tokens defined  
- [x] Root README roadmap updated  

Next: **Phase 1** — Cases CRUD, upload, analysis jobs, read APIs.
