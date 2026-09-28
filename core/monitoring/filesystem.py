import os
import time
from collections import deque
from datetime import datetime
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from core.paths import DB_PATH, DATA_DIR, LOGS_DIR, PROJECT_ROOT, DEBUG_LOGGING
from .base import BaseCollector

# Upper bound on filesystem events forwarded per second (all types combined).
# Bulk operations (unzipping, copying folders) beyond this are counted and dropped
# so evidence writes cannot saturate the disk, database, and GUI.
MAX_EVENTS_PER_SECOND = 40
MAX_MODIFIED_PER_SECOND = 25

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
        self.exclusions = [e.lower() for e in (exclusions or [])]
        self._last_emit = {}
        self._recent_times = deque()
        self._recent_modified = deque()
        self._dropped = 0
        self._last_drop_report = 0.0
        try:
            self._user = os.getlogin()
        except Exception:
            self._user = None

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

    def _is_excluded(self, abs_path: str) -> bool:
        for excl in self.exclusions:
            if abs_path == excl or abs_path.startswith(excl + os.sep):
                return True
        return False

    def _count_drop(self, now: float):
        self._dropped += 1
        if now - self._last_drop_report >= 5.0:
            print(f"FilesystemCollector: rate limit dropped {self._dropped} events in the last few seconds")
            self._dropped = 0
            self._last_drop_report = now

    def _should_drop(self, event_type: str, abs_path: str) -> bool:
        now = time.time()
        while self._recent_times and now - self._recent_times[0] >= 1.0:
            self._recent_times.popleft()
        while self._recent_modified and now - self._recent_modified[0] >= 1.0:
            self._recent_modified.popleft()
        if len(self._last_emit) > 4000:
            self._last_emit.clear()

        last = self._last_emit.get(abs_path)
        if last and last[0] == event_type and (now - last[1]) < 1.5:
            return True

        if len(self._recent_times) >= MAX_EVENTS_PER_SECOND or (
            event_type == "file_modified" and len(self._recent_modified) >= MAX_MODIFIED_PER_SECOND
        ):
            self._count_drop(now)
            return True

        self._last_emit[abs_path] = (event_type, now)
        self._recent_times.append(now)
        if event_type == "file_modified":
            self._recent_modified.append(now)
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
        
        # Never record the application's own database/evidence writes (feedback loop)
        if self._is_excluded(abs_path):
            return

        if self._should_drop(event_type, abs_path):
            return
            
        user = self._user
            
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
        
        if DEBUG_LOGGING:
            print(f"[FS] {event_type}: {abs_path}")
            
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
        
        if self._is_excluded(abs_new_path) or self._is_excluded(abs_old_path):
            return

        if self._should_drop(event_type, abs_new_path):
            return
            
        user = self._user
            
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
        
        if DEBUG_LOGGING:
            print(f"[FS] MOVED: {abs_old_path} -> {abs_new_path}")
        
        self.callback(data)

class FilesystemCollector(BaseCollector):
    def __init__(self, case_id: str, monitored_dirs=None):
        super().__init__(case_id)
        self.observer = None
        self.monitored_dirs = monitored_dirs
        
        # The application's own runtime files, excluded to prevent a feedback loop
        # (every evidence write would otherwise produce a new filesystem event).
        ocsi_path = os.path.join(PROJECT_ROOT, "OCSI.db")
        self.exclusions = [
            DB_PATH,
            DB_PATH + "-wal",
            DB_PATH + "-shm",
            DB_PATH + "-journal",
            ocsi_path,
            ocsi_path + "-wal",
            ocsi_path + "-shm",
            DATA_DIR,
            LOGS_DIR,
        ]

    @staticmethod
    def default_watch_targets():
        """(directory, recursive) pairs for user-facing locations.

        AppData, TEMP and System32 are intentionally not watched: they change
        constantly in the background and made the whole system unresponsive.
        """
        # USERPROFILE only exists on Windows; the home folder has the same layout elsewhere.
        user_profile = os.environ.get('USERPROFILE', '') or os.path.expanduser('~')
        onedrive = os.environ.get('OneDrive', '')
        targets = []
        for base in (user_profile, onedrive):
            if not base:
                continue
            for name in ("Downloads", "Desktop", "Documents"):
                targets.append((os.path.join(base, name), True))
        appdata = os.environ.get('APPDATA', '')
        if appdata:
            # Autostart persistence location; small and rarely written.
            targets.append((os.path.join(appdata, "Microsoft", "Windows", "Start Menu", "Programs", "Startup"), False))

        seen = set()
        unique = []
        for directory, recursive in targets:
            key = os.path.normcase(os.path.abspath(directory))
            if key in seen:
                continue
            seen.add(key)
            unique.append((directory, recursive))
        return unique
        
    def run(self):
        if self.monitored_dirs is None:
            watch_targets = self.default_watch_targets()
        else:
            watch_targets = [(d, True) for d in self.monitored_dirs]
        
        self.observer = Observer()
        handler = ForensicFileEventHandler(self.event_captured.emit, exclusions=self.exclusions)
        
        watched = 0
        for directory, recursive in watch_targets:
            if os.path.isdir(directory):
                try:
                    self.observer.schedule(handler, directory, recursive=recursive)
                    watched += 1
                except Exception as e:
                    print(f"FilesystemCollector: cannot watch {directory}: {e}")
        if watched == 0:
            print("FilesystemCollector: no folders available to watch.")
                
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
