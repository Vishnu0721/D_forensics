"""Human-readable integrity table helpers."""
from __future__ import annotations

from core.database.models import EvidenceArtifact, ForensicEvent

STATUS_LABELS = {
    "VALID": "Unchanged",
    "MODIFIED": "Changed on disk",
    "UNVERIFIABLE": "File missing",
    "UNVERIFIED": "Not checked yet",
}

STATUS_HELP = {
    "VALID": "The saved copy still matches its fingerprint.",
    "MODIFIED": "The file on disk no longer matches — do not trust it alone.",
    "UNVERIFIABLE": "The original file path cannot be read.",
    "UNVERIFIED": "Click Verify Integrity or stop monitoring to re-check.",
}


def human_source_label(artifact: EvidenceArtifact, db) -> str:
    st = (artifact.source_type or "unknown").replace("_", " ")
    try:
        event = (
            db.query(ForensicEvent)
            .filter(ForensicEvent.evidence_id == artifact.id)
            .first()
        )
    except Exception:
        event = None
    if event:
        if event.source_type == "network" and event.process:
            return f"Network · {event.process}"
        if event.source_type == "process" and event.process:
            return f"Program · {event.process}"
        if event.source_type == "filesystem" and (event.file or event.path):
            name = event.file or (event.path.replace("/", "\\").split("\\")[-1] if event.path else "")
            return f"File · {name}"
    if st == "network":
        return "Network connection"
    if st == "filesystem":
        return "File change"
    if st == "process":
        return "Program activity"
    return st.title()


def map_status_display(status: str) -> str:
    return STATUS_LABELS.get(status, status)
