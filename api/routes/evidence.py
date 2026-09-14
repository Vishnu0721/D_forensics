"""Evidence upload / list."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from api.config import get_settings
from api.db import get_db
from api.schemas import EvidenceSummary
from api.serializers import evidence_summary, get_case_or_404
from core.database.models import EvidenceArtifact
from core.services.ingestion import ingest_preserved_evidence

router = APIRouter(prefix="/api/v1/cases/{case_id}/evidence", tags=["evidence"])


@router.get("", response_model=dict)
def list_evidence(case_id: str, db: Session = Depends(get_db)):
    get_case_or_404(db, case_id)
    items = (
        db.query(EvidenceArtifact)
        .filter(EvidenceArtifact.case_id == case_id)
        .order_by(EvidenceArtifact.collection_timestamp.desc())
        .all()
    )
    return {"items": [evidence_summary(a) for a in items]}


@router.post("", response_model=EvidenceSummary, status_code=201)
async def upload_evidence(
    case_id: str,
    file: UploadFile = File(...),
    source_hint: str | None = Form(default=None),
    db: Session = Depends(get_db),
):
    get_case_or_404(db, case_id)
    settings = get_settings()
    suffix = Path(file.filename or "upload.bin").suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp_path = Path(tmp.name)
        shutil.copyfileobj(file.file, tmp)

    try:
        # Keep original filename for investigator readability
        named = tmp_path.with_name(file.filename or tmp_path.name)
        if named != tmp_path:
            shutil.copy2(tmp_path, named)
            upload_path = named
        else:
            upload_path = tmp_path

        source_type = (source_hint or "offline_report").strip() or "offline_report"
        artifact = ingest_preserved_evidence(
            db=db,
            case_id=case_id,
            source_file_path=str(upload_path),
            source_type=source_type,
            actor="web_investigator",
            evidence_root=str(settings.evidence_dir),
        )
        return evidence_summary(artifact)
    finally:
        for path in {tmp_path, tmp_path.with_name(file.filename or tmp_path.name)}:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
