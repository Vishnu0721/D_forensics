"""
Web live monitor — process + network polling for THIS PC only.

Mirrors desktop collectors conceptually (psutil process/network) but does NOT use
Qt MonitoringManager or desktop data/ paths. Writes only under web_data/.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import psutil

from api.case_meta import save_case_meta
from api.config import get_settings
from api.db import get_session_factory
from core.database.models import EvidenceArtifact
from core.services.normalization import NORMALIZERS


class LiveMonitorError(Exception):
    pass


class WebLiveMonitor:
    """At most one live case at a time."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._case_id: Optional[str] = None
        self._running = False
        self._threads: list[threading.Thread] = []
        self._started_at: Optional[str] = None
        self._events_captured = 0
        self._last_error: Optional[str] = None
        self._seen_pids: set[int] = set()
        self._seen_conns: set[tuple] = set()

    def status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "available": True,
                "running": self._running,
                "case_id": self._case_id,
                "started_at": self._started_at,
                "events_captured": self._events_captured,
                "last_error": self._last_error,
                "collectors": ["process", "network"],
                "note": "Local PC only. Writes to web_data/ — never forensics.db/data/.",
            }

    def start(self, case_id: str) -> dict[str, Any]:
        with self._lock:
            if self._running:
                if self._case_id == case_id:
                    return self.status()
                raise LiveMonitorError(
                    f"Live monitoring already active for case {self._case_id}. Stop it first."
                )
            self._case_id = case_id
            self._running = True
            self._events_captured = 0
            self._last_error = None
            self._started_at = datetime.now(timezone.utc).isoformat()
            self._seen_pids = set()
            self._seen_conns = set()
            self._threads = [
                threading.Thread(target=self._process_loop, name="web-live-process", daemon=True),
                threading.Thread(target=self._network_loop, name="web-live-network", daemon=True),
            ]
            for t in self._threads:
                t.start()
            save_case_meta(case_id, mode="live", live_started_at=self._started_at)
            return self.status()

    def stop(self) -> dict[str, Any]:
        with self._lock:
            case_id = self._case_id
            self._running = False
        for t in list(self._threads):
            t.join(timeout=3.0)
        with self._lock:
            self._threads = []
            if case_id:
                save_case_meta(
                    case_id,
                    mode="imported",
                    live_stopped_at=datetime.now(timezone.utc).isoformat(),
                )
            status = self.status()
            self._case_id = None
            self._started_at = None
            return status

    def _persist(self, raw_event: dict[str, Any]) -> None:
        case_id = self._case_id
        if not case_id or not self._running:
            return
        settings = get_settings()
        SessionLocal = get_session_factory()
        db = SessionLocal()
        try:
            evidence_id = str(uuid.uuid4())
            evidence_dir = settings.evidence_dir / case_id / "live"
            evidence_dir.mkdir(parents=True, exist_ok=True)
            filename = f"{evidence_id}.json"
            file_path = evidence_dir / filename
            disk_bytes = json.dumps(raw_event, sort_keys=True).encode("utf-8")
            file_path.write_bytes(disk_bytes)

            evidence = EvidenceArtifact(
                id=evidence_id,
                case_id=case_id,
                filename=filename,
                source_type=raw_event.get("source_type") or "process",
                original_path=str(file_path.resolve()),
                file_size=len(disk_bytes),
                sha256_hash=hashlib.sha256(disk_bytes).hexdigest(),
                mime_type="application/json",
                created_by="web_live_monitor",
                integrity_status="VALID",
            )
            db.add(evidence)
            db.commit()
            db.refresh(evidence)

            normalizer = NORMALIZERS.get(raw_event.get("source_type"))
            if normalizer:
                db.add(normalizer(raw_event, case_id, evidence.id))
                db.commit()

            with self._lock:
                self._events_captured += 1
        except Exception as exc:
            db.rollback()
            with self._lock:
                self._last_error = str(exc)
        finally:
            db.close()

    def _interruptible_sleep(self, seconds: float) -> None:
        end = time.time() + seconds
        while self._running and time.time() < end:
            time.sleep(0.1)

    def _process_loop(self) -> None:
        try:
            for p in psutil.process_iter(["pid"]):
                try:
                    self._seen_pids.add(p.info["pid"])
                except Exception:
                    continue
            while self._running:
                try:
                    current = set(psutil.pids())
                    for pid in list(current - self._seen_pids)[:40]:
                        if not self._running:
                            break
                        self._emit_process_start(pid)
                    self._seen_pids = current
                except Exception as exc:
                    with self._lock:
                        self._last_error = f"process: {exc}"
                self._interruptible_sleep(2.0)
        except Exception as exc:
            with self._lock:
                self._last_error = f"process loop: {exc}"
                self._running = False

    def _emit_process_start(self, pid: int) -> None:
        try:
            p = psutil.Process(pid)
            try:
                user = p.username()
                if "\\" in user:
                    user = user.split("\\")[1]
            except Exception:
                user = "Unavailable"
            try:
                parent = p.parent()
                parent_name = parent.name() if parent else "Unavailable"
            except Exception:
                parent_name = "Unavailable"
            try:
                cmdline = p.cmdline() or "Unavailable"
            except Exception:
                cmdline = "Unavailable"
            try:
                exe_path = p.exe()
            except Exception:
                exe_path = "Unavailable"
            self._persist(
                {
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "source_type": "process",
                    "event_type": "process_started",
                    "pid": pid,
                    "process": p.name() if hasattr(p, "name") else "Unavailable",
                    "parent_process": parent_name,
                    "user": user,
                    "path": exe_path,
                    "cmdline": cmdline,
                    "sha256": "Unavailable",
                }
            )
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return

    def _network_loop(self) -> None:
        try:
            try:
                for conn in psutil.net_connections(kind="inet"):
                    if conn.raddr:
                        self._seen_conns.add(
                            (conn.laddr.ip, conn.laddr.port, conn.raddr.ip, conn.raddr.port)
                        )
            except psutil.AccessDenied:
                with self._lock:
                    self._last_error = (
                        "Network collector needs elevated privileges for full PID mapping."
                    )

            while self._running:
                try:
                    current: set[tuple] = set()
                    for conn in psutil.net_connections(kind="inet"):
                        if not conn.raddr:
                            continue
                        key = (conn.laddr.ip, conn.laddr.port, conn.raddr.ip, conn.raddr.port)
                        current.add(key)
                        if key in self._seen_conns:
                            continue
                        process_name = "Unavailable"
                        pid = conn.pid or "Unavailable"
                        if conn.pid:
                            try:
                                process_name = psutil.Process(conn.pid).name()
                            except Exception:
                                pass
                        self._persist(
                            {
                                "timestamp": datetime.utcnow().isoformat() + "Z",
                                "source_type": "network",
                                "event_type": "connection",
                                "process": process_name,
                                "pid": pid,
                                "ip": conn.raddr.ip,
                                "port": conn.raddr.port,
                                "protocol": "TCP" if conn.type == 1 else "UDP",
                            }
                        )
                    self._seen_conns = current
                except psutil.AccessDenied:
                    with self._lock:
                        self._last_error = "Network AccessDenied — try running API elevated."
                    self._interruptible_sleep(6.0)
                    continue
                except Exception as exc:
                    with self._lock:
                        self._last_error = f"network: {exc}"
                self._interruptible_sleep(3.0)
        except Exception as exc:
            with self._lock:
                self._last_error = f"network loop: {exc}"


live_monitor = WebLiveMonitor()
