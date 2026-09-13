import os
import datetime
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFrame, QListWidget, QTableWidget,
    QTableWidgetItem, QGroupBox, QSplitter, QHeaderView, QTextEdit, QTabWidget,
    QComboBox, QFileDialog, QMessageBox, QDialog, QDialogButtonBox, QFormLayout
)
from PySide6.QtCore import Qt, QTimer, Slot, QThread
from PySide6.QtGui import QFont, QColor

from core.database import init_db, get_db, Case
from core.database.models import ForensicEvent, EvidenceArtifact
from core.services.graph import EvidenceGraph
from core.services.correlation import correlate_events, correlate_new_event
from core.services.reconstruction import reconstruct_incidents
from core.services.timeline import generate_timeline
from core.monitoring.manager import MonitoringManager
from core.services.classification import ClassificationEngine
from core.services.correlation import CorrelationWorker
from core.services.offline_analysis import OfflineAnalysisResult
from gui.offline_analysis_window import OfflineAnalysisDialog
from core.services.integrity import verify_integrity
from gui.graph_view import InteractiveGraphWidget
from PySide6.QtCore import Signal

class MainWindow(QMainWindow):
    batch_ready = Signal(list)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Evidence-Backed Forensic Monitor")
        self.setMinimumSize(1200, 800)

        # Initialize Database
        init_db()
        self.db = next(get_db())

        self.current_case = self.db.query(Case).first()
        if not self.current_case:
            self.current_case = Case(name="Default Case", description="Live Monitoring Case")
            self.db.add(self.current_case)
            self.db.commit()

        self.graph_db = EvidenceGraph(self.current_case.id)
        self.classification_engine = ClassificationEngine()

        self.is_monitoring = False
        self.event_buffer = []
        self.cached_suspicious = []
        self.cached_incidents = []
        self.graph_version = 0

        # Setup Monitoring Manager
        self.monitor = MonitoringManager(self.current_case.id)
        self.monitor.event_processed.connect(self.on_new_event)

        # Setup Correlation Worker
        self.correlation_thread = QThread()
        self.correlation_worker = CorrelationWorker(self.current_case.id, self.graph_db)
        self.correlation_worker.moveToThread(self.correlation_thread)
        self.correlation_thread.start()

        self.correlation_worker.correlations_found.connect(self.on_correlations_found)
        self.correlation_worker.graph_updated.connect(self.on_graph_updated)
        self.correlation_worker.suspicious_updated.connect(self.on_suspicious_updated)
        self.correlation_worker.incidents_updated.connect(self.on_incidents_updated)

        self.batch_ready.connect(self.correlation_worker.process_batch)

        self.evidence_classifications = {}

        # Offline analysis state
        self._current_offline_result: OfflineAnalysisResult = None

        self.setup_ui()

        # Setup timer for periodic UI stat polling
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self.poll_stats)
        self.update_timer.start(2000)

        # Setup timer for UI event stream batching
        self.ui_refresh_timer = QTimer(self)
        self.ui_refresh_timer.timeout.connect(self.process_event_buffer)
        self.ui_refresh_timer.start(500)

        # Setup timer for debounced graph saving
        self.save_timer = QTimer(self)
        self.save_timer.timeout.connect(self.graph_db.save)
        self.save_timer.start(10000)

        # Populate integrity table with existing evidence on startup
        self.populate_integrity_table()

        self.poll_stats()
        self.update_incidents_ui()

    def closeEvent(self, event):
        if self.is_monitoring:
            self.stop_monitoring()
        self.correlation_thread.quit()
        self.correlation_thread.wait()
        self.monitor.shutdown()
        self.graph_db.save()
        super().closeEvent(event)

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        # 1. Header
        header_layout = QHBoxLayout()
        title_label = QLabel("EVIDENCE-BACKED FORENSIC MONITOR")
        title_font = QFont("Segoe UI", 16, QFont.Weight.Bold)
        title_label.setFont(title_font)
        
        self.status_label = QLabel("● STATUS: IDLE")
        self.status_label.setStyleSheet("color: gray; font-weight: bold; font-size: 14px;")
        
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        header_layout.addWidget(self.status_label)
        main_layout.addLayout(header_layout)
        
        # 2. Controls Toolbar
        toolbar_layout = QHBoxLayout()
        
        self.btn_start = QPushButton("▶ START MONITORING")
        self.btn_start.setStyleSheet("background-color: #2e7d32; color: white; font-weight: bold; padding: 8px;")
        self.btn_start.clicked.connect(self.start_monitoring)
        
        self.btn_stop = QPushButton("■ STOP MONITORING")
        self.btn_stop.setStyleSheet("background-color: #c62828; color: white; font-weight: bold; padding: 8px;")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self.stop_monitoring)
        
        self.btn_verify = QPushButton("Verify Integrity")
        self.btn_verify.clicked.connect(self.verify_integrity)
        self.btn_offline = QPushButton("Offline Evidence (Advanced)")
        self.btn_offline.clicked.connect(self.on_offline_evidence_clicked)
        self.btn_offline.setStyleSheet("background-color: #1565c0; color: white; font-weight: bold; padding: 8px;")

        toolbar_layout.addWidget(self.btn_start)
        toolbar_layout.addWidget(self.btn_stop)
        toolbar_layout.addWidget(self.btn_verify)
        toolbar_layout.addWidget(self.btn_offline)
        toolbar_layout.addStretch()
        
        main_layout.addLayout(toolbar_layout)
        
        # Line separator
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        main_layout.addWidget(line)
        
        # 3. Stats Row
        stats_layout = QHBoxLayout()
        self.lbl_events = self.create_stat_widget("Events Captured", "0", stats_layout)
        self.lbl_evidence = self.create_stat_widget("Evidence Artifacts", "0", stats_layout)
        self.lbl_relations = self.create_stat_widget("Relationships", "0", stats_layout)
        self.lbl_incidents = self.create_stat_widget("Potential Incidents", "0", stats_layout)
        self.lbl_suspicious = self.create_stat_widget("Suspicious", "0", stats_layout)
        self.lbl_user_acts = self.create_stat_widget("User Activities", "0", stats_layout)
        self.lbl_bg_acts = self.create_stat_widget("Background", "0", stats_layout)
        main_layout.addLayout(stats_layout)
        
        # 4. Main Body Splitter (Left: Live Stream/Timeline, Right: Incidents/Integrity)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left Panel
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 5, 0)
        
        # Left Tabs
        self.left_tabs = QTabWidget()

        # Tab 1: Suspicious Activity
        self.suspicious_list = QListWidget()
        self.suspicious_list.setStyleSheet("background-color: #2b0000; color: #ff6b6b; font-family: Consolas; font-size: 13px;")
        self.suspicious_list.setWordWrap(True)
        self.suspicious_list.itemClicked.connect(self.on_suspicious_clicked)
        self.left_tabs.addTab(self.suspicious_list, "SUSPICIOUS ACTIVITY")

        # Tab 2: Event Stream
        all_events_widget = QWidget()
        all_events_layout = QVBoxLayout(all_events_widget)
        all_events_layout.setContentsMargins(0, 0, 0, 0)

        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Filter:"))
        self.event_filter_combo = QComboBox()
        self.event_filter_combo.addItems(["ALL EVENTS", "USER ACTIVITY", "BACKGROUND", "SUSPICIOUS", "CORRELATED", "UNKNOWN", "INCIDENT RELATED"])
        self.event_filter_combo.setCurrentText("USER ACTIVITY")
        self.event_filter_combo.currentTextChanged.connect(self.apply_event_filter)
        filter_layout.addWidget(self.event_filter_combo)
        filter_layout.addStretch()
        all_events_layout.addLayout(filter_layout)
        
        self.live_stream = QListWidget()
        self.live_stream.setStyleSheet("background-color: #1e1e1e; color: #00ff00; font-family: Consolas;")
        self.live_stream.itemClicked.connect(self.on_event_clicked)
        
        self.timeline_list = QListWidget()
        self.timeline_list.itemClicked.connect(self.on_event_clicked)
        
        all_events_layout.addWidget(QLabel("LIVE EVENT STREAM"))
        all_events_layout.addWidget(self.live_stream, stretch=2)
        all_events_layout.addWidget(QLabel("RECENT TIMELINE"))
        all_events_layout.addWidget(self.timeline_list, stretch=1)
        
        self.left_tabs.addTab(all_events_widget, "EVENT STREAM")
        
        left_layout.addWidget(self.left_tabs)
        
        splitter.addWidget(left_widget)
        
        # Right Panel
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(5, 0, 0, 0)
        
        # Incidents & Graph Tabs
        self.right_tabs = QTabWidget()
        
        # Tab 1: Interactive Graph
        self.graph_widget = InteractiveGraphWidget()
        self.right_tabs.addTab(self.graph_widget, "Evidence Graph")
        
        # Tab 2: Incident Reconstruction (Text)
        self.incident_view = QTextEdit()
        self.incident_view.setReadOnly(True)
        self.incident_view.setHtml("<p style='color: gray;'>Waiting for events...</p>")
        self.right_tabs.addTab(self.incident_view, "Incident Summary")
        
        # Tab 3: Event Details
        self.event_details_view = QTextEdit()
        self.event_details_view.setReadOnly(True)
        self.event_details_view.setHtml("<p style='color: gray;'>Select an event from the stream to view details.</p>")
        self.right_tabs.addTab(self.event_details_view, "Event Details")
        
        right_layout.addWidget(self.right_tabs, stretch=2)
        
        # Integrity
        grp_integrity = QGroupBox("EVIDENCE INTEGRITY")
        integrity_layout = QVBoxLayout(grp_integrity)
        self.integrity_table = QTableWidget(0, 6)
        self.integrity_table.setHorizontalHeaderLabels(["Evidence ID", "Source", "Original Hash", "Current Hash", "Status", "Time"])
        self.integrity_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        integrity_layout.addWidget(self.integrity_table)
        right_layout.addWidget(grp_integrity, stretch=1)
        
        splitter.addWidget(right_widget)
        
        # Add Splitter to main
        main_layout.addWidget(splitter, stretch=1)
        
    def create_stat_widget(self, title, value, parent_layout):
        container = QFrame()
        container.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        layout = QVBoxLayout(container)
        
        lbl_title = QLabel(title)
        lbl_title.setStyleSheet("color: gray; font-size: 12px;")
        lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        lbl_value = QLabel(value)
        lbl_value.setStyleSheet("font-size: 24px; font-weight: bold;")
        lbl_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        layout.addWidget(lbl_title)
        layout.addWidget(lbl_value)
        parent_layout.addWidget(container)
        return lbl_value

    def start_monitoring(self):
        self.is_monitoring = True
        self.status_label.setText("● STATUS: MONITORING")
        self.status_label.setStyleSheet("color: #2e7d32; font-weight: bold; font-size: 14px;")
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.live_stream.insertItem(0, ">>> Monitoring Initialized. Awaiting telemetry...")
        self.monitor.start_all()

    def stop_monitoring(self):
        self.is_monitoring = False
        self.status_label.setText("● STATUS: STOPPED")
        self.status_label.setStyleSheet("color: #c62828; font-weight: bold; font-size: 14px;")
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.live_stream.insertItem(0, ">>> Monitoring Stopped.")
        self.monitor.stop_all()

    def verify_integrity(self):
        from core.services.integrity import verify_all_evidence
        results = verify_all_evidence(self.db, self.current_case.id)
        
        self.integrity_table.setRowCount(0)
        
        for row, res in enumerate(results):
            self.integrity_table.insertRow(row)
            self.integrity_table.setItem(row, 0, QTableWidgetItem(res["evidence_id"]))
            self.integrity_table.setItem(row, 1, QTableWidgetItem(res["source"]))
            self.integrity_table.setItem(row, 2, QTableWidgetItem(res["original_hash"][:12] + "..."))
            self.integrity_table.setItem(row, 3, QTableWidgetItem(res["current_hash"][:12] + "..."))
            
            status_item = QTableWidgetItem(res["status"])
            if res["status"] == "VALID":
                status_item.setForeground(QColor("#2ecc71"))
            elif res["status"] == "MODIFIED":
                status_item.setForeground(QColor("#e74c3c"))
            else:
                status_item.setForeground(QColor("#f1c40f"))
                
            self.integrity_table.setItem(row, 4, status_item)
            self.integrity_table.setItem(row, 5, QTableWidgetItem(res["time"]))

    def _event_in_incidents(self, event) -> bool:
        if not self.cached_incidents or not event:
            return False
        eid = event.evidence_id
        eid_set = {eid}
        for inc in self.cached_incidents:
            inc_eids = set(inc.get("evidence_ids", []))
            if eid_set & inc_eids:
                return True
            for node in inc.get("nodes", []):
                pass
        return False

    def apply_event_filter(self):
        filter_text = self.event_filter_combo.currentText()

        # We use cached suspicious activities
        all_suspicious = self.cached_suspicious
        incidents = self.cached_incidents

        incident_evidence_ids = set()
        for inc in incidents:
            incident_evidence_ids.update(inc.get("evidence_ids", []))

        for i in range(self.live_stream.count()):
            item = self.live_stream.item(i)
            event = item.data(Qt.UserRole)
            if event:
                res = self.classification_engine.classify_event(event, self.graph_db.graph, all_suspicious, self.graph_version)
                show = False
                if filter_text == "ALL EVENTS":
                    show = True
                elif filter_text == "USER ACTIVITY" and res["classification"] == "USER_ACTIVITY":
                    show = True
                elif filter_text == "BACKGROUND" and res["classification"] == "BACKGROUND_ACTIVITY":
                    show = True
                elif filter_text == "SUSPICIOUS" and res["classification"] == "SUSPICIOUS_ACTIVITY":
                    show = True
                elif filter_text == "CORRELATED" and res["classification"] == "CORRELATED_ACTIVITY":
                    show = True
                elif filter_text == "UNKNOWN" and res["classification"] == "UNKNOWN":
                    show = True
                elif filter_text == "INCIDENT RELATED":
                    show = event.evidence_id in incident_evidence_ids
                item.setHidden(not show)

        for i in range(self.timeline_list.count()):
            item = self.timeline_list.item(i)
            event = item.data(Qt.UserRole)
            if event:
                res = self.classification_engine.classify_event(event, self.graph_db.graph, all_suspicious, self.graph_version)
                show = False
                if filter_text == "ALL EVENTS":
                    show = True
                elif filter_text == "USER ACTIVITY" and res["classification"] == "USER_ACTIVITY":
                    show = True
                elif filter_text == "BACKGROUND" and res["classification"] == "BACKGROUND_ACTIVITY":
                    show = True
                elif filter_text == "SUSPICIOUS" and res["classification"] == "SUSPICIOUS_ACTIVITY":
                    show = True
                elif filter_text == "CORRELATED" and res["classification"] == "CORRELATED_ACTIVITY":
                    show = True
                elif filter_text == "UNKNOWN" and res["classification"] == "UNKNOWN":
                    show = True
                elif filter_text == "INCIDENT RELATED":
                    show = event.evidence_id in incident_evidence_ids
                item.setHidden(not show)

    @Slot(object)
    def on_new_event(self, event: ForensicEvent):
        # Just buffer the event to avoid blocking UI
        self.event_buffer.append(event)
        
    def process_event_buffer(self):
        if not self.event_buffer:
            return
            
        import time
        start_time = time.perf_counter()
        
        from PySide6.QtWidgets import QListWidgetItem
        
        batch = self.event_buffer[:]
        self.event_buffer.clear()
        
        all_suspicious = self.cached_suspicious
        current_filter = self.event_filter_combo.currentText()
        
        for event in batch:
            desc = event.process or event.file or event.ip or ""
            
            if event.source_type == "filesystem" and event.event_type == "file_deleted":
                stream_text = f"{event.timestamp.strftime('%H:%M:%S')} FILESYSTEM    file_deleted    Filesystem delete event observed: {desc}"
            else:
                stream_text = f"{event.timestamp.strftime('%H:%M:%S')} {event.source_type.upper().ljust(10)} {event.event_type.ljust(15)} {desc}"
                
            item_live = QListWidgetItem(stream_text)
            item_live.setData(Qt.UserRole, event)
            self.live_stream.insertItem(0, item_live)
            
            item_timeline = QListWidgetItem(stream_text)
            item_timeline.setData(Qt.UserRole, event)
            self.timeline_list.insertItem(0, item_timeline)
            
            if current_filter != "ALL EVENTS":
                res = self.classification_engine.classify_event(event, self.graph_db.graph, all_suspicious, self.graph_version)
                is_visible = False
                if current_filter == "USER ACTIVITY" and res["classification"] == "USER_ACTIVITY": is_visible = True
                elif current_filter == "BACKGROUND" and res["classification"] == "BACKGROUND_ACTIVITY": is_visible = True
                elif current_filter == "SUSPICIOUS" and res["classification"] == "SUSPICIOUS_ACTIVITY": is_visible = True
                elif current_filter == "CORRELATED" and res["classification"] == "CORRELATED_ACTIVITY": is_visible = True
                elif current_filter == "UNKNOWN" and res["classification"] == "UNKNOWN": is_visible = True
                
                item_live.setHidden(not is_visible)
                item_timeline.setHidden(not is_visible)
                
            # Store classification for graph filtering
            if event.evidence_id not in self.evidence_classifications:
                res = self.classification_engine.classify_event(event, self.graph_db.graph, all_suspicious, self.graph_version)
                self.evidence_classifications[event.evidence_id] = res["classification"]
                
        # Truncate lists
        while self.live_stream.count() > 5000:
            self.live_stream.takeItem(5000)
        while self.timeline_list.count() > 500:
            self.timeline_list.takeItem(500)
            
        # Send batch to correlation worker
        self.batch_ready.emit(batch)
        
        elapsed = (time.perf_counter() - start_time) * 1000
        print(f"[PERF] GUI refresh: {elapsed:.2f} ms")
            
    @Slot(list)
    def on_correlations_found(self, relationships):
        self.graph_version += 1
        
    @Slot(object)
    def on_graph_updated(self, graph_snapshot):
        self.graph_version += 1
        self.graph_widget.update_graph(graph_snapshot, self.cached_suspicious, self.cached_incidents, self.evidence_classifications)
        self.poll_stats()
        
    @Slot(list)
    def on_suspicious_updated(self, suspicious):
        self.cached_suspicious = suspicious
        self.graph_widget.update_graph(self.graph_db.graph, self.cached_suspicious, self.cached_incidents, self.evidence_classifications)
        self.update_incidents_ui()
        
    @Slot(list)
    def on_incidents_updated(self, incidents):
        self.cached_incidents = incidents
        self.graph_widget.update_graph(self.graph_db.graph, self.cached_suspicious, self.cached_incidents, self.evidence_classifications)
        self.update_incidents_ui()
        
    def update_incidents_ui(self):
        # We don't update graph widget here directly, it's done via on_graph_updated
        
        all_suspicious = self.cached_suspicious
        
        # Update suspicious feed
        self.suspicious_list.clear()
        for act in all_suspicious:
            reason = act.get('reason', '')
            nodes = ", ".join(str(n) for n in act.get('nodes', []))
            score = act.get('score', 0)
            severity_label = "Potentially Suspicious"
            if score >= 0.8:
                severity_label = "Suspicious"
            elif score >= 0.5:
                severity_label = "Potentially Suspicious"
            else:
                severity_label = "Observed"

            ev_ids = act.get("evidence_ids", [])
            item_text = (f"[{severity_label} / Score: {score:.2f}] {act['rule_name']}\n"
                         f"Rule: {act.get('rule_name','')}\n"
                         f"Reason: {reason}\n"
                         f"Evidence IDs: {', '.join(ev_ids) if ev_ids else 'N/A'}\n"
                         f"Entities: {nodes}\n")
            from PySide6.QtWidgets import QListWidgetItem
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, act)
            self.suspicious_list.addItem(item)
        
        # Update text summary
        incidents = self.cached_incidents
        
        if not incidents:
            self.incident_view.setHtml("<p style='color: gray;'>Waiting for events...</p>")
            return
            
        html = "<h3>Identified Incidents</h3>"
        for inc in incidents:
            status_color = "red" if inc["status"] == "Requires Investigation" else "green"
            html += f"<div style='border: 1px solid gray; padding: 5px; margin-bottom: 5px;'>"
            html += f"<b>{inc['incident_id']}</b> - {len(inc['nodes'])} Entities - <span style='color: {status_color}'>{inc['status']}</span><br/>"
            html += f"<b>Time:</b> {inc.get('start_time')} - {inc.get('end_time')}<br/>"
            html += f"<b>Reason:</b> {inc.get('reconstruction_reason')}<br/>"
            
            if inc.get("evidence_ids"):
                html += f"<b>Evidence IDs:</b> {', '.join(inc['evidence_ids'])}<br/>"
                
            if inc.get("suspicious_activities"):
                html += "<b>Suspicious Activities:</b><br/>"
                for act in inc["suspicious_activities"]:
                    html += f"&nbsp;&nbsp;- {act['rule_name']} (Score: {act['score']})<br/>"
                    
            if inc.get("timeline"):
                html += "<b>Causal Timeline:</b><br/><pre style='background-color: #1e1e1e; color: #d4d4d4; padding: 5px;'>"
                html += inc["timeline"]
                html += "</pre>"
                
            html += "<b>Relationships:</b><br/>"
            for rel in inc['relationships']:
                html += f"&nbsp;&nbsp;[Conf: {rel['confidence']}] {rel['source']} &rarr; {rel['target']} ({rel.get('type', rel.get('relationship_type', ''))})<br/>"
            html += "</div>"
            
        self.incident_view.setHtml(html)

    def poll_stats(self):
        # Update summary statistics lightly
        
        # Don't do heavy DB queries on the main thread for count, 
        # instead just run quick counts.
        # SQLite handles simple count(*) fast enough, but we should not do it if it freezes. 
        # For small DBs it's fine.
        event_count = self.db.query(ForensicEvent).filter(ForensicEvent.case_id == self.current_case.id).count()
        ev_count = self.db.query(EvidenceArtifact).filter(EvidenceArtifact.case_id == self.current_case.id).count()
        
        self.lbl_events.setText(str(event_count))
        self.lbl_evidence.setText(str(ev_count))
        
        rel_count = self.graph_db.graph.number_of_edges()
        
        suspicious_count = len(self.cached_suspicious)
        inc_count = len(self.cached_incidents)
        
        self.lbl_relations.setText(str(rel_count))
        self.lbl_incidents.setText(str(inc_count))
        self.lbl_suspicious.setText(str(suspicious_count))
        
        user_acts = sum(1 for v in self.classification_engine._cache.values() if v["classification"] == "USER_ACTIVITY")
        bg_acts = sum(1 for v in self.classification_engine._cache.values() if v["classification"] == "BACKGROUND_ACTIVITY")
        
        self.lbl_user_acts.setText(str(user_acts))
        self.lbl_bg_acts.setText(str(bg_acts))

    @Slot(object)
    def on_event_clicked(self, item):
        event = item.data(Qt.UserRole)
        if not event:
            return
            
        all_suspicious = self.cached_suspicious
        res = self.classification_engine.classify_event(event, self.graph_db.graph, all_suspicious, self.graph_version)
        
        html = f"<h3>Event Details</h3>"
        
        def safe_get(val):
            return val if val else "Unavailable"
            
        html += f"<b>Event ID:</b> {safe_get(event.id)}<br/>"
        html += f"<b>Evidence ID:</b> {safe_get(event.evidence_id)}<br/>"
        html += f"<b>Timestamp:</b> {event.timestamp.strftime('%Y-%m-%d %H:%M:%S')}<br/>"
        html += f"<b>Source Type:</b> {safe_get(event.source_type)}<br/>"
        html += f"<b>Event Type:</b> {safe_get(event.event_type)}<br/>"
        html += f"<b>User:</b> {safe_get(event.user)}<br/>"
        html += f"<b>Host:</b> {safe_get(event.host)}<br/>"
        
        html += f"<b>Process:</b> {safe_get(event.process)}<br/>"
        html += f"<b>PID:</b> {safe_get(event.pid)}<br/>"
        html += f"<b>Parent PID:</b> {safe_get(event.parent_process)}<br/>"
        
        html += f"<b>File:</b> {safe_get(event.file)}<br/>"
        html += f"<b>Path:</b> {safe_get(event.path)}<br/>"
        
        # Check metadata_json for extra fields
        meta = event.metadata_json if event.metadata_json else {}
        old_path = meta.get("old_path")
        new_path = meta.get("new_path")
        if old_path:
            html += f"<b>Old Path:</b> {safe_get(old_path)}<br/>"
        if new_path:
            html += f"<b>New Path:</b> {safe_get(new_path)}<br/>"
            
        html += f"<b>IP:</b> {safe_get(event.ip)}<br/>"
        html += f"<b>Port:</b> {safe_get(event.port)}<br/>"
        
        cls_color = "white"
        if res['classification'] == 'SUSPICIOUS_ACTIVITY': cls_color = "red"
        elif res['classification'] == 'USER_ACTIVITY': cls_color = "lightgreen"
        elif res['classification'] == 'BACKGROUND_ACTIVITY': cls_color = "gray"
        elif res['classification'] == 'CORRELATED_ACTIVITY': cls_color = "orange"
        
        html += f"<br/><b>Classification:</b> <span style='color: {cls_color};'>{res['classification']}</span><br/>"
        html += f"<b>Attribution:</b> {res['attribution']}<br/>"
        html += f"<b>Classification Reason:</b> {res['reason']}<br/><br/>"
        
        # Check integrity and provenance
        integrity = "VALID"
        ev_artifact = self.db.query(EvidenceArtifact).filter_by(id=event.evidence_id).first()
        if ev_artifact:
            integrity = ev_artifact.integrity_status
            html += f"<b>Integrity status:</b> {integrity}<br/>"
            html += f"<hr style='border: 1px dashed #555;'>"
            html += f"<h4>Evidence Provenance</h4>"
            html += f"<b>Evidence ID:</b> {ev_artifact.id}<br/>"
            html += f"<b>Source File:</b> {ev_artifact.filename}<br/>"
            html += f"<b>Source Type:</b> {ev_artifact.source_type}<br/>"
            html += f"<b>SHA-256:</b> {ev_artifact.sha256_hash}<br/>"
            html += f"<b>Collected:</b> {ev_artifact.collection_timestamp.strftime('%Y-%m-%d %H:%M:%S') if ev_artifact.collection_timestamp else 'N/A'}<br/>"
        else:
            html += f"<b>Integrity status:</b> UNVERIFIABLE (EvidenceArtifact record not found)<br/>"
        # Switch to the Event Details tab (index 2)
        self.right_tabs.setCurrentIndex(2)

    def on_suspicious_clicked(self, item):
        data = item.data(Qt.UserRole)
        if not data:
            return
        act_id = data.get("activity_id")
        self.show_suspicious_provenance(data)

    def show_suspicious_provenance(self, act):
        html = f"<h3>Suspicious Finding: {act.get('rule_name','Unknown')}</h3>"
        html += f"<b>Activity ID:</b> {act.get('activity_id','N/A')}<br/>"
        html += f"<b>Severity/Confidence:</b> {act.get('score','N/A')}<br/>"
        html += f"<b>Observed Reason:</b> {act.get('reason','N/A')}<br/>"
        html += f"<b>Detected At:</b> {act.get('timestamp','N/A')}<br/><br/>"

        html += f"<hr style='border: 1px dashed #555;'>"
        html += f"<h4>Supporting Evidence Provenance</h4>"
        ev_ids = act.get("evidence_ids", [])
        if ev_ids:
            html += "<b>Evidence IDs:</b><ul>"
            for eid in ev_ids:
                html += f"<li>{eid}</li>"
            html += "</ul>"
            for eid in ev_ids:
                artifact = self.db.query(EvidenceArtifact).filter_by(id=eid).first()
                if artifact:
                    html += f"<hr/>"
                    html += f"<b>Evidence:</b> {artifact.filename}<br/>"
                    html += f"<b>&nbsp;&nbsp;ID:</b> {artifact.id}<br/>"
                    html += f"<b>&nbsp;&nbsp;SHA-256:</b> {artifact.sha256_hash}<br/>"
                    html += f"<b>&nbsp;&nbsp;Integrity:</b> {artifact.integrity_status}<br/>"

        rels = act.get("relationships", [])
        if rels:
            html += f"<br/><b>Related Relationships:</b><ul>"
            for r in rels:
                html += f"<li>{r['source']} &rarr; {r['target']} [{r.get('type','?')}] (conf: {r.get('confidence','?')})</li>"
            html += "</ul>"

        nodes = act.get("nodes", [])
        if nodes:
            html += f"<b>Related Entities:</b> {', '.join(str(n) for n in nodes)}<br/>"

        self.event_details_view.setHtml(html)
        self.right_tabs.setCurrentIndex(2)

    def populate_integrity_table(self):
        artifacts = self.db.query(EvidenceArtifact).filter(
            EvidenceArtifact.case_id == self.current_case.id
        ).all()

        self.integrity_table.setRowCount(0)

        now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        for row, art in enumerate(artifacts):
            self.integrity_table.insertRow(row)
            self.integrity_table.setItem(row, 0, QTableWidgetItem(art.id))
            source_label = f"{art.source_type} ({art.filename})" if art.filename else art.source_type
            self.integrity_table.setItem(row, 1, QTableWidgetItem(source_label))

            orig_hash_short = (art.sha256_hash[:16] + "...") if art.sha256_hash else "N/A"
            self.integrity_table.setItem(row, 2, QTableWidgetItem(orig_hash_short))
            self.integrity_table.setItem(row, 2, QTableWidgetItem(orig_hash_short))

            status = art.integrity_status or "UNVERIFIED"
            status_item = QTableWidgetItem(status)
            if status == "VALID":
                status_item.setForeground(QColor("#2ecc71"))
            elif status == "MODIFIED":
                status_item.setForeground(QColor("#e74c3c"))
            else:
                status_item.setForeground(QColor("#f1c40f"))
            self.integrity_table.setItem(row, 4, status_item)

            current_hash = "Pending verification"
            self.integrity_table.setItem(row, 3, QTableWidgetItem(current_hash))

            ts = art.collection_timestamp
            ts_str = ts.strftime("%Y-%m-%d %H:%M:%S") if ts else now
            self.integrity_table.setItem(row, 5, QTableWidgetItem(ts_str))

    def verify_integrity(self):
        from core.services.integrity import verify_all_evidence
        results = verify_all_evidence(self.db, self.current_case.id)

        self.integrity_table.setRowCount(0)

        for row, res in enumerate(results):
            self.integrity_table.insertRow(row)
            self.integrity_table.setItem(row, 0, QTableWidgetItem(res["evidence_id"]))
            self.integrity_table.setItem(row, 1, QTableWidgetItem(res["source"]))
            self.integrity_table.setItem(row, 2, QTableWidgetItem(res["original_hash"][:16] + "..."))
            self.integrity_table.setItem(row, 3, QTableWidgetItem(res["current_hash"][:16] + "..."))

            status_item = QTableWidgetItem(res["status"])
            if res["status"] == "VALID":
                status_item.setForeground(QColor("#2ecc71"))
            elif res["status"] == "MODIFIED":
                status_item.setForeground(QColor("#e74c3c"))
            else:
                status_item.setForeground(QColor("#f1c40f"))

            self.integrity_table.setItem(row, 4, status_item)
            self.integrity_table.setItem(row, 5, QTableWidgetItem(res["time"]))

    def on_offline_evidence_clicked(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Forensic Report / Evidence File",
            "",
            "Supported Files (*.json *.csv *.txt *.log *.evtx);;All Files (*.*)"
        )
        if not file_path:
            return

        if not os.path.exists(file_path):
            QMessageBox.critical(self, "Error", f"File not found: {file_path}")
            return

        dialog = OfflineAnalysisDialog(
            case_id=self.current_case.id,
            source_file_path=file_path,
            graph_db=self.graph_db,
            actor="investigator",
            parent=self
        )
        dialog.analysis_complete.connect(self.on_offline_analysis_complete)
        dialog.show()
        dialog.start_analysis()

    @Slot(object)
    def on_offline_analysis_complete(self, result: OfflineAnalysisResult):
        self._current_offline_result = result
        self.status_label.setText("● STATUS: IDLE")
        self.status_label.setStyleSheet("color: gray; font-weight: bold; font-size: 14px;")

        if not result.success:
            return

        self.cached_suspicious = result.suspicious_activities
        self.cached_incidents = result.incidents

        self._populate_offline_events(result)
        self._populate_suspicious_list(result)

        self.graph_version += 1

        ev_cls = {}
        for ev in result.events:
            r = self.classification_engine.classify_event(
                ev, self.graph_db.graph, self.cached_suspicious, self.graph_version
            )
            ev_cls[ev.evidence_id] = r["classification"]
        self.evidence_classifications.update(ev_cls)

        self.graph_widget.update_graph(
            self.graph_db.graph,
            self.cached_suspicious,
            self.cached_incidents,
            self.evidence_classifications,
        )

        self.update_incidents_ui()
        self.populate_integrity_table()
        self.poll_stats()

        self.apply_event_filter()

    def _populate_offline_events(self, result: OfflineAnalysisResult):
        from PySide6.QtWidgets import QListWidgetItem

        all_suspicious = self.cached_suspicious
        current_filter = self.event_filter_combo.currentText()

        for event in result.events:
            desc = event.process or event.file or event.ip or ""
            stream_text = (f"{event.timestamp.strftime('%H:%M:%S')} "
                           f"{event.source_type.upper().ljust(10)} "
                           f"{event.event_type.ljust(15)} {desc}")

            item_live = QListWidgetItem(stream_text)
            item_live.setData(Qt.UserRole, event)
            self.live_stream.insertItem(0, item_live)

            item_timeline = QListWidgetItem(stream_text)
            item_timeline.setData(Qt.UserRole, event)
            self.timeline_list.insertItem(0, item_timeline)

            if current_filter != "ALL EVENTS":
                res = self.classification_engine.classify_event(
                    event, self.graph_db.graph, all_suspicious, self.graph_version
                )
                is_visible = False
                if current_filter == "USER ACTIVITY" and res["classification"] == "USER_ACTIVITY":
                    is_visible = True
                elif current_filter == "BACKGROUND" and res["classification"] == "BACKGROUND_ACTIVITY":
                    is_visible = True
                elif current_filter == "SUSPICIOUS" and res["classification"] == "SUSPICIOUS_ACTIVITY":
                    is_visible = True
                elif current_filter == "CORRELATED" and res["classification"] == "CORRELATED_ACTIVITY":
                    is_visible = True
                elif current_filter == "UNKNOWN" and res["classification"] == "UNKNOWN":
                    is_visible = True
                elif current_filter == "INCIDENT RELATED":
                    iids = set()
                    for inc in self.cached_incidents:
                        iids.update(inc.get("evidence_ids", []))
                    is_visible = event.evidence_id in iids

                item_live.setHidden(not is_visible)
                item_timeline.setHidden(not is_visible)

        while self.live_stream.count() > 10000:
            self.live_stream.takeItem(10000)
        while self.timeline_list.count() > 1000:
            self.timeline_list.takeItem(1000)

    def _populate_suspicious_list(self, result: OfflineAnalysisResult):
        from PySide6.QtWidgets import QListWidgetItem
        for act in result.suspicious_activities:
            reason = act.get('reason', '')
            nodes = ", ".join(str(n) for n in act.get('nodes', []))
            score = act.get('score', 0)
            severity_label = "Potentially Suspicious"
            if score >= 0.8:
                severity_label = "Suspicious"
            elif score >= 0.5:
                severity_label = "Potentially Suspicious"
            else:
                severity_label = "Observed"

            ev_ids = act.get("evidence_ids", [])
            item_text = (f"[{severity_label} / Score: {score:.2f}] {act['rule_name']}\n"
                         f"Rule: {act.get('rule_name','')}\n"
                         f"Reason: {reason}\n"
                         f"Evidence IDs: {', '.join(ev_ids) if ev_ids else 'N/A'}\n"
                         f"Entities: {nodes}\n")
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, act)
            self.suspicious_list.addItem(item)
