# Phase 1–2 status

Branch: `feature/webapp`

## Phase 1 (API) — done

- Web DB: `web_data/forensics_web.db` via `api/db.py`
- Cases CRUD
- Evidence upload into `web_data/evidence/`
- Analysis jobs (background thread) + poll
- Events, findings, graph, integrity read/verify APIs
- Plain-language DTOs (`api/plain_language.py`)
- Core: optional `evidence_root`; `analyze_preserved_artifact`; Qt lazy-import for offline worker

## Phase 2 (UI) — done

- Home: case list
- New investigation form
- Case Overview: stats, import + analyze, top findings
- Case shell nav (Timeline/Connections/Findings/Integrity placeholders)

## Check commands

See root reply / `api/README.md` and `web/README.md`.
