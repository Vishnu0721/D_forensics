from PySide6.QtCore import QThread, Signal
from typing import Dict, Any
import time

class BaseCollector(QThread):
    """
    Abstract base class for all forensic telemetry collectors.
    Runs on a separate QThread so it doesn't block the GUI.
    """
    # Emits a normalized dictionary representing the raw event
    event_captured = Signal(dict)
    
    def __init__(self, case_id: str):
        super().__init__()
        self.case_id = case_id
        self._is_running = False
        
    def start_monitoring(self):
        self._is_running = True
        self.start()
        
    def stop_monitoring(self):
        # Collectors override run() with a poll loop, so QThread.quit() does nothing.
        self._is_running = False

    def interruptible_sleep(self, seconds: float, step: float = 0.1):
        remaining = seconds
        while self._is_running and remaining > 0:
            nap = step if remaining > step else remaining
            time.sleep(nap)
            remaining -= nap
        
    def run(self):
        """Override this in subclasses with the specific monitoring loop."""
        pass
