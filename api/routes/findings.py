"""Findings and activity stories (Phase F)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.db import get_db
from api.schemas import FindingSummary, FindingsResponse
from api.serializers import get_case_or_404
from api.services.analysis import load_analysis_snapshot

router = APIRouter(prefix="/api/v1/cases/{case_id}/findings", tags=["findings"])


@router.get("", response_model=FindingsResponse)
def list_findings(case_id: str, db: Session = Depends(get_db)):
    get_case_or_404(db, case_id)
    snapshot = load_analysis_snapshot(case_id) or {}
    findings = [FindingSummary(**item) for item in (snapshot.get("findings") or [])]
    stories = [FindingSummary(**item) for item in (snapshot.get("stories") or [])]
    return FindingsResponse(findings=findings, stories=stories)
