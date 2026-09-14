import os
import time
from datetime import datetime
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from .base import BaseCollector

NOISY_PATH_MARKERS = (
    "\\appdata\\local\\packages\\",
    "\\appdata\\roaming\\cursor\\",
    "\\appdata\\roaming\\code\\",
    "\\appdata\\local\\google\\chrome\\user data\\",
    "\\appdata\\local\\microsoft\\edge\\user data\\",
    "\\appdata\\local\\mozilla\\firefox\\",
    "\\appdata\\local\\pip\\",
    "\\__pycache__\\",
    "\\node_modules\\",
    "\\.git\\",
    "\\sentry\\",
    "\\code cache\\",
    "\\gpucache\\",
    "\\gpuCache\\",
    "\\service worker\\",
    "\\ebwebview\\",
    "\\cursor\\snapshots\\",
    "\\windows\\system32\\logfiles\\",
    "\\windows\\system32\\wbem\\logs\\",
    "\\windows\\system32\\winevt\\",
    "\\inetcache\\",
)

NOISY_NAME_PREFIXES = ("~", ".")
NOISY_EXTENSIONS = (
    ".tmp", ".temp", ".lock", ".ldb", ".log", ".pyc", ".pyo",
    ".pack", ".idx", ".wal", ".shm", ".journal",
)


class ForensicFileEventHandler(FileSystemEventHandler):
    def __init__(self, callback, exclusions=None):
        super().__init__()
        self.callback = callback
        self.exclusions = exclusions or []
        self._last_emit = {}
        self._recent_times = []

    def _is_noisy_path(self, abs_path: str) -> bool:
        path_lower = abs_path.lower()
        for marker in NOISY_PATH_MARKERS:
            if marker in path_lower:
                return True
        filename = os.path.basename(path_lower)
        _, ext = os.path.splitext(filename)
        in_high_churn_dir = (
            "\\appdata\\" in path_lower
            or "\\temp\\" in path_lower
            or "\\windows\\system32\\" in path_lower
        )
        if in_high_churn_dir and ext in NOISY_EXTENSIONS:
            return True
        return False

    def _should_drop(self, event_type: str, abs_path: str) -> bool:
        now = time.time()
        self._recent_times = [t for t in self._recent_times if now - t < 1.0]
        if len(self._last_emit) > 4000:
            self._last_emit.clear()

        last = self._last_emit.get(abs_path)
        if last and last[0] == event_type and (now - last[1]) < 1.5:
            return True

        if event_type == "file_modified" and len(self._recent_times) > 25:
            return True

        self._last_emit[abs_path] = (event_type, now)
        self._recent_times.append(now)
        return False
        
    def on_created(self, event):
        if not event.is_directory:
            self._emit("file_created", event.src_path)
            
    def on_modified(self, event):
        if not event.is_directory:
            self._emit("file_modified", event.src_path)
            
    def on_moved(self, event):
        if not event.is_directory:
            dest_path = getattr(event, 'dest_path', '')
            if dest_path:
                self._emit_moved("file_moved", event.src_path, dest_path)
            else:
                self._emit("file_moved", event.src_path)
            
    def on_deleted(self, event):
        if not event.is_directory:
            self._emit("file_deleted", event.src_path)
            
    def _emit(self, event_type, path):
        filename = os.path.basename(path)
        
        # Avoid spamming temporary or hidden files common in windows
        if filename.startswith('~') or filename.startswith('.') or filename.endswith('.tmp'):
            return
            
        abs_path = os.path.abspath(path).lower()

        if self._is_noisy_path(abs_path):
            return
        
        # Check exclusions (infrastructure)
        for excl in self.exclusions:
            excl_lower = excl.lower()
            if abs_path == excl_lower or abs_path.startswith(excl_lower + os.sep):
                print(f"FILESYSTEM EVENT IGNORED:\npath={abs_path}\nreason=application infrastructure")
                return

        if self._should_drop(event_type, abs_path):
            return
            
        try:
            user = os.getlogin()
        except:
            user = None
            
        parent_dir = os.path.dirname(abs_path)
        _, ext = os.path.splitext(filename)
        
        file_size = 0
        if os.path.exists(abs_path):
            try:
                file_size = os.path.getsize(abs_path)
            except:
                pass
                
        # File type classification logic
        ext_lower = ext.lower()
        file_type = "Unknown"
        if ext_lower in ['.exe', '.dll', '.sys', '.bat', '.cmd', '.ps1', '.msi']:
            file_type = "Executable"
        elif ext_lower in ['.doc', '.docx', '.pdf', '.txt', '.csv', '.xlsx', '.xls', '.ppt', '.pptx']:
            file_type = "Document"
        elif ext_lower in ['.zip', '.rar', '.7z', '.tar', '.gz']:
            file_type = "Archive"
        elif ext_lower in ['.db', '.ldb', '.sqlite', '.sqlite3', '.db-wal', '.db-shm', '.log']:
            if ext_lower == '.log':
                file_type = "Log"
            else:
                file_type = "Database/Storage"
        elif ext_lower == '.tmp' or ext_lower == '.temp':
            file_type = "Temporary"
        elif ext_lower == '.lnk':
            file_type = "Shortcut"
            
        data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "source_type": "filesystem",
            "event_type": event_type,
            "file": filename,
            "path": abs_path,
            "parent_directory": parent_dir,
            "file_extension": ext_lower,
            "file_size": file_size,
            "file_type": file_type,
            "process": "unavailable",
            "user": user
        }
        
        if event_type == "file_created":
            print(f"[FS] CREATED: {abs_path}")
        elif event_type == "file_deleted":
            print(f"[FS] DELETED: {abs_path}")
        elif event_type == "file_modified":
            print(f"[FS] MODIFIED: {abs_path}")
            
        self.callback(data)
        
    def _emit_moved(self, event_type, old_path, new_path):
        filename = os.path.basename(new_path)
        
        # Avoid spamming temporary or hidden files common in windows
        if filename.startswith('~') or filename.startswith('.') or filename.endswith('.tmp'):
            return
            
        abs_old_path = os.path.abspath(old_path).lower()
        abs_new_path = os.path.abspath(new_path).lower()

        if self._is_noisy_path(abs_new_path) or self._is_noisy_path(abs_old_path):
            return
        
        # Check exclusions (infrastructure)
        for excl in self.exclusions:
            excl_lower = excl.lower()
            if abs_new_path == excl_lower or abs_new_path.startswith(excl_lower + os.sep) or abs_old_path == excl_lower or abs_old_path.startswith(excl_lower + os.sep):
                print(f"FILESYSTEM EVENT IGNORED:\npath={abs_new_path}\nreason=application infrastructure")
                return

        if self._should_drop(event_type, abs_new_path):
            return
            
        try:
            user = os.getlogin()
        except:
            user = None
            
        parent_dir = os.path.dirname(abs_new_path)
        _, ext = os.path.splitext(filename)
        
        file_size = 0
        if os.path.exists(abs_new_path):
            try:
                file_size = os.path.getsize(abs_new_path)
            except:
                pass
                
        # File type classification logic
        ext_lower = ext.lower()
        file_type = "Unknown"
        if ext_lower in ['.exe', '.dll', '.sys', '.bat', '.cmd', '.ps1', '.msi']:
            file_type = "Executable"
        elif ext_lower in ['.doc', '.docx', '.pdf', '.txt', '.csv', '.xlsx', '.xls', '.ppt', '.pptx']:
            file_type = "Document"
        elif ext_lower in ['.zip', '.rar', '.7z', '.tar', '.gz']:
            file_type = "Archive"
        elif ext_lower in ['.db', '.ldb', '.sqlite', '.sqlite3', '.db-wal', '.db-shm', '.log']:
            if ext_lower == '.log':
                file_type = "Log"
            else:
                file_type = "Database/Storage"
        elif ext_lower == '.tmp' or ext_lower == '.temp':
            file_type = "Temporary"
        elif ext_lower == '.lnk':
            file_type = "Shortcut"
            
        data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "source_type": "filesystem",
            "event_type": event_type,
            "file": filename,
            "path": abs_new_path,
            "old_path": abs_old_path,
            "parent_directory": parent_dir,
            "file_extension": ext_lower,
            "file_size": file_size,
            "file_type": file_type,
            "process": "unavailable",
            "user": user
        }
        
        print(f"[FS] MOVED: {abs_old_path} -> {abs_new_path}")
        
        self.callback(data)

class FilesystemCollector(BaseCollector):
    def __init__(self, case_id: str, monitored_dirs=None):
        super().__init__(case_id)
        self.observer = None
        self.monitored_dirs = monitored_dirs
        
        # Identify the actual runtime paths used by the application's infrastructure
        # to prevent a filesystem feedback loop.
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        
        db_path = os.path.join(project_root, "forensics.db")
        ocsi_path = os.path.join(project_root, "OCSI.db")
        evidence_dir = os.path.join(project_root, "data", "evidence")
        logs_dir = os.path.join(project_root, "logs")
        
        self.exclusions = [
            db_path,
            db_path + "-wal",
            db_path + "-shm",
            ocsi_path,
            ocsi_path + "-wal",
            ocsi_path + "-shm",
            evidence_dir,
            logs_dir
        ]
        
    def run(self):
        user_profile = os.environ.get('USERPROFILE', '')
        if not user_profile:
            print("FilesystemCollector: Could not determine USERPROFILE.")
            return
            
        if self.monitored_dirs is None:
            watch_dirs = [
                os.path.join(user_profile, "Downloads"),
                os.path.join(user_profile, "Desktop"),
                os.path.join(user_profile, "Documents"),
                os.path.join(user_profile, "AppData"),
                os.environ.get('TEMP', os.path.join(user_profile, "AppData", "Local", "Temp")),
                os.path.join(os.environ.get('SystemRoot', 'C:\\Windows'), 'System32')
            ]
        else:
            watch_dirs = self.monitored_dirs
        
        self.observer = Observer()
        handler = ForensicFileEventHandler(self.event_captured.emit, exclusions=self.exclusions)
        
        for directory in watch_dirs:
            if os.path.exists(directory):
                self.observer.schedule(handler, directory, recursive=True)
                
        self.observer.start()
        
        # Keep the QThread alive while monitoring
        while self._is_running:
            time.sleep(0.2)
            
        if self.observer:
            self.observer.stop()
            self.observer.join(timeout=2)

    def stop_monitoring(self):
        self._is_running = False
        observer = self.observer
        if observer is not None:
            try:
                observer.stop()
            except Exception:
                pass
