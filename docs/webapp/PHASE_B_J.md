# Phases B–J — Implementation notes

Branch: `feature/webapp`  
Builds on [PHASE_A.md](PHASE_A.md). Desktop PySide6 app stays for capture; web reuses `core/` and stores only under `web_data/`.

| Phase | Focus | Delivered |
|-------|--------|-----------|
| **B** | Case shell & home | Cases API, Home, New investigation, CaseLayout nav |
| **C** | Import & analyze | Upload evidence, async jobs, `analyze_preserved_artifact` pipeline |
| **D** | Timeline | Single chronological feed + event drawer (technical details optional) |
| **E** | Connections | Graph Simple/Detailed via NetworkX → Cytoscape |
| **F** | Findings & Integrity | Needs a look + activity stories; human integrity labels first |
| **G** | Overview & export | `next_step`, plain cards, Markdown/HTML export |
| **H** | Live watch | Optional process+network agent → `web_data/` (not Qt MonitoringManager) |
| **I** | Desktop bridge | Scan `data/evidence/`, copy files into web case (no shared DB) |
| **J** | Hardening | Job lock, graph caps, smoke `api/smoke_phase_b_j.py`, docs |

## Desktop mapping

| Desktop | Web |
|---------|-----|
| Start/Stop Monitoring | Overview live Start/Stop (optional) |
| Offline Evidence | Import + desktop bridge |
| Activity stream | Timeline (one list) |
| Evidence Graph | Connections |
| Needs attention / Incident Summary | Findings |
| Evidence Integrity | Integrity |
| Stats ribbon | Overview cards (Saved records / Activity / Links / Needs a look) |

## Core touch

- `core/services/correlation.py` — Qt `CorrelationWorker` is lazy so web can import `correlate_events` without PySide6.

## Verify

See root README / `api/README.md` / `web/README.md` for commands.
