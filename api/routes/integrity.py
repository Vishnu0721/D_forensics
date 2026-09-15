"""Integrity list + verify (Phase F) — human status first."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.db import get_db
from api.plain_language import INTEGRITY_LABELS, INTEGRITY_LEGEND
from api.schemas import IntegrityResponse, IntegrityRow
from api.serializers import get_case_or_404
from core.database.models import EvidenceArtifact
from core.services.integrity import verify_all_evidence

router = APIRouter(prefix="/api/v1/cases/{case_id}/integrity", tags=["integrity"])


def _rows(db: Session, case_id: str) -> list[IntegrityRow]:
    artifacts = (
        db.query(EvidenceArtifact)
        .filter(EvidenceArtifact.case_id == case_id)
        .order_by(EvidenceArtifact.collection_timestamp.desc())
        .all()
    )
    rows: list[IntegrityRow] = []
    for a in artifacts:
        status = a.integrity_status or "PENDING"
        rows.append(
            IntegrityRow(
                evidence_id=a.id,
                what=a.filename,
                sha256_hash=a.sha256_hash,
                status=status,
                status_label=INTEGRITY_LABELS.get(status, status),
                collected_at=a.collection_timestamp,
            )
        )
    return rows


@router.get("", response_model=IntegrityResponse)
def list_integrity(case_id: str, db: Session = Depends(get_db)):
    get_case_or_404(db, case_id)
    return IntegrityResponse(items=_rows(db, case_id), legend=INTEGRITY_LEGEND)


@router.post("", response_model=IntegrityResponse)
def verify_integrity(case_id: str, db: Session = Depends(get_db)):
    get_case_or_404(db, case_id)
    verify_all_evidence(db, case_id)
    return IntegrityResponse(items=_rows(db, case_id), legend=INTEGRITY_LEGEND)
