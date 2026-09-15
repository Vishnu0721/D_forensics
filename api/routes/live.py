"""Live monitoring control API (Phase H) — web_data only."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.db import get_db
from api.jobs import job_store
from api.serializers import get_case_or_404
from api.services.live_monitor import LiveMonitorError, live_monitor

router = APIRouter(prefix="/api/v1", tags=["live"])


@router.get("/live/status")
def live_status():
    return live_monitor.status()


@router.get("/cases/{case_id}/live")
def case_live_status(case_id: str, db: Session = Depends(get_db)):
    get_case_or_404(db, case_id)
    status = live_monitor.status()
    return {
        **status,
        "this_case_active": bool(status.get("running") and status.get("case_id") == case_id),
    }


@router.post("/cases/{case_id}/live/start")
def start_live(case_id: str, db: Session = Depends(get_db)):
    get_case_or_404(db, case_id)
    active = job_store.active_for_case(case_id)
    if active and active.status in ("queued", "running"):
        raise HTTPException(
            status_code=409,
            detail="Cannot start live monitoring while an analysis job is running.",
        )
    try:
        return live_monitor.start(case_id)
    except LiveMonitorError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/cases/{case_id}/live/stop")
def stop_live(case_id: str, db: Session = Depends(get_db)):
    get_case_or_404(db, case_id)
    status = live_monitor.status()
    if status.get("running") and status.get("case_id") not in (None, case_id):
        raise HTTPException(
            status_code=409,
            detail=f"Live monitoring is active for a different case ({status.get('case_id')}).",
        )
    return live_monitor.stop()
