"""Shared serializers / lookups for routes."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session

from api.case_meta import load_case_meta
from api.plain_language import INTEGRITY_LABELS
from api.schemas import CaseSummary, EvidenceSummary
from api.services.live_monitor import live_monitor
from core.database.models import Case, EvidenceArtifact, ForensicEvent


def get_case_or_404(db: Session, case_id: str) -> Case:
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return case


def case_summary(db: Session, case: Case) -> CaseSummary:
    evidence_count = (
        db.query(EvidenceArtifact).filter(EvidenceArtifact.case_id == case.id).count()
    )
    event_count = db.query(ForensicEvent).filter(ForensicEvent.case_id == case.id).count()
    meta = load_case_meta(case.id)
    live = live_monitor.status()
    mode = "live" if (live.get("running") and live.get("case_id") == case.id) else meta.get("mode", "imported")
    if mode not in ("imported", "live"):
        mode = "imported"
    return CaseSummary(
        id=case.id,
        name=case.name,
        description=case.description,
        mode=mode,  # type: ignore[arg-type]
        created_at=case.created_at,
        evidence_count=evidence_count,
        event_count=event_count,
    )


def evidence_summary(artifact: EvidenceArtifact) -> EvidenceSummary:
    status = artifact.integrity_status or "PENDING"
    return EvidenceSummary(
        id=artifact.id,
        filename=artifact.filename,
        source_type=artifact.source_type,
        sha256_hash=artifact.sha256_hash,
        file_size=artifact.file_size,
        integrity_status=status,
        status_label=INTEGRITY_LABELS.get(status, status),
        created_at=artifact.collection_timestamp,
    )
