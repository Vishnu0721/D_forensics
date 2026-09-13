from PySide6.QtCore import QThread, Signal
from typing import Dict, Any

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
        self._is_running = False
        self.quit()
        
    def run(self):
        """Override this in subclasses with the specific monitoring loop."""
        pass
