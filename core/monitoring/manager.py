import json
import hashlib
from PySide6.QtCore import QObject, Signal, Slot
from typing import Dict, Any

from core.database import SessionLocal
from core.database.models import EvidenceArtifact, AuditLog
from core.services.normalization import NORMALIZERS
from .process import ProcessCollector
from .filesystem import FilesystemCollector
from .network import NetworkCollector

class PersistenceWorker(QObject):
    event_processed = Signal(object)
    
    def __init__(self, case_id: str):
        super().__init__()
        self.case_id = case_id
        
    @Slot(dict)
    def handle_raw_event(self, raw_event: Dict[str, Any]):
        import time
        start_time = time.perf_counter()
        
        db = SessionLocal()
        try:
            # 1. Live Evidence Generation
            raw_json = json.dumps(raw_event, sort_keys=True)
            
            # Create physical directory
            import os, uuid
            evidence_id = str(uuid.uuid4())
            evidence_dir = os.path.join("data", "evidence", self.case_id)
            os.makedirs(evidence_dir, exist_ok=True)
            
            filename = f"{evidence_id}.json"
            file_path = os.path.abspath(os.path.join(evidence_dir, filename))
            
            # Write to disk securely
            with open(file_path, "wb") as f:
                f.write(raw_json.encode('utf-8'))
                
            # Read back to ensure hash matches EXACT physical bytes on disk
            with open(file_path, "rb") as f:
                disk_bytes = f.read()
            event_hash = hashlib.sha256(disk_bytes).hexdigest()
            
            evidence = EvidenceArtifact(
                id=evidence_id,
                case_id=self.case_id,
                filename=filename,
                source_type=raw_event['source_type'],
                original_path=file_path,
                file_size=len(disk_bytes),
                sha256_hash=event_hash,
                mime_type="application/json",
                created_by="system_monitor",
                integrity_status="VALID"
            )
            db.add(evidence)
            db.commit()
            db.refresh(evidence)
            
            # 2. Normalization
            normalizer = NORMALIZERS.get(raw_event['source_type'])
            if normalizer:
                forensic_event = normalizer(raw_event, self.case_id, evidence.id)
                db.add(forensic_event)
                db.commit()
                db.refresh(forensic_event)
                
                # 3. Notify the correlation engine and GUI
                self.event_processed.emit(forensic_event)
                
        except Exception as e:
            print(f"PersistenceWorker error: {e}")
            db.rollback()
        finally:
            db.close()
            
        elapsed = (time.perf_counter() - start_time) * 1000
        print(f"[PERF] persistence: {elapsed:.2f} ms")


class MonitoringManager(QObject):
    """
    Coordinates all collectors, processes incoming raw events,
    creates in-memory evidence artifacts, and normalizes them.
    """
    # Signal emitted when an event is successfully stored in the DB
    event_processed = Signal(object) 
    
    def __init__(self, case_id: str):
        super().__init__()
        self.case_id = case_id
        
        from PySide6.QtCore import QThread
        self.worker_thread = QThread()
        self.persistence_worker = PersistenceWorker(case_id)
        self.persistence_worker.moveToThread(self.worker_thread)
        self.worker_thread.start()
        
        self.persistence_worker.event_processed.connect(self.event_processed)
        
        self.collectors = [
            ProcessCollector(case_id, poll_interval=2),
            FilesystemCollector(case_id),
            NetworkCollector(case_id, poll_interval=3)
        ]
        
        for collector in self.collectors:
            # Connect the collector's signal directly to the persistence worker's slot
            # Because they are in different threads, Qt will safely queue these calls
            collector.event_captured.connect(self.persistence_worker.handle_raw_event)
            
    def start_all(self):
        for c in self.collectors:
            c.start_monitoring()
            
    def stop_all(self):
        for c in self.collectors:
            c.stop_monitoring()
            
    def shutdown(self):
        self.stop_all()
        self.worker_thread.quit()
        self.worker_thread.wait()
