"""Timeline / event read APIs (Phase D)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from api.db import get_db
from api.plain_language import (
    event_detail,
    event_headline,
    severity_for_classification,
    technical_fields,
)
from api.schemas import EventDetail, EventPage, EventSummary
from api.serializers import get_case_or_404
from api.services.analysis import load_analysis_snapshot
from core.database.models import ForensicEvent

router = APIRouter(prefix="/api/v1/cases/{case_id}/events", tags=["events"])

FILTER_MAP = {
    "all": None,
    "user": "USER_ACTIVITY",
    "background": "BACKGROUND_ACTIVITY",
    "findings": "SUSPICIOUS_ACTIVITY",
    "linked": "CORRELATED_ACTIVITY",
    "unclear": "UNKNOWN",
}


@router.get("", response_model=EventPage)
def list_events(
    case_id: str,
    filter: str = Query(default="all"),
    evidence_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    get_case_or_404(db, case_id)
    snapshot = load_analysis_snapshot(case_id) or {}
    classifications = snapshot.get("event_classifications") or {}

    query = db.query(ForensicEvent).filter(ForensicEvent.case_id == case_id)
    if evidence_id:
        query = query.filter(ForensicEvent.evidence_id == evidence_id)
    events = query.order_by(ForensicEvent.timestamp.asc()).all()

    if filter not in FILTER_MAP:
        raise HTTPException(status_code=400, detail=f"Unknown filter: {filter}")
    wanted = FILTER_MAP[filter]

    items: list[EventSummary] = []
    for ev in events:
        cls = classifications.get(ev.id, "UNKNOWN")
        if wanted and cls != wanted:
            continue
        items.append(
            EventSummary(
                id=ev.id,
                timestamp=ev.timestamp,
                source_type=ev.source_type or "",
                event_type=ev.event_type or "",
                classification=cls,
                headline=event_headline(ev),
                detail=event_detail(ev),
                severity_label=severity_for_classification(cls),
            )
        )

    total = len(items)
    return EventPage(total=total, items=items[offset : offset + limit])


@router.get("/{event_id}", response_model=EventDetail)
def get_event(case_id: str, event_id: str, db: Session = Depends(get_db)):
    get_case_or_404(db, case_id)
    ev = (
        db.query(ForensicEvent)
        .filter(ForensicEvent.case_id == case_id, ForensicEvent.id == event_id)
        .first()
    )
    if not ev:
        raise HTTPException(status_code=404, detail="Event not found")
    snapshot = load_analysis_snapshot(case_id) or {}
    cls = (snapshot.get("event_classifications") or {}).get(ev.id, "UNKNOWN")
    return EventDetail(
        id=ev.id,
        timestamp=ev.timestamp,
        source_type=ev.source_type or "",
        event_type=ev.event_type or "",
        classification=cls,
        headline=event_headline(ev),
        detail=event_detail(ev),
        severity_label=severity_for_classification(cls),
        evidence_id=ev.evidence_id,
        technical=technical_fields(ev),
    )
