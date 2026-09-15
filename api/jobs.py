"""In-memory analysis job tracker with per-case locking."""

from __future__ import annotations

import threading
import uuid
from collections import OrderedDict
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
    """Bounded job history + one active analysis per case."""

    MAX_JOBS = 200

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._jobs: OrderedDict[str, JobRecord] = OrderedDict()
        self._case_active: dict[str, str] = {}

    def create(self, case_id: str) -> JobRecord:
        with self._lock:
            active_id = self._case_active.get(case_id)
            if active_id:
                active = self._jobs.get(active_id)
                if active and active.status in ("queued", "running"):
                    raise RuntimeError(
                        "An analysis job is already running for this case. Wait for it to finish."
                    )
            job = JobRecord(id=str(uuid.uuid4()), case_id=case_id)
            self._jobs[job.id] = job
            self._case_active[case_id] = job.id
            while len(self._jobs) > self.MAX_JOBS:
                old_id, old = self._jobs.popitem(last=False)
                if old.status in ("queued", "running"):
                    self._jobs[old_id] = old
                    self._jobs.move_to_end(old_id)
                    break
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
            if job.status in ("completed", "failed"):
                if self._case_active.get(job.case_id) == job_id:
                    self._case_active.pop(job.case_id, None)
            return job

    def active_for_case(self, case_id: str) -> Optional[JobRecord]:
        with self._lock:
            job_id = self._case_active.get(case_id)
            if not job_id:
                return None
            return self._jobs.get(job_id)


job_store = JobStore()
