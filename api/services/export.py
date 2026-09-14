"""Case export (Markdown / HTML) — Phase 5."""

from __future__ import annotations

import html
from datetime import datetime, timezone
from typing import Literal

from sqlalchemy.orm import Session

from api.plain_language import event_headline
from api.services.analysis import load_analysis_snapshot
from core.database.models import Case, EvidenceArtifact, ForensicEvent


def build_case_export(db: Session, case: Case, fmt: Literal["markdown", "html"] = "markdown") -> str:
    snapshot = load_analysis_snapshot(case.id) or {}
    evidence = (
        db.query(EvidenceArtifact)
        .filter(EvidenceArtifact.case_id == case.id)
        .order_by(EvidenceArtifact.collection_timestamp.asc())
        .all()
    )
    events = (
        db.query(ForensicEvent)
        .filter(ForensicEvent.case_id == case.id)
        .order_by(ForensicEvent.timestamp.asc())
        .limit(200)
        .all()
    )
    findings = snapshot.get("findings") or []
    stories = snapshot.get("stories") or []
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    if fmt == "html":
        return _as_html(case, generated, evidence, events, findings, stories, snapshot)
    return _as_markdown(case, generated, evidence, events, findings, stories, snapshot)


def _as_markdown(case, generated, evidence, events, findings, stories, snapshot) -> str:
    lines = [
        f"# Case report: {case.name}",
        "",
        f"_Generated {generated}_",
        "",
        case.description or "_No description_",
        "",
        "## Summary",
        "",
        f"- Evidence files: **{len(evidence)}**",
        f"- Events (showing up to 200): **{len(events)}**",
        f"- Findings: **{len(findings)}**",
        f"- Activity stories: **{len(stories)}**",
        f"- Relationships: **{snapshot.get('relationship_count', 0)}**",
        "",
        "## Evidence integrity",
        "",
    ]
    if not evidence:
        lines.append("_No evidence imported._")
    else:
        for a in evidence:
            lines.append(
                f"- **{a.filename}** — {a.integrity_status or 'PENDING'} — `{a.sha256_hash[:16]}…`"
            )
    lines.extend(["", "## Findings", ""])
    if not findings:
        lines.append("_No findings._")
    else:
        for f in findings:
            lines.append(f"- **{f.get('headline')}** ({f.get('severity_label')})")
            if f.get("detail"):
                lines.append(f"  - {f.get('detail')}")
    lines.extend(["", "## Activity stories", ""])
    if not stories:
        lines.append("_No activity stories._")
    else:
        for s in stories:
            lines.append(f"- **{s.get('headline')}**")
            if s.get("detail"):
                lines.append(f"  - {s.get('detail')}")
    lines.extend(["", "## Timeline (excerpt)", ""])
    if not events:
        lines.append("_No events._")
    else:
        for ev in events:
            ts = ev.timestamp.isoformat() if ev.timestamp else "unknown"
            lines.append(f"- `{ts}` — {event_headline(ev)}")
    lines.extend(["", "---", "", "_Digital Forensics web export (feature/webapp). Authorized use only._", ""])
    return "\n".join(lines)


def _as_html(case, generated, evidence, events, findings, stories, snapshot) -> str:
    def esc(v) -> str:
        return html.escape(str(v) if v is not None else "")

    parts = [
        "<!DOCTYPE html><html><head><meta charset='utf-8'/>",
        f"<title>Case report: {esc(case.name)}</title>",
        "<style>body{font-family:system-ui,sans-serif;max-width:960px;margin:2rem auto;padding:0 1rem;color:#0f1f33}"
        "h1,h2{font-family:Georgia,serif}code{font-size:0.9em}.muted{color:#5a6f8a}</style>",
        "</head><body>",
        f"<h1>Case report: {esc(case.name)}</h1>",
        f"<p class='muted'>Generated {esc(generated)}</p>",
        f"<p>{esc(case.description or 'No description')}</p>",
        "<h2>Summary</h2><ul>",
        f"<li>Evidence files: <strong>{len(evidence)}</strong></li>",
        f"<li>Events: <strong>{len(events)}</strong></li>",
        f"<li>Findings: <strong>{len(findings)}</strong></li>",
        f"<li>Activity stories: <strong>{len(stories)}</strong></li>",
        f"<li>Relationships: <strong>{esc(snapshot.get('relationship_count', 0))}</strong></li>",
        "</ul><h2>Evidence</h2><ul>",
    ]
    if not evidence:
        parts.append("<li class='muted'>No evidence imported.</li>")
    else:
        for a in evidence:
            parts.append(
                f"<li><strong>{esc(a.filename)}</strong> — {esc(a.integrity_status)} — "
                f"<code>{esc(a.sha256_hash[:16])}…</code></li>"
            )
    parts.append("</ul><h2>Findings</h2><ul>")
    if not findings:
        parts.append("<li class='muted'>No findings.</li>")
    else:
        for f in findings:
            parts.append(
                f"<li><strong>{esc(f.get('headline'))}</strong> ({esc(f.get('severity_label'))})"
                f"<div class='muted'>{esc(f.get('detail') or '')}</div></li>"
            )
    parts.append("</ul><h2>Timeline</h2><ul>")
    if not events:
        parts.append("<li class='muted'>No events.</li>")
    else:
        for ev in events:
            ts = ev.timestamp.isoformat() if ev.timestamp else "unknown"
            parts.append(f"<li><code>{esc(ts)}</code> — {esc(event_headline(ev))}</li>")
    parts.append("</ul><hr/><p class='muted'>Digital Forensics web export. Authorized use only.</p></body></html>")
    return "".join(parts)
