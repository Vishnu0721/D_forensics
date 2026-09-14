# Phases 5–7 (feature/webapp)

Branch: **`feature/webapp` only**. Web data stays in `web_data/` — never writes desktop `forensics.db` / `data/`.

## Phase 5 — Polish

- Guided tour (Home / Settings replay)
- Case export Markdown + HTML (`/api/v1/cases/{id}/export`)
- Clearer empty states and Overview CTAs

## Phase 6 — Live agent (web-native)

- Threaded process + network collectors in `api/services/live_monitor.py`
- Start/stop/status API — **does not** use desktop Qt `MonitoringManager`
- Writes live JSON under `web_data/evidence/<case>/live/`
- UI: Overview live controls + polling while LIVE
- Mutual exclusion: live ↔ analysis jobs

## Phase 7 — Hardening

- Per-case analysis job lock + bounded job history
- Graph node/edge caps (250 / 500)
- Expanded smoke: `api/smoke_phase5_7.py`
- `psutil` in `api/requirements.txt`; optional `python-evtx` documented

## Verify

```powershell
cd D:\D_forensics
$env:PYTHONPATH = "D:\D_forensics"
python api/smoke_phase1.py
python api/smoke_phase5_7.py
```
