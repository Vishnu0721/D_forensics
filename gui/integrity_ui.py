"""Human-readable integrity table helpers."""
from __future__ import annotations

from PySide6.QtCore import QObject, QThread, Signal, Slot

from core.database import SessionLocal
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

_NOT_PREFETCHED = object()


def human_source_label(artifact: EvidenceArtifact, db, event=_NOT_PREFETCHED) -> str:
    st = (artifact.source_type or "unknown").replace("_", " ")
    if event is _NOT_PREFETCHED:
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


def first_events_by_evidence(db, evidence_ids) -> dict:
    """One query (chunked) instead of one query per table row."""
    found = {}
    ids = list(evidence_ids)
    for start in range(0, len(ids), 500):
        chunk = ids[start:start + 500]
        for ev in db.query(ForensicEvent).filter(ForensicEvent.evidence_id.in_(chunk)):
            found.setdefault(ev.evidence_id, ev)
    return found


def map_status_display(status: str) -> str:
    return STATUS_LABELS.get(status, status)


class IntegrityCheckWorker(QObject):
    """Re-hashes evidence files off the UI thread (can take minutes for large cases)."""

    finished = Signal(list)
    failed = Signal(str)

    def __init__(self, case_id: str):
        super().__init__()
        self.case_id = case_id

    @Slot()
    def run(self):
        from core.services.integrity import verify_all_evidence

        db = SessionLocal()
        try:
            thread = QThread.currentThread()
            results = verify_all_evidence(
                db, self.case_id, should_stop=thread.isInterruptionRequested
            )
            self.finished.emit(results)
        except Exception as e:
            self.failed.emit(str(e))
        finally:
            db.close()
