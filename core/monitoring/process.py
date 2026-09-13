import psutil
import time
from datetime import datetime
from .base import BaseCollector

class ProcessCollector(BaseCollector):
    def __init__(self, case_id: str, poll_interval: int = 2):
        super().__init__(case_id)
        self.poll_interval = poll_interval
        self._seen_pids = set()
        
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
                            
                        exe_path = p.exe() if hasattr(p, 'exe') and p.exe() else "Unavailable"
                        
                        sha256_hash = "Unavailable"
                        if exe_path and exe_path != "Unavailable":
                            try:
                                import hashlib
                                h = hashlib.sha256()
                                with open(exe_path, "rb") as f:
                                    for byte_block in iter(lambda: f.read(8192), b""):
                                        h.update(byte_block)
                                sha256_hash = h.hexdigest()
                            except Exception:
                                sha256_hash = "Unavailable"
                                
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
                
            # Wait for next poll cycle
            time.sleep(self.poll_interval)
