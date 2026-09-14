"""Case CRUD and overview."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.db import get_db
from api.schemas import CaseCreate, CaseDetail, CaseSummary, CaseUpdate, FindingSummary
from api.serializers import case_summary, get_case_or_404
from api.services.analysis import load_analysis_snapshot
from core.database.models import Case

router = APIRouter(prefix="/api/v1/cases", tags=["cases"])


@router.get("", response_model=dict)
def list_cases(db: Session = Depends(get_db)):
    cases = db.query(Case).order_by(Case.created_at.desc()).all()
    return {"items": [case_summary(db, c) for c in cases]}


@router.post("", response_model=CaseSummary, status_code=201)
def create_case(body: CaseCreate, db: Session = Depends(get_db)):
    case = Case(name=body.name.strip(), description=(body.description or "").strip() or None)
    db.add(case)
    db.commit()
    db.refresh(case)
    return case_summary(db, case)


@router.get("/{case_id}", response_model=CaseDetail)
def get_case(case_id: str, db: Session = Depends(get_db)):
    case = get_case_or_404(db, case_id)
    base = case_summary(db, case)
    snapshot = load_analysis_snapshot(case_id)
    last_analysis_at = None
    top_findings: list[FindingSummary] = []
    relationship_count = 0
    finding_count = 0
    story_count = 0
    if snapshot:
        raw_ts = snapshot.get("analyzed_at")
        if raw_ts:
            try:
                last_analysis_at = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
            except ValueError:
                last_analysis_at = None
        findings = snapshot.get("findings") or []
        stories = snapshot.get("stories") or []
        finding_count = len(findings)
        story_count = len(stories)
        relationship_count = int(snapshot.get("relationship_count") or 0)
        combined = findings + stories
        top_findings = [FindingSummary(**item) for item in combined[:3]]

    return CaseDetail(
        **base.model_dump(),
        last_analysis_at=last_analysis_at,
        top_findings=top_findings,
        relationship_count=relationship_count,
        finding_count=finding_count,
        story_count=story_count,
    )


@router.patch("/{case_id}", response_model=CaseSummary)
def update_case(case_id: str, body: CaseUpdate, db: Session = Depends(get_db)):
    case = get_case_or_404(db, case_id)
    if body.name is not None:
        case.name = body.name.strip()
    if body.description is not None:
        case.description = body.description.strip() or None
    db.commit()
    db.refresh(case)
    return case_summary(db, case)
