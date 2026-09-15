"""Delete a web investigation and its web_data artifacts (not desktop DB)."""

from __future__ import annotations

import shutil
from pathlib import Path

from sqlalchemy.orm import Session

from api.config import get_settings
from api.services.analysis import case_analysis_dir, graph_for_case
from api.services.live_monitor import live_monitor
from core.database.models import AuditLog, Case, EvidenceArtifact, ForensicEvent


def delete_case_cascade(db: Session, case_id: str) -> None:
    """Remove case rows and web_data files. Stops live watch if this case is active."""
    live = live_monitor.status()
    if live.get("running") and live.get("case_id") == case_id:
        live_monitor.stop()

    db.query(ForensicEvent).filter(ForensicEvent.case_id == case_id).delete(
        synchronize_session=False
    )
    db.query(EvidenceArtifact).filter(EvidenceArtifact.case_id == case_id).delete(
        synchronize_session=False
    )
    db.query(AuditLog).filter(AuditLog.object_id == case_id).delete(synchronize_session=False)
    db.query(Case).filter(Case.id == case_id).delete(synchronize_session=False)
    db.commit()

    settings = get_settings()
    evidence_dir = settings.evidence_dir / case_id
    if evidence_dir.exists():
        shutil.rmtree(evidence_dir, ignore_errors=True)

    analysis_dir = case_analysis_dir(case_id)
    if analysis_dir.exists():
        shutil.rmtree(analysis_dir, ignore_errors=True)

    try:
        graph = graph_for_case(case_id)
        graph_path = Path(graph.file_path)
        if graph_path.exists():
            graph_path.unlink(missing_ok=True)
    except Exception:
        pass
