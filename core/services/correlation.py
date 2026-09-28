from typing import List, Dict, Any
from PySide6.QtCore import QObject, Signal, Slot, QTimer
import time
from core.database.models import ForensicEvent
from core.database import SessionLocal
from core.paths import DEBUG_LOGGING
from core.services.graph import (
    make_process_entity,
    make_ip_entity,
    make_file_entity,
    make_user_entity,
    make_device_entity,
)

# Configurable weights for confidence scoring
WEIGHTS = {
    'time': 0.4,
    'entity': 0.4,
    'source': 0.2
}

_HEX_DIGITS = frozenset("0123456789abcdefABCDEF")


def _is_real_sha256(value: Any) -> bool:
    """Collectors use placeholders like 'Unavailable' or 'skipped_large_file'; only real digests may match."""
    return isinstance(value, str) and len(value) == 64 and all(c in _HEX_DIGITS for c in value)


def _same_windows_name(a: Any, b: Any) -> bool:
    """Windows paths and file names are case-insensitive (live file events are lower-cased)."""
    return bool(a) and bool(b) and str(a).lower() == str(b).lower()


def calculate_temporal_score(event_a: ForensicEvent, event_b: ForensicEvent, max_window_seconds: int = 300) -> float:
    """Calculates a temporal proximity score between 0.0 and 1.0."""
    time_diff = abs((event_a.timestamp - event_b.timestamp).total_seconds())
    if time_diff > max_window_seconds:
        return 0.0
    return 1.0 - (time_diff / max_window_seconds)

def correlate_events(events: List[ForensicEvent], max_window_seconds: int = 300) -> List[Dict[str, Any]]:
    """
    Applies deterministic rules to find relationships between events.
    Returns a list of relationship dictionaries ready for graph insertion.
    """
    relationships = []
    
    # Sort events chronologically to allow sliding window
    events.sort(key=lambda x: x.timestamp)
    
    for i in range(len(events)):
        event_a = events[i]
        host_str_a = event_a.host or "localhost"
        
        # Intra-event Rule: Network -> Process (Live telemetry correlation)
        if event_a.event_type == 'connection' and event_a.pid and event_a.process and event_a.ip:
            relationships.append({
                "source": make_process_entity(host_str_a, event_a.pid, event_a.process),
                "target": make_ip_entity(event_a.ip),
                "type": "CONNECTED_TO",
                "confidence": 1.0,
                "evidence_ids": [event_a.evidence_id],
                "reasons": [
                    f"Process {event_a.process} (PID {event_a.pid}) directly established connection to {event_a.ip}"
                ]
            })
            
        for j in range(i + 1, len(events)):
            event_b = events[j]
            host_str_b = event_b.host or "localhost"
            
            time_diff = abs((event_a.timestamp - event_b.timestamp).total_seconds())
            if time_diff > max_window_seconds:
                break # We can break inner loop early since events are sorted
                
            temp_score = calculate_temporal_score(event_a, event_b, max_window_seconds)
            
            # Rule 1: Process -> Network (Fallback for missing process names in network events)
            if event_a.event_type == 'process_started' and event_b.event_type == 'connection':
                if event_a.pid and event_a.pid != "Unavailable" and event_a.pid == event_b.pid and event_a.host == event_b.host:
                    conf = (WEIGHTS['time'] * temp_score) + (WEIGHTS['entity'] * 1.0) + (WEIGHTS['source'] * 0.9)
                    relationships.append({
                        "source": make_process_entity(host_str_a, event_a.pid, event_a.process),
                        "target": make_ip_entity(event_b.ip),
                        "type": "CONNECTED_TO",
                        "confidence": round(min(conf, 1.0), 2),
                        "evidence_ids": [event_a.evidence_id, event_b.evidence_id],
                        "reasons": [
                            f"Matching PID {event_a.pid} on host {host_str_a}",
                            f"Events occurred {time_diff} seconds apart"
                        ]
                    })
                    
            # Rule 2: File -> Process
            if event_a.event_type == 'file_created' and event_b.event_type == 'process_started':
                if event_a.host == event_b.host:
                    path_match = _same_windows_name(event_a.path, event_b.path)
                    file_match = _same_windows_name(event_a.file, event_b.process)
                    
                    if path_match or file_match:
                        conf = (WEIGHTS['time'] * temp_score) + (WEIGHTS['entity'] * (1.0 if path_match else 0.8)) + (WEIGHTS['source'] * 0.9)
                        
                        reasons = []
                        if path_match:
                            reasons.append(f"Matching exact path {event_a.path} on host {host_str_a}")
                        else:
                            reasons.append(f"Matching filename {event_a.file} to process name on host {host_str_a}")
                        reasons.append(f"Events occurred {time_diff} seconds apart")
                        
                        relationships.append({
                            "source": make_file_entity(host_str_a, event_a.file),
                            "target": make_process_entity(host_str_b, event_b.pid, event_b.process),
                            "type": "EXECUTED_AS",
                            "confidence": round(min(conf, 1.0), 2),
                            "evidence_ids": [event_a.evidence_id, event_b.evidence_id],
                            "reasons": reasons,
                            "file_path": event_a.path,
                            "time_diff_seconds": time_diff,
                        })
                    
            # Rule 3: Browser Download -> File Created
            if event_a.event_type == 'download' and event_b.event_type == 'file_created':
                if event_a.file and event_a.file == event_b.file and event_a.host == event_b.host:
                    conf = (WEIGHTS['time'] * temp_score) + (WEIGHTS['entity'] * 0.9) + (WEIGHTS['source'] * 0.9)
                    relationships.append({
                        "source": make_user_entity(event_a.user or "unknown"),
                        "target": make_file_entity(host_str_b, event_b.file),
                        "type": "DOWNLOADED",
                        "confidence": round(min(conf, 1.0), 2),
                        "evidence_ids": [event_a.evidence_id, event_b.evidence_id],
                        "reasons": [
                            f"User {event_a.user or 'unknown'} downloaded {event_a.file}",
                            f"Events occurred {time_diff} seconds apart"
                        ]
                    })
                    
    return relationships

def correlate_new_event(new_event: ForensicEvent, history: List[ForensicEvent], max_window_seconds: int = 300) -> List[Dict[str, Any]]:
    """
    Correlates a single new event against a bounded history of past events.
    """
    relationships = []
    host_str_a = new_event.host or "localhost"
    
    # Intra-event Rule: Network -> Process (Live telemetry correlation)
    if new_event.event_type == 'connection' and new_event.pid and new_event.process and new_event.ip:
        relationships.append({
            "source": make_process_entity(host_str_a, new_event.pid, new_event.process),
            "target": make_ip_entity(new_event.ip),
            "type": "CONNECTED_TO",
            "confidence": 1.0,
            "evidence_ids": [new_event.evidence_id],
            "reasons": [
                f"Process {new_event.process} (PID {new_event.pid}) directly established connection to {new_event.ip}"
            ]
        })
        
    for past_event in history:
        host_str_b = past_event.host or "localhost"
        
        # Determine temporal order
        if past_event.timestamp <= new_event.timestamp:
            event_early, event_late = past_event, new_event
            host_early, host_late = host_str_b, host_str_a
        else:
            event_early, event_late = new_event, past_event
            host_early, host_late = host_str_a, host_str_b
            
        time_diff = abs((event_early.timestamp - event_late.timestamp).total_seconds())
        if time_diff > max_window_seconds:
            continue
            
        temp_score = calculate_temporal_score(event_early, event_late, max_window_seconds)
        
        # Rule 1: Process -> Network
        if event_early.event_type == 'process_started' and event_late.event_type == 'connection':
            if event_early.pid and event_early.pid != "Unavailable" and event_early.pid == event_late.pid and event_early.host == event_late.host:
                conf = (WEIGHTS['time'] * temp_score) + (WEIGHTS['entity'] * 1.0) + (WEIGHTS['source'] * 0.9)
                relationships.append({
                    "source": make_process_entity(host_early, event_early.pid, event_early.process),
                    "target": make_ip_entity(event_late.ip),
                    "type": "CONNECTED_TO",
                    "confidence": round(min(conf, 1.0), 2),
                    "evidence_ids": [event_early.evidence_id, event_late.evidence_id],
                    "reasons": [
                        f"Matching PID {event_early.pid} on host {host_early}",
                        f"Events occurred {time_diff} seconds apart"
                    ]
                })
                
        # Rule 2: File -> Process
        if event_early.event_type == 'file_created' and event_late.event_type == 'process_started':
            if event_early.host == event_late.host:
                path_match = _same_windows_name(event_early.path, event_late.path)
                file_match = _same_windows_name(event_early.file, event_late.process)
                
                if path_match or file_match:
                    conf = (WEIGHTS['time'] * temp_score) + (WEIGHTS['entity'] * (1.0 if path_match else 0.8)) + (WEIGHTS['source'] * 0.9)
                    
                    reasons = []
                    if path_match:
                        reasons.append(f"Matching exact path {event_early.path} on host {host_early}")
                    else:
                        reasons.append(f"Matching filename {event_early.file} to process name on host {host_early}")
                    reasons.append(f"Events occurred {time_diff} seconds apart")
                    
                    relationships.append({
                        "source": make_file_entity(host_early, event_early.file),
                        "target": make_process_entity(host_late, event_late.pid, event_late.process),
                        "type": "EXECUTED_AS",
                        "confidence": round(min(conf, 1.0), 2),
                        "evidence_ids": [event_early.evidence_id, event_late.evidence_id],
                        "reasons": reasons,
                        "file_path": event_early.path,
                        "time_diff_seconds": time_diff,
                    })
                
        # Rule 3: Browser Download -> File Created
        if event_early.event_type == 'download' and event_late.event_type == 'file_created':
            if event_early.file and event_early.file == event_late.file and event_early.host == event_late.host:
                conf = (WEIGHTS['time'] * temp_score) + (WEIGHTS['entity'] * 0.9) + (WEIGHTS['source'] * 0.9)
                relationships.append({
                    "source": make_user_entity(event_early.user or "unknown"),
                    "target": make_file_entity(host_late, event_late.file),
                    "type": "DOWNLOADED",
                    "confidence": round(min(conf, 1.0), 2),
                    "evidence_ids": [event_early.evidence_id, event_late.evidence_id],
                    "reasons": [
                        f"User {event_early.user or 'unknown'} downloaded {event_early.file}",
                        f"Events occurred {time_diff} seconds apart"
                    ]
                })
                
        # Rule 4: User -> Process (Login)
        if event_early.event_type == 'login' and event_late.event_type == 'process_started':
            if event_early.user and event_early.user == event_late.user and event_early.host == event_late.host:
                conf = (WEIGHTS['time'] * temp_score) + (WEIGHTS['entity'] * 1.0) + (WEIGHTS['source'] * 0.8)
                relationships.append({
                    "source": make_user_entity(event_early.user),
                    "target": make_process_entity(host_late, event_late.pid, event_late.process),
                    "type": "EXECUTED_BY",
                    "confidence": round(min(conf, 1.0), 2),
                    "evidence_ids": [event_early.evidence_id, event_late.evidence_id],
                    "reasons": [
                        f"Process {event_late.process} started by user {event_early.user} shortly after login",
                        f"Events occurred {time_diff} seconds apart"
                    ]
                })

        # Rule 5: Process/File -> USB (Exfiltration)
        if event_early.event_type in ['file_accessed', 'file_created', 'process_started'] and event_late.event_type in ['usb_connected', 'file_copied']:
            if event_early.host == event_late.host:
                conf = (WEIGHTS['time'] * temp_score) + (WEIGHTS['entity'] * 0.7) + (WEIGHTS['source'] * 0.9)
                if event_early.event_type == 'process_started':
                    source = make_process_entity(host_early, event_early.pid, event_early.process)
                else:
                    source = make_file_entity(host_early, event_early.file)
                relationships.append({
                    "source": source,
                    "target": make_device_entity(host_late, event_late.user),
                    "type": "EXFILTRATED_VIA",
                    "confidence": round(min(conf, 1.0), 2),
                    "evidence_ids": [event_early.evidence_id, event_late.evidence_id],
                    "reasons": [
                        f"Potential exfiltration: {event_early.event_type} followed by {event_late.event_type}",
                        f"Events occurred {time_diff} seconds apart"
                    ]
                })

        # Rule 6: Process Hash Matching
        if event_early.event_type == 'process_started' and event_late.event_type == 'process_started':
            if _is_real_sha256(event_early.file_hash) and _is_real_sha256(event_late.file_hash):
                if event_early.file_hash.lower() == event_late.file_hash.lower() and event_early.pid != event_late.pid:
                    conf = 1.0  # Exact hash match is strong evidence
                    relationships.append({
                        "source": make_process_entity(host_early, event_early.pid, event_early.process),
                        "target": make_process_entity(host_late, event_late.pid, event_late.process),
                        "type": "SAME_HASH_AS",
                        "confidence": conf,
                        "evidence_ids": [event_early.evidence_id, event_late.evidence_id],
                        "reasons": [
                            f"Identical SHA-256 hash: {event_early.file_hash}"
                        ]
                    })
                
    return relationships


ANALYSIS_MIN_INTERVAL_SECONDS = 1.5
# Event-rule findings (parent process, command line, ports...) kept for the live session.
MAX_EVENT_FINDINGS = 2000


class CorrelationWorker(QObject):
    correlations_found = Signal(list)
    graph_updated = Signal(object) # emits nx_graph snapshot
    suspicious_updated = Signal(list)
    incidents_updated = Signal(list)
    analysis_error = Signal(str)

    def __init__(self, case_id: str, graph_db):
        super().__init__()
        self.case_id = case_id
        self.graph_db = graph_db
        self._last_analysis = 0.0
        self._analysis_timer = None
        self._event_findings = {}

    def _collect_event_findings(self, events) -> bool:
        from core.services.suspicious import detect_event_findings

        added = False
        for finding in detect_event_findings(events):
            existing = self._event_findings.get(finding["activity_id"])
            if existing is not None and existing["score"] >= finding["score"]:
                continue
            if existing is None and len(self._event_findings) >= MAX_EVENT_FINDINGS:
                self._event_findings.pop(next(iter(self._event_findings)))
            self._event_findings[finding["activity_id"]] = finding
            added = True
        return added
        
    @Slot(list)
    def process_batch(self, events: List[ForensicEvent]):
        if not events:
            return
            
        start_time = time.perf_counter()
        db = SessionLocal()
        try:
            # Query history once for the batch
            history = db.query(ForensicEvent).filter(ForensicEvent.case_id == self.case_id).order_by(ForensicEvent.timestamp.desc()).limit(100).all()
            
            all_new_relationships = []
            
            for event in events:
                # We could optimize by correlating the whole batch against history, but correlate_new_event expects one
                rels = correlate_new_event(event, history, max_window_seconds=120)
                if rels:
                    all_new_relationships.extend(rels)
                    
            new_findings = self._collect_event_findings(events)

            if all_new_relationships:
                self.graph_db.populate_from_correlations(all_new_relationships)
                self.correlations_found.emit(all_new_relationships)
            if all_new_relationships or new_findings:
                self._schedule_analysis()
                
        except Exception as e:
            self.analysis_error.emit(str(e))
        finally:
            db.close()
            
        if DEBUG_LOGGING:
            elapsed = (time.perf_counter() - start_time) * 1000
            print(f"[PERF] correlation: {elapsed:.2f} ms")

    def _schedule_analysis(self):
        """Whole-graph analysis is expensive; coalesce bursts into one run per interval."""
        elapsed = time.monotonic() - self._last_analysis
        if elapsed >= ANALYSIS_MIN_INTERVAL_SECONDS:
            self._run_analysis()
            return
        if self._analysis_timer is None:
            # Created lazily so the timer lives in this worker's thread.
            self._analysis_timer = QTimer(self)
            self._analysis_timer.setSingleShot(True)
            self._analysis_timer.timeout.connect(self._run_analysis)
        if not self._analysis_timer.isActive():
            remaining_ms = int((ANALYSIS_MIN_INTERVAL_SECONDS - elapsed) * 1000) + 1
            self._analysis_timer.start(remaining_ms)

    @Slot()
    def _run_analysis(self):
        self._last_analysis = time.monotonic()
        try:
            from core.services.suspicious import detect_suspicious_activity, merge_findings
            from core.services.reconstruction import reconstruct_incidents

            graph_snapshot = self.graph_db.snapshot()
            suspicious = merge_findings(
                detect_suspicious_activity(graph_snapshot),
                list(self._event_findings.values()),
            )
            incidents = reconstruct_incidents(graph_snapshot, suspicious)

            self.graph_updated.emit(graph_snapshot)
            self.suspicious_updated.emit(suspicious)
            self.incidents_updated.emit(incidents)
        except Exception as e:
            self.analysis_error.emit(str(e))
