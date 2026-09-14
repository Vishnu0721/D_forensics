# Phase 3 status

Branch: `feature/webapp`

## Done

- **Import wizard** (`/cases/:id/import`) — choose file → confirm type → analyze → done
- **Timeline** — single chronological feed, filters, event drawer with technical details
- **Findings** — Needs attention + Activity stories, links into Timeline via `evidence=` filter
- Events API: optional `evidence_id` query param

## Manual check

1. Start API + `npm run dev`
2. Open a case → Import evidence → use `web/fixtures/sample_evidence.json`
3. Open Timeline — click an event for the drawer
4. Open Findings — follow “View related activity on Timeline”
