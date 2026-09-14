import datetime
from typing import Dict, Any, List, Optional, Callable
from sqlalchemy.orm import Session

from core.database.models import ForensicEvent, EvidenceArtifact
from core.services.ingestion import ingest_preserved_evidence
from core.services.report_parser import parse_report, ParseResult
from core.services.normalization import normalize_records, bulk_store_events
from core.services.correlation import correlate_events
from core.services.graph import EvidenceGraph
from core.services.suspicious import detect_suspicious_activity
from core.services.reconstruction import reconstruct_incidents
from core.services.classification import ClassificationEngine


ProgressCallback = Optional[Callable[[str], None]]


def _make_offline_worker_class():
    """Lazy Qt worker so the web API can import run_offline_analysis without PySide6."""
    from PySide6.QtCore import QObject, Signal, Slot
    from core.database import SessionLocal

    class OfflineAnalysisWorker(QObject):
        progress = Signal(str)
        analysis_complete = Signal(object)
        analysis_error = Signal(str)

        def __init__(self, case_id: str, source_file_path: str, graph_db: EvidenceGraph,
                     actor: str = "investigator", force_source_type: Optional[str] = None):
            super().__init__()
            self.case_id = case_id
            self.source_file_path = source_file_path
            self.graph_db = graph_db
            self.actor = actor
            self.force_source_type = force_source_type

        @Slot()
        def run(self):
            db = SessionLocal()
            try:
                result = run_offline_analysis(
                    db=db,
                    case_id=self.case_id,
                    source_file_path=self.source_file_path,
                    graph_db=self.graph_db,
                    actor=self.actor,
                    force_source_type=self.force_source_type,
                    progress_cb=lambda msg: self.progress.emit(msg),
                )
                if result.evidence:
                    db.refresh(result.evidence)
                db.expunge_all()
                self.analysis_complete.emit(result)
            except Exception as e:
                self.analysis_error.emit(str(e))
            finally:
                db.close()

    return OfflineAnalysisWorker


class _OfflineAnalysisWorkerProxy:
    """Attribute access constructs the real Qt worker class on first use."""

    _cls = None

    def __call__(self, *args, **kwargs):
        if self._cls is None:
            self._cls = _make_offline_worker_class()
        return self._cls(*args, **kwargs)


OfflineAnalysisWorker = _OfflineAnalysisWorkerProxy()


class OfflineAnalysisResult:
    def __init__(self):
        self.success: bool = False
        self.error_message: Optional[str] = None

        self.evidence: Optional[EvidenceArtifact] = None
        self.parse_result: Optional[ParseResult] = None

        self.events_extracted: int = 0
        self.events_stored: int = 0

        self.suspicious_activities: List[Dict[str, Any]] = []
        self.relationships: List[Dict[str, Any]] = []
        self.incidents: List[Dict[str, Any]] = []

        self.classification_counts: Dict[str, int] = {
            "USER_ACTIVITY": 0,
            "BACKGROUND_ACTIVITY": 0,
            "SUSPICIOUS_ACTIVITY": 0,
            "CORRELATED_ACTIVITY": 0,
            "UNKNOWN": 0,
        }

        self.events: List[ForensicEvent] = []

    def summary_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "error_message": self.error_message,
            "evidence_id": self.evidence.id if self.evidence else None,
            "filename": self.evidence.filename if self.evidence else None,
            "sha256": self.evidence.sha256_hash if self.evidence else None,
            "format_detected": self.parse_result.format_detected if self.parse_result else None,
            "source_type_detected": self.parse_result.source_type_detected if self.parse_result else None,
            "records_parsed": self.parse_result.records_parsed if self.parse_result else 0,
            "records_failed": self.parse_result.records_failed if self.parse_result else 0,
            "events_extracted": self.events_extracted,
            "events_stored": self.events_stored,
            "suspicious_activities": len(self.suspicious_activities),
            "relationships": len(self.relationships),
            "incidents": len(self.incidents),
            "classification_counts": dict(self.classification_counts),
        }


def _emit(progress_cb: ProgressCallback, msg: str) -> None:
    if progress_cb:
        try:
            progress_cb(msg)
        except Exception:
            pass


def analyze_preserved_artifact(
    db: Session,
    case_id: str,
    evidence: EvidenceArtifact,
    graph_db: EvidenceGraph,
    actor: str = "investigator",
    force_source_type: Optional[str] = None,
    progress_cb: ProgressCallback = None,
) -> OfflineAnalysisResult:
    """Parse → normalize → correlate → findings for an already-ingested artifact."""
    result = OfflineAnalysisResult()
    result.evidence = evidence

    try:
        _emit(progress_cb, "Parsing report...")
        parse_result = parse_report(evidence.original_path)
        result.parse_result = parse_result

        if not parse_result.success:
            result.success = False
            result.error_message = parse_result.error_message or "Unsupported or unparseable evidence format"
            _emit(progress_cb, f"Warning: {result.error_message}")
            # Preserve artifact even when parse fails (matches prior behavior)
            result.success = True
            return result

        source_type = force_source_type or parse_result.source_type_detected
        evidence.source_type = source_type
        db.commit()
        db.refresh(evidence)

        _emit(progress_cb, "Normalizing events...")
        events = list(normalize_records(parse_result.records, source_type, case_id, evidence.id))
        result.events_extracted = len(events)

        events_sorted = sorted(
            events,
            key=lambda e: (e.timestamp if e.timestamp else datetime.datetime.max)
        )
        result.events = events_sorted

        if events_sorted:
            stored = bulk_store_events(db, events_sorted, evidence.id, actor)
            result.events_stored = stored
            db.commit()
        else:
            result.events_stored = 0

        if events_sorted:
            _emit(progress_cb, "Correlating events...")
            rels = correlate_events(events_sorted, max_window_seconds=86400)
            result.relationships = rels

            if rels:
                graph_db.populate_from_correlations(rels)
            _emit(progress_cb, f"Correlation complete: {len(rels)} relationships")
        else:
            result.relationships = []

        graph_snapshot = graph_db.graph.copy()

        _emit(progress_cb, "Running suspicious detection engine...")
        suspicious = detect_suspicious_activity(graph_snapshot)
        result.suspicious_activities = suspicious
        _emit(progress_cb, f"Suspicious detection: {len(suspicious)} findings")

        _emit(progress_cb, "Reconstructing incidents...")
        incidents = reconstruct_incidents(graph_snapshot, suspicious)
        result.incidents = incidents
        _emit(progress_cb, f"Incident reconstruction: {len(incidents)} potential incidents")

        cls_engine = ClassificationEngine()
        for ev in events_sorted:
            r = cls_engine.classify_event(ev, graph_snapshot, suspicious)
            cls = r["classification"]
            if cls in result.classification_counts:
                result.classification_counts[cls] += 1

        result.success = True
        _emit(progress_cb, "Finalizing analysis...")
        _emit(progress_cb, "Analysis Complete")
        return result

    except Exception as e:
        result.success = False
        result.error_message = f"Analysis error: {e}"
        return result


def run_offline_analysis(
    db: Session,
    case_id: str,
    source_file_path: str,
    graph_db: EvidenceGraph,
    actor: str = "investigator",
    force_source_type: Optional[str] = None,
    progress_cb: ProgressCallback = None,
    evidence_root: Optional[str] = None,
) -> OfflineAnalysisResult:
    result = OfflineAnalysisResult()

    try:
        _emit(progress_cb, "Uploading evidence...")
        evidence = ingest_preserved_evidence(
            db,
            case_id,
            source_file_path,
            "offline_report",
            actor,
            evidence_root=evidence_root,
        )
        result.evidence = evidence
        _emit(progress_cb, f"SHA-256 calculated: {evidence.sha256_hash[:16]}...")

        analyzed = analyze_preserved_artifact(
            db=db,
            case_id=case_id,
            evidence=evidence,
            graph_db=graph_db,
            actor=actor,
            force_source_type=force_source_type,
            progress_cb=progress_cb,
        )
        return analyzed

    except Exception as e:
        result.success = False
        result.error_message = f"Analysis error: {e}"
        return result
