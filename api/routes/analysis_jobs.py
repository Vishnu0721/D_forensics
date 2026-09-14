"""Analysis jobs."""

from __future__ import annotations

import threading

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.db import get_db, get_session_factory
from api.jobs import job_store
from api.schemas import AnalyzeRequest, JobStatus
from api.serializers import get_case_or_404
from api.services.analysis import run_case_analysis

router = APIRouter(tags=["jobs"])


def _job_to_schema(job) -> JobStatus:
    return JobStatus(
        id=job.id,
        case_id=job.case_id,
        status=job.status,  # type: ignore[arg-type]
        progress=job.progress,
        message=job.message,
        error=job.error,
        result_summary=job.result_summary,
    )


def _run_job(job_id: str, case_id: str, evidence_ids: list[str] | None) -> None:
    SessionLocal = get_session_factory()
    db = SessionLocal()

    def progress(msg: str) -> None:
        job_store.update(job_id, status="running", message=msg, progress=min(0.9, (job_store.get(job_id).progress or 0) + 0.05))

    try:
        job_store.update(job_id, status="running", message="Starting analysis", progress=0.05)
        snapshot = run_case_analysis(db, case_id, evidence_ids=evidence_ids, progress_cb=progress)
        summary = {
            "events_stored": snapshot.get("events_stored"),
            "relationship_count": snapshot.get("relationship_count"),
            "finding_count": len(snapshot.get("findings") or []),
            "story_count": len(snapshot.get("stories") or []),
            "classification_counts": snapshot.get("classification_counts"),
            "analyzed_at": snapshot.get("analyzed_at"),
        }
        job_store.update(
            job_id,
            status="completed",
            message="Analysis complete",
            progress=1.0,
            result_summary=summary,
            error=None,
        )
    except Exception as exc:
        job_store.update(
            job_id,
            status="failed",
            message="Analysis failed",
            error=str(exc),
            progress=1.0,
        )
    finally:
        db.close()


@router.post("/api/v1/cases/{case_id}/analyze", response_model=JobStatus, status_code=202)
def start_analysis(
    case_id: str,
    body: AnalyzeRequest | None = None,
    db: Session = Depends(get_db),
):
    get_case_or_404(db, case_id)
    evidence_ids = body.evidence_ids if body else None
    job = job_store.create(case_id)
    thread = threading.Thread(
        target=_run_job,
        args=(job.id, case_id, evidence_ids),
        daemon=True,
    )
    thread.start()
    return _job_to_schema(job)


@router.get("/api/v1/jobs/{job_id}", response_model=JobStatus)
def get_job(job_id: str):
    job = job_store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return _job_to_schema(job)
