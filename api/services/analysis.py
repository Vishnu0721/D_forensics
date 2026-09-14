"""Case analysis helpers: run pipeline and persist snapshot under web_data."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from sqlalchemy.orm import Session

from api.config import get_settings
from api.plain_language import finding_from_suspicious, story_from_incident
from core.database.models import EvidenceArtifact, ForensicEvent
from core.services.classification import ClassificationEngine
from core.services.graph import EvidenceGraph
from core.services.offline_analysis import analyze_preserved_artifact


def case_analysis_dir(case_id: str) -> Path:
    path = get_settings().data_root / "cases" / case_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def analysis_snapshot_path(case_id: str) -> Path:
    return case_analysis_dir(case_id) / "last_analysis.json"


def graph_for_case(case_id: str) -> EvidenceGraph:
    settings = get_settings()
    return EvidenceGraph(case_id, storage_dir=str(settings.graphs_dir))


def load_analysis_snapshot(case_id: str) -> Optional[dict[str, Any]]:
    path = analysis_snapshot_path(case_id)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def save_analysis_snapshot(case_id: str, payload: dict[str, Any]) -> None:
    path = analysis_snapshot_path(case_id)
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


def build_snapshot(
    case_id: str,
    *,
    suspicious: list[dict],
    incidents: list[dict],
    relationships: list[dict],
    classification_counts: dict,
    events_stored: int,
    evidence_ids: list[str],
) -> dict[str, Any]:
    findings = [finding_from_suspicious(item, i) for i, item in enumerate(suspicious)]
    stories = [story_from_incident(item, i) for i, item in enumerate(incidents)]
    return {
        "case_id": case_id,
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
        "evidence_ids": evidence_ids,
        "events_stored": events_stored,
        "relationship_count": len(relationships),
        "classification_counts": classification_counts,
        "findings": findings,
        "stories": stories,
        "raw_suspicious": suspicious,
        "raw_incidents": incidents,
    }


def run_case_analysis(
    db: Session,
    case_id: str,
    evidence_ids: Optional[list[str]] = None,
    progress_cb=None,
) -> dict[str, Any]:
    """Analyze selected (or all) preserved evidence for a case."""
    settings = get_settings()
    query = db.query(EvidenceArtifact).filter(EvidenceArtifact.case_id == case_id)
    if evidence_ids:
        query = query.filter(EvidenceArtifact.id.in_(evidence_ids))
    artifacts = query.order_by(EvidenceArtifact.collection_timestamp.asc()).all()
    if not artifacts:
        raise ValueError("No evidence artifacts to analyze for this case")

    # Remove prior events for selected evidence so re-analyze is idempotent
    selected_ids = [a.id for a in artifacts]
    db.query(ForensicEvent).filter(ForensicEvent.evidence_id.in_(selected_ids)).delete(
        synchronize_session=False
    )
    db.commit()

    graph = graph_for_case(case_id)
    # Fresh graph for this analysis pass
    graph.graph.clear()
    graph.save()

    all_suspicious: list[dict] = []
    all_incidents: list[dict] = []
    all_relationships: list[dict] = []
    classification_counts = {
        "USER_ACTIVITY": 0,
        "BACKGROUND_ACTIVITY": 0,
        "SUSPICIOUS_ACTIVITY": 0,
        "CORRELATED_ACTIVITY": 0,
        "UNKNOWN": 0,
    }
    events_stored = 0

    for artifact in artifacts:
        if progress_cb:
            progress_cb(f"Analyzing {artifact.filename}...")
        result = analyze_preserved_artifact(
            db=db,
            case_id=case_id,
            evidence=artifact,
            graph_db=graph,
            actor="web_investigator",
            progress_cb=progress_cb,
        )
        if not result.success and result.error_message:
            raise RuntimeError(result.error_message)
        events_stored += result.events_stored
        all_relationships.extend(result.relationships)
        all_suspicious.extend(result.suspicious_activities)
        all_incidents.extend(result.incidents)
        for key, value in result.classification_counts.items():
            classification_counts[key] = classification_counts.get(key, 0) + value

    # Final pass on full graph for coherent findings
    if progress_cb:
        progress_cb("Finalizing findings across case graph...")
    from core.services.suspicious import detect_suspicious_activity
    from core.services.reconstruction import reconstruct_incidents

    snapshot_graph = graph.graph.copy()
    all_suspicious = detect_suspicious_activity(snapshot_graph)
    all_incidents = reconstruct_incidents(snapshot_graph, all_suspicious)

    # Reclassify all case events against final graph
    events = (
        db.query(ForensicEvent)
        .filter(ForensicEvent.case_id == case_id)
        .order_by(ForensicEvent.timestamp.asc())
        .all()
    )
    cls_engine = ClassificationEngine()
    classification_counts = {k: 0 for k in classification_counts}
    event_classifications: dict[str, str] = {}
    for ev in events:
        r = cls_engine.classify_event(ev, snapshot_graph, all_suspicious)
        cls = r["classification"]
        event_classifications[ev.id] = cls
        if cls in classification_counts:
            classification_counts[cls] += 1

    snapshot = build_snapshot(
        case_id,
        suspicious=all_suspicious,
        incidents=all_incidents,
        relationships=all_relationships,
        classification_counts=classification_counts,
        events_stored=events_stored,
        evidence_ids=selected_ids,
    )
    snapshot["event_classifications"] = event_classifications
    snapshot["evidence_root"] = str(settings.evidence_dir)
    save_analysis_snapshot(case_id, snapshot)
    graph.save()
    return snapshot
