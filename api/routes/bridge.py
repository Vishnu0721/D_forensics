"""Phase I — desktop evidence folder bridge (copy into web_data)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.db import get_db
from api.schemas import DesktopBridgeImportRequest
from api.serializers import evidence_summary, get_case_or_404
from api.services.bridge import import_desktop_folder, scan_desktop_evidence
from core.database.models import EvidenceArtifact

router = APIRouter(prefix="/api/v1", tags=["bridge"])


@router.get("/bridge/desktop")
def list_desktop_folders():
    """List folders under data/evidence/ (desktop output). Does not open forensics.db."""
    return {"items": scan_desktop_evidence()}


@router.post("/cases/{case_id}/bridge/desktop")
def import_from_desktop(
    case_id: str,
    body: DesktopBridgeImportRequest,
    db: Session = Depends(get_db),
):
    get_case_or_404(db, case_id)
    try:
        result = import_desktop_folder(db, case_id, body.source_dir)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Import failed: {exc}") from exc

    artifacts = (
        db.query(EvidenceArtifact)
        .filter(EvidenceArtifact.case_id == case_id)
        .order_by(EvidenceArtifact.collection_timestamp.desc())
        .limit(20)
        .all()
    )
    return {
        **result,
        "recent_evidence": [evidence_summary(a) for a in artifacts],
    }
