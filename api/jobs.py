"""In-memory analysis job tracker (Phase 1)."""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


@dataclass
class JobRecord:
    id: str
    case_id: str
    status: str = "queued"
    progress: float = 0.0
    message: str = "Queued"
    error: Optional[str] = None
    result_summary: Optional[dict[str, Any]] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class JobStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._jobs: dict[str, JobRecord] = {}

    def create(self, case_id: str) -> JobRecord:
        job = JobRecord(id=str(uuid.uuid4()), case_id=case_id)
        with self._lock:
            self._jobs[job.id] = job
        return job

    def get(self, job_id: str) -> Optional[JobRecord]:
        with self._lock:
            return self._jobs.get(job_id)

    def update(self, job_id: str, **kwargs: Any) -> Optional[JobRecord]:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return None
            for key, value in kwargs.items():
                setattr(job, key, value)
            job.updated_at = datetime.now(timezone.utc)
            return job


job_store = JobStore()
