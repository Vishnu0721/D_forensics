import os
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QTextEdit, QPushButton, QHBoxLayout,
    QTabWidget, QWidget, QListWidget, QListWidgetItem
)
from PySide6.QtCore import Qt, Slot, QThread, Signal
from PySide6.QtGui import QFont, QColor

from core.services.offline_analysis import OfflineAnalysisWorker, OfflineAnalysisResult
from gui.graph_view import InteractiveGraphWidget

class OfflineAnalysisDialog(QDialog):
    analysis_complete = Signal(object)  # Emits OfflineAnalysisResult

    def __init__(self, case_id, source_file_path, graph_db, actor, parent=None):
        super().__init__(parent)
        self.case_id = case_id
        self.source_file_path = source_file_path
        self.graph_db = graph_db
        self.actor = actor
        
        self.setWindowTitle("Offline Forensic Analysis Dashboard")
        self.setMinimumSize(1000, 700)
        
        self._offline_thread = None
        self._offline_worker = None
        self._result = None

        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Header
        header_layout = QHBoxLayout()
        header = QLabel("OFFLINE FORENSIC ANALYSIS")
        header.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        header.setStyleSheet("color: #1565c0;")
        header_layout.addWidget(header)
        
        self.status_label = QLabel(f"File: {os.path.basename(self.source_file_path)}")
        self.status_label.setStyleSheet("color: gray; font-family: Consolas;")
        header_layout.addWidget(self.status_label, stretch=1)
        
        self.progress_label = QLabel("Initializing...")
        self.progress_label.setStyleSheet("color: #00bcd4; font-family: Consolas; font-weight: bold;")
        header_layout.addWidget(self.progress_label)
        layout.addLayout(header_layout)

        # Tab Widget
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, stretch=1)
        
        # Tab 1: Overview (Summary)
        self.summary_view = QTextEdit()
        self.summary_view.setReadOnly(True)
        self.summary_view.setHtml("<p style='color: gray;'>Analysis in progress...</p>")
        self.tabs.addTab(self.summary_view, "Overview")
        
        # Tab 2: Suspicious Events
        self.suspicious_list = QListWidget()
        self.suspicious_list.setStyleSheet("background-color: #2b0000; color: #ff6b6b; font-family: Consolas; font-size: 13px;")
        self.suspicious_list.setWordWrap(True)
        self.tabs.addTab(self.suspicious_list, "Suspicious Events")
        
        # Tab 3: Evidence Graph
        self.graph_widget = InteractiveGraphWidget()
        self.tabs.addTab(self.graph_widget, "Evidence Graph")
        
        # Tab 4: Incident Reconstruction
        self.incident_view = QTextEdit()
        self.incident_view.setReadOnly(True)
        self.incident_view.setStyleSheet("background-color: #0d1117; color: #c9d1d9; font-family: Consolas; font-size: 13px;")
        self.incident_view.setHtml("<p style='color: gray;'>Waiting for analysis...</p>")
        self.tabs.addTab(self.incident_view, "Incident Reconstruction")

        # Footer
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.btn_close = QPushButton("Close")
        self.btn_close.clicked.connect(self.accept)
        self.btn_close.setEnabled(False)  # Disable until finished
        self.btn_close.setStyleSheet("background-color: #333333; color: white; padding: 5px 15px;")
        btn_layout.addWidget(self.btn_close)
        layout.addLayout(btn_layout)

    def start_analysis(self):
        self._offline_thread = QThread(self)
        self._offline_worker = OfflineAnalysisWorker(
            case_id=self.case_id,
            source_file_path=self.source_file_path,
            graph_db=self.graph_db,
            actor=self.actor,
        )
        self._offline_worker.moveToThread(self._offline_thread)
        
        self._offline_thread.started.connect(self._offline_worker.run)
        self._offline_worker.progress.connect(self.on_progress)
        self._offline_worker.analysis_complete.connect(self.on_complete)
        self._offline_worker.analysis_error.connect(self.on_error)
        
        self._offline_worker.analysis_complete.connect(self._offline_thread.quit)
        self._offline_worker.analysis_error.connect(self._offline_thread.quit)
        self._offline_thread.finished.connect(self.on_thread_finished)
        
        self._offline_thread.start()

    @Slot(str)
    def on_progress(self, msg: str):
        self.progress_label.setText(msg)

    @Slot(object)
    def on_error(self, err: str):
        self.status_label.setText(f"<span style='color: red;'>ERROR: {err}</span>")
        self.summary_view.setHtml(f"<p style='color: red;'>{err}</p>")
        self.btn_close.setEnabled(True)
        self.btn_close.setStyleSheet("background-color: #1565c0; color: white; padding: 5px 15px;")

    @Slot(object)
    def on_complete(self, result: OfflineAnalysisResult):
        self._result = result
        if not result.success:
            if result.evidence:
                self.status_label.setText(
                    f"<span style='color: #e67e22;'>Evidence preserved but analysis limited.</span>"
                )
            else:
                self.status_label.setText(
                    f"<span style='color: red;'>Analysis failed.</span>"
                )
        else:
            self.status_label.setText("<span style='color: #2e7d32;'>Analysis Complete.</span>")
            
        self._render_summary(result)
        self._populate_suspicious_list(result)
        self._populate_graph(result)
        self._populate_incidents(result)

        self.btn_close.setEnabled(True)
        self.btn_close.setStyleSheet("background-color: #1565c0; color: white; font-weight: bold; padding: 5px 15px;")
        
        # Emit so main window can process the result
        self.analysis_complete.emit(result)

    def on_thread_finished(self):
        if self._offline_worker:
            self._offline_worker.deleteLater()
            self._offline_worker = None
        if self._offline_thread:
            self._offline_thread.deleteLater()
            self._offline_thread = None

    def _render_summary(self, result: OfflineAnalysisResult):
        summ = result.summary_dict()
        html = "<h3 style='color: #1565c0;'>OFFLINE FORENSIC ANALYSIS SUMMARY</h3>"

        if result.evidence:
            html += "<div style='background-color: #0d1117; padding: 10px; border: 1px solid #30363d; border-radius: 4px; margin-bottom: 10px;'>"
            html += f"<table style='width:100%;'>"
            html += f"<tr><td><b>Evidence File:</b></td><td style='font-family: Consolas;'>{summ.get('filename')}</td></tr>"
            html += f"<tr><td><b>Evidence ID:</b></td><td style='font-family: Consolas; color: #f1c40f;'>{summ.get('evidence_id')}</td></tr>"
            html += f"<tr><td><b>Format Detected:</b></td><td style='font-family: Consolas;'>{summ.get('format_detected')}</td></tr>"
            html += f"<tr><td><b>Source Type:</b></td><td style='font-family: Consolas;'>{summ.get('source_type_detected')}</td></tr>"
            html += f"<tr><td><b>SHA-256:</b></td><td style='font-family: Consolas; font-size: 11px; word-break: break-all; color: #2ecc71;'>{summ.get('sha256')}</td></tr>"
            html += f"</table>"
            html += "</div>"

        if not result.success:
            html += f"<div style='background-color: #2b0000; padding: 8px; border: 1px solid #e74c3c; margin-bottom: 10px;'>"
            html += f"<b style='color: #e74c3c;'>Issue:</b> {result.error_message or 'Unknown'}"
            html += "</div>"
            self.summary_view.setHtml(html)
            return

        html += "<div style='display: flex; flex-wrap: wrap; gap: 8px;'>"
        def _stat(label, value, color="#ffffff"):
            return (f"<div style='background-color: #161b22; padding: 8px 12px; border: 1px solid #30363d; border-radius: 4px; min-width: 130px;'>"
                    f"<div style='color: gray; font-size: 11px;'>{label}</div>"
                    f"<div style='color: {color}; font-size: 22px; font-weight: bold;'>{value}</div>"
                    f"</div>")
        html += _stat("Events Extracted", summ.get("records_parsed"), "#00bcd4")
        html += _stat("Suspicious Activities", summ.get("suspicious_activities"), "#e74c3c")
        html += _stat("Relationships", summ.get("relationships"), "#f39c12")
        html += _stat("Potential Incidents", summ.get("incidents"), "#9b59b6")
        cc = summ.get("classification_counts", {})
        html += _stat("User Activities", cc.get("USER_ACTIVITY", 0), "#2ecc71")
        html += _stat("Background", cc.get("BACKGROUND_ACTIVITY", 0), "#95a5a6")
        html += _stat("Correlated", cc.get("CORRELATED_ACTIVITY", 0), "#e67e22")
        html += _stat("Unknown", cc.get("UNKNOWN", 0), "#7f8c8d")
        html += "</div>"

        if result.parse_result and result.parse_result.records_failed > 0:
            html += f"<p style='color: #e67e22; margin-top: 10px;'>"
            html += f"Note: {result.parse_result.records_parsed} events parsed, "
            html += f"{result.parse_result.records_failed} records could not be parsed."
            html += "</p>"

        self.summary_view.setHtml(html)

    def _populate_suspicious_list(self, result: OfflineAnalysisResult):
        self.suspicious_list.clear()
        if not result.suspicious_activities:
            self.suspicious_list.addItem("No suspicious activities detected in this report.")
            return

        for act in result.suspicious_activities:
            reason = act.get("reason", "Unknown")
            evt = act.get("event")
            desc = ""
            if evt:
                desc = f"[{evt.get('timestamp', '')}] {evt.get('source_type', '')} - {evt.get('event_type', '')}"
            item_text = f"WARNING: {reason}\n{desc}\n"
            item = QListWidgetItem(item_text)
            self.suspicious_list.addItem(item)

    def _populate_graph(self, result: OfflineAnalysisResult):
        self.graph_widget.update_graph(
            self.graph_db.graph,
            result.suspicious_activities,
            result.incidents,
            {}  
        )

    def _populate_incidents(self, result: OfflineAnalysisResult):
        if not result.incidents:
            self.incident_view.setHtml("<p style='color: #2ecc71;'>No correlated incidents found in this report.</p>")
            return
            
        try:
            html = "<h3>Reconstructed Incidents</h3>"
            for inc in result.incidents:
                incident_id = inc.get("incident_id", "Unknown")
                status = inc.get("status", "Unknown")
                node_count = len(inc.get("nodes", []))
                timeline = inc.get("timeline", "No timeline available")
                
                timeline_html = timeline.replace("\n", "<br/>")
                
                html += f"<div style='border: 1px solid #30363d; padding: 10px; margin-bottom: 10px;'>"
                html += f"<h4 style='color: #e74c3c; margin-top: 0;'>{incident_id}</h4>"
                html += f"<p><b>Status:</b> {status} | <b>Nodes Involved:</b> {node_count}</p>"
                html += f"<div style='background-color: #161b22; padding: 8px; font-family: Consolas;'>"
                html += f"{timeline_html}"
                html += f"</div></div>"
            
            self.incident_view.setHtml(html)
        except Exception as e:
            self.incident_view.setHtml(f"<p style='color: red;'>Error rendering incidents: {str(e)}</p>")
