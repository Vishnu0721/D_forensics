import hashlib
import os
import psutil
import time
from datetime import datetime
from .base import BaseCollector

MAX_HASH_BYTES = 8 * 1024 * 1024
HASH_CACHE_LIMIT = 2000

class ProcessCollector(BaseCollector):
    def __init__(self, case_id: str, poll_interval: int = 2):
        super().__init__(case_id)
        self.poll_interval = poll_interval
        self._seen_pids = set()
        self._hash_cache = {}

    def _hash_executable(self, exe_path: str) -> str:
        """SHA-256 of an executable, cached by (path, size, mtime)."""
        try:
            st = os.stat(exe_path)
        except OSError:
            return "Unavailable"
        if st.st_size > MAX_HASH_BYTES:
            return "skipped_large_file"
        key = (exe_path.lower(), st.st_size, st.st_mtime_ns)
        cached = self._hash_cache.get(key)
        if cached:
            return cached
        h = hashlib.sha256()
        try:
            with open(exe_path, "rb") as f:
                for byte_block in iter(lambda: f.read(65536), b""):
                    if not self._is_running:
                        return "Unavailable"
                    h.update(byte_block)
        except OSError:
            return "Unavailable"
        digest = h.hexdigest()
        if len(self._hash_cache) >= HASH_CACHE_LIMIT:
            self._hash_cache.clear()
        self._hash_cache[key] = digest
        return digest
        
    def run(self):
        # Capture baseline to avoid emitting events for already running processes
        for p in psutil.process_iter(['pid']):
            self._seen_pids.add(p.info['pid'])
            
        while self._is_running:
            try:
                current_pids = set(psutil.pids())
                new_pids = current_pids - self._seen_pids
                terminated_pids = self._seen_pids - current_pids
                
                # Handle terminated processes
                for pid in terminated_pids:
                    if not self._is_running: break
                    event = {
                        "timestamp": datetime.utcnow().isoformat() + "Z",
                        "source_type": "process",
                        "event_type": "process_terminated",
                        "pid": pid,
                        "process": "Unavailable",
                        "parent_process": "Unavailable",
                        "parent_pid": "Unavailable",
                        "user": "Unavailable",
                        "path": "Unavailable",
                        "cmdline": "Unavailable",
                        "create_time": "Unavailable",
                        "sha256": "Unavailable"
                    }
                    self.event_captured.emit(event)
                
                for pid in new_pids:
                    if not self._is_running: 
                        break
                    try:
                        p = psutil.Process(pid)
                        
                        # Extract username safely
                        try:
                            user = p.username()
                            if '\\' in user:
                                user = user.split('\\')[1]
                        except psutil.AccessDenied:
                            user = "Unavailable"
                            
                        # Extract parent process
                        try:
                            parent = p.parent()
                            parent_name = parent.name() if parent else "Unavailable"
                            parent_pid = parent.pid if parent else "Unavailable"
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            parent_name = "Unavailable"
                            parent_pid = "Unavailable"
                            
                        try:
                            cmdline = p.cmdline()
                            if not cmdline: cmdline = "Unavailable"
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            cmdline = "Unavailable"
                            
                        try:
                            create_time = p.create_time()
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            create_time = "Unavailable"
                            
                        exe_path = p.exe() or "Unavailable"
                        
                        sha256_hash = "Unavailable"
                        if exe_path != "Unavailable":
                            sha256_hash = self._hash_executable(exe_path)
                                
                        event = {
                            "timestamp": datetime.utcnow().isoformat() + "Z",
                            "source_type": "process",
                            "event_type": "process_started",
                            "pid": pid,
                            "process": p.name(),
                            "parent_process": parent_name,
                            "parent_pid": parent_pid,
                            "user": user,
                            "path": exe_path,
                            "cmdline": cmdline,
                            "create_time": create_time,
                            "sha256": sha256_hash
                        }
                        
                        # Only emit if it's not a generic inaccessible system process
                        if event["process"]:
                            self.event_captured.emit(event)
                            
                    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                        pass
                
                self._seen_pids = current_pids
                
            except Exception as e:
                print(f"ProcessCollector error: {e}")
                
            # Wait for next poll cycle without blocking Stop for the full interval
            self.interruptible_sleep(self.poll_interval)
