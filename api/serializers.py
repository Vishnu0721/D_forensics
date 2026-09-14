"""Shared serializers / lookups for routes."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session

from api.plain_language import INTEGRITY_LABELS
from api.schemas import CaseSummary, EvidenceSummary
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
    return CaseSummary(
        id=case.id,
        name=case.name,
        description=case.description,
        mode="imported",
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
