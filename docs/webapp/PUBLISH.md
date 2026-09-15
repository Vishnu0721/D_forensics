# Publish polish (P1–P7)

Status: **implemented** (2026-09-15)  
Builds on [PHASE_A.md](PHASE_A.md) and [PHASE_B_J.md](PHASE_B_J.md).

## Framing (P0)

| Item | Choice |
|------|--------|
| Audience | Academic / portfolio / classmates |
| Product | **Digital Forensics** |
| Tagline | Import evidence. Analyze. Follow the story. |
| UI noun | Investigation |
| Not claiming | Multi-user cloud DFIR / enterprise SOC |

## What shipped

| Phase | Focus | Delivered |
|-------|--------|-----------|
| **P1** | Identity | Tagline on Home, favicon, clean title, stronger empty state |
| **P2** | Prototype tells | Desktop capture copy (no “Phase I”), About from `/meta`, version `0.3.0` |
| **P3** | Investigation loop | Findings → Timeline `?event=`, Import promoted when empty, sample load, Load more |
| **P4** | Trust | `/health` hides paths by default, live confirm, Delete investigation, API banner |
| **P5** | Polish | Graph colors from CSS tokens, export letterhead, Integrity loading |
| **P6** | Docs | This file + README pointers |
| **P7** | Labels only | Plain / Formal label mode in Settings |

## Explicitly deferred (P7 remainder)

- User login / multi-user auth  
- Public cloud deploy  
- Full mobile redesign  
- Rewriting `core/` collectors  

## Desktop mapping (unchanged)

Web screens still mirror desktop concepts: Import ≈ Offline Evidence, Timeline ≈ Activity, Connections ≈ Evidence Graph, Findings ≈ Needs attention + Incident Summary, Integrity ≈ Evidence Integrity, Live ≈ Start Monitoring.

## Verify

```powershell
cd D:\D_forensics
$env:PYTHONPATH = (Get-Location).Path
python api/smoke_phase_b_j.py
```

Health should report `"phase": "P7"`, `"version": "0.3.0"`, and **no** `database_url` unless `FORENSICS_WEB_EXPOSE_PATHS=true`.
