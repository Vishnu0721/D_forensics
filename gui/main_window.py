import os
import datetime
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFrame, QListWidget, QTableWidget,
    QTableWidgetItem, QSplitter, QHeaderView, QTextEdit, QTabWidget,
    QComboBox, QFileDialog, QMessageBox, QDialog
)
from PySide6.QtCore import Qt, QTimer, Slot, QThread, Signal
from PySide6.QtGui import QFont, QColor

from core.database import init_db, get_db, Case
from core.database.models import ForensicEvent, EvidenceArtifact
from core.services.graph import EvidenceGraph
from core.monitoring.manager import MonitoringManager
from core.services.classification import ClassificationEngine
from core.services.correlation import CorrelationWorker
from core.services.offline_analysis import OfflineAnalysisResult
from gui.offline_analysis_window import OfflineAnalysisDialog
from gui.graph_view import InteractiveGraphWidget
from gui.event_language import (
    FILTER_OPTIONS,
    FILTER_LABEL_TO_KEY,
    format_event_sentence,
    format_event_summary_html,
    format_event_advanced_html,
    event_item_color,
    filter_matches,
)
from gui.incident_language import (
    format_suspicious_item,
    format_suspicious_detail_html,
    format_incidents_page_html,
    severity_color,
)
from gui.integrity_ui import human_source_label, map_status_display, STATUS_HELP
from gui.quick_tour import QuickTourDialog, should_show_tour, mark_tour_seen

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
        self._latest_graph_snapshot = None
        self._stat_events = 0
        self._stat_evidence = 0
        self._last_event_at = None
        self._session_event_count = 0

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
        self._setup_menu()

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

        # Coalesce graph redraws so correlation bursts cannot freeze the UI
        self._graph_refresh_timer = QTimer(self)
        self._graph_refresh_timer.setSingleShot(True)
        self._graph_refresh_timer.setInterval(250)
        self._graph_refresh_timer.timeout.connect(self._refresh_graph_view)

        # Populate integrity table with existing evidence on startup
        self.populate_integrity_table()
        self._refresh_stat_counts_from_db()

        self.poll_stats()
        self.update_incidents_ui()

        if should_show_tour():
            QTimer.singleShot(500, self._show_quick_tour)

    def _show_quick_tour(self):
        dlg = QuickTourDialog(self)
        dlg.exec()
        mark_tour_seen()

    def closeEvent(self, event):
        self.update_timer.stop()
        self.ui_refresh_timer.stop()
        self.save_timer.stop()
        self._graph_refresh_timer.stop()
        if self.is_monitoring:
            # Skip auto-verify on exit — hashing many files can delay close.
            self.stop_monitoring(auto_verify=False)
        if hasattr(self, "graph_widget"):
            self.graph_widget.cleanup()
        self.correlation_thread.quit()
        self.correlation_thread.wait(2000)
        self.monitor.shutdown()
        try:
            self.graph_db.save()
        except Exception as e:
            print(f"Failed to save graph on close: {e}")
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
        
        self.btn_monitor = QPushButton("▶ START MONITORING")
        self.btn_monitor.setStyleSheet("background-color: #2e7d32; color: white; font-weight: bold; padding: 8px 16px;")
        self.btn_monitor.clicked.connect(self.toggle_monitoring)
        
        self.btn_verify = QPushButton("Verify Integrity")
        self.btn_verify.clicked.connect(lambda: self.verify_integrity())
        self.btn_offline = QPushButton("Offline Evidence (Advanced)")
        self.btn_offline.clicked.connect(self.on_offline_evidence_clicked)
        self.btn_offline.setStyleSheet("background-color: #1565c0; color: white; font-weight: bold; padding: 8px;")

        toolbar_layout.addWidget(self.btn_monitor)
        toolbar_layout.addWidget(self.btn_verify)
        toolbar_layout.addWidget(self.btn_offline)
        toolbar_layout.addStretch()
        
        main_layout.addLayout(toolbar_layout)

        self.monitor_banner = QFrame()
        self.monitor_banner.setFrameShape(QFrame.Shape.StyledPanel)
        banner_layout = QVBoxLayout(self.monitor_banner)
        banner_layout.setContentsMargins(12, 8, 12, 8)
        self.monitor_state_label = QLabel()
        self.monitor_state_label.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        self.monitor_detail_label = QLabel()
        self.monitor_detail_label.setWordWrap(True)
        banner_layout.addWidget(self.monitor_state_label)
        banner_layout.addWidget(self.monitor_detail_label)
        main_layout.addWidget(self.monitor_banner)
        self._update_monitor_banner()
        
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
        self.suspicious_list.setStyleSheet(
            "background-color: #1a1a1a; color: #eeeeee; font-family: Segoe UI; font-size: 13px;"
        )
        self.suspicious_list.setWordWrap(True)
        self.suspicious_list.itemClicked.connect(self.on_suspicious_clicked)
        self.suspicious_list.addItem(
            "Nothing unusual flagged yet.\n\n"
            "This list fills when the app finds patterns that may need attention "
            "(for example a new file that runs and then contacts the internet).\n\n"
            "Open the Activity tab to see live captures."
        )
        self.left_tabs.addTab(self.suspicious_list, "Needs attention")

        # Tab 2: Event Stream
        all_events_widget = QWidget()
        all_events_layout = QVBoxLayout(all_events_widget)
        all_events_layout.setContentsMargins(0, 0, 0, 0)

        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Show:"))
        self.event_filter_combo = QComboBox()
        for label, _key in FILTER_OPTIONS:
            self.event_filter_combo.addItem(label)
        self.event_filter_combo.setCurrentText("All activity")
        self.event_filter_combo.currentTextChanged.connect(self.apply_event_filter)
        filter_layout.addWidget(self.event_filter_combo)
        filter_layout.addStretch()
        all_events_layout.addLayout(filter_layout)

        self.filter_help_label = QLabel()
        self.filter_help_label.setStyleSheet("color: #888; font-size: 11px; padding: 2px 0;")
        self.filter_help_label.setWordWrap(True)
        all_events_layout.addWidget(self.filter_help_label)
        
        self.live_stream = QListWidget()
        self.live_stream.setStyleSheet(
            "background-color: #1e1e1e; color: #e8e8e8; font-family: Segoe UI; font-size: 13px;"
        )
        self.live_stream.itemClicked.connect(self.on_event_clicked)
        
        self.timeline_list = QListWidget()
        self.timeline_list.setStyleSheet("font-family: Segoe UI; font-size: 12px;")
        self.timeline_list.itemClicked.connect(self.on_event_clicked)
        
        all_events_layout.addWidget(QLabel("Activity stream (what just happened)"))
        all_events_layout.addWidget(self.live_stream, stretch=2)
        all_events_layout.addWidget(QLabel("Recent activity"))
        all_events_layout.addWidget(self.timeline_list, stretch=1)
        
        self.left_tabs.addTab(all_events_widget, "Activity")
        self.left_tabs.setCurrentIndex(1)
        self._update_filter_help()
        
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
        self.incident_view.setHtml(
            "<p style='color: gray;'>Incident stories appear after the app links related activity "
            "(for example a program contacting the internet).</p>"
        )
        self.right_tabs.addTab(self.incident_view, "Incident Summary")
        
        # Tab 3: Event Details
        self.event_details_view = QTextEdit()
        self.event_details_view.setReadOnly(True)
        self.event_details_view.setHtml(
            "<p style='color: gray;'>Select an activity line on the left to see a plain-language summary.</p>"
        )
        self.right_tabs.addTab(self.event_details_view, "Event Details")

        integrity_widget = QWidget()
        integrity_layout = QVBoxLayout(integrity_widget)
        integrity_layout.setContentsMargins(4, 4, 4, 4)
        self.integrity_table = QTableWidget(0, 6)
        self.integrity_table.setHorizontalHeaderLabels(
            ["Evidence ID", "What it is", "Original fingerprint", "Current fingerprint", "Status", "Collected"]
        )
        self.integrity_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        integrity_layout.addWidget(self.integrity_table, stretch=1)
        self.integrity_help_label = QLabel(
            "<b>Status meanings:</b> "
            "<span style='color:#2e7d32;'>Unchanged</span> = file still matches its fingerprint · "
            "<span style='color:#c62828;'>Changed on disk</span> = do not trust alone · "
            "<span style='color:#e67e22;'>File missing</span> = original path unreadable · "
            "<span style='color:#757575;'>Not checked yet</span> = click Verify Integrity or stop monitoring."
        )
        self.integrity_help_label.setWordWrap(True)
        self.integrity_help_label.setStyleSheet("color: #555; font-size: 11px; padding: 6px 0;")
        integrity_layout.addWidget(self.integrity_help_label)
        self.right_tabs.addTab(integrity_widget, "Evidence Integrity")
        
        right_layout.addWidget(self.right_tabs, stretch=1)
        
        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)
        
        # Add Splitter to main
        main_layout.addWidget(splitter, stretch=1)

    def _setup_menu(self):
        help_menu = self.menuBar().addMenu("Help")
        tour_action = help_menu.addAction("Quick tour (30 seconds)")
        tour_action.triggered.connect(self._show_quick_tour)
        
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

    def _update_monitor_banner(self):
        if self.is_monitoring:
            collectors = self.monitor.collector_status()
            parts = []
            for item in collectors:
                mark = "ON" if item["running"] else "starting…"
                parts.append(f"{item['name']} {mark}")
            collector_text = "  ·  ".join(parts) if parts else "collectors starting…"
            last = "waiting for the first event"
            if self._last_event_at:
                age = max(0, int((datetime.datetime.utcnow() - self._last_event_at).total_seconds()))
                if age < 3:
                    last = "event just now — collectors are live"
                else:
                    last = f"last event {age}s ago"
            self.monitor_banner.setStyleSheet(
                "QFrame { background-color: #e8f5e9; border: 2px solid #2e7d32; border-radius: 4px; }"
            )
            self.monitor_state_label.setStyleSheet("color: #1b5e20;")
            self.monitor_state_label.setText("LIVE — this PC is being monitored")
            self.monitor_detail_label.setStyleSheet("color: #33691e;")
            next_step = (
                "Next: watch Activity stream on the left. "
                "Open a browser or create a file to generate events. "
                "Links on the Evidence Graph appear when a program contacts the internet."
            )
            self.monitor_detail_label.setText(
                f"Watching this PC only (local collectors, not a remote agent).  "
                f"{collector_text}.  {last}.  "
                f"This session: {self._session_event_count} events.  "
                f"Click Stop to pause.  {next_step}"
            )
            self.setWindowTitle("Evidence-Backed Forensic Monitor  [LIVE]")
            self.status_label.setText("● LIVE")
            self.status_label.setStyleSheet("color: #2e7d32; font-weight: bold; font-size: 14px;")
            self.btn_monitor.setText("■ STOP MONITORING")
            self.btn_monitor.setStyleSheet("background-color: #c62828; color: white; font-weight: bold; padding: 8px 16px;")
        else:
            self.monitor_banner.setStyleSheet(
                "QFrame { background-color: #f5f5f5; border: 2px solid #9e9e9e; border-radius: 4px; }"
            )
            self.monitor_state_label.setStyleSheet("color: #424242;")
            self.monitor_state_label.setText("STOPPED — not capturing live activity")
            self.monitor_detail_label.setStyleSheet("color: #616161;")
            self.monitor_detail_label.setText(
                "Not capturing right now. Saved evidence stays in the database. "
                "Next: click Start Monitoring, then open a program or save a file — "
                "activity will appear in the Activity stream."
            )
            self.setWindowTitle("Evidence-Backed Forensic Monitor  [STOPPED]")
            self.status_label.setText("● STOPPED")
            self.status_label.setStyleSheet("color: #c62828; font-weight: bold; font-size: 14px;")
            self.btn_monitor.setText("▶ START MONITORING")
            self.btn_monitor.setStyleSheet("background-color: #2e7d32; color: white; font-weight: bold; padding: 8px 16px;")

    def toggle_monitoring(self):
        if self.is_monitoring:
            self.stop_monitoring()
        else:
            self.start_monitoring()

    def start_monitoring(self):
        self.is_monitoring = True
        self._session_event_count = 0
        self._last_event_at = None
        self.left_tabs.setCurrentIndex(1)
        self.event_filter_combo.setCurrentText("All activity")
        self.live_stream.insertItem(0, "▶ Started — watching programs, files, and network on this PC…")
        self.monitor.start_all()
        self._update_monitor_banner()
        self._update_filter_help()

    def stop_monitoring(self, auto_verify: bool = True):
        self.is_monitoring = False
        self.live_stream.insertItem(0, "■ Stopped — no longer capturing new activity.")
        self.monitor.stop_all()
        self._update_monitor_banner()
        self._update_filter_help()
        if auto_verify:
            QTimer.singleShot(200, self._auto_verify_integrity)

    def _auto_verify_integrity(self):
        try:
            self.verify_integrity(silent=True)
        except Exception as e:
            print(f"Auto integrity check failed: {e}")

    def _current_filter_key(self) -> str:
        return FILTER_LABEL_TO_KEY.get(self.event_filter_combo.currentText(), "ALL")

    def _update_filter_help(self):
        total = 0
        visible = 0
        for i in range(self.live_stream.count()):
            item = self.live_stream.item(i)
            if item.data(Qt.UserRole) is None:
                continue
            total += 1
            if not item.isHidden():
                visible += 1
        key = self._current_filter_key()
        if total == 0:
            if self.is_monitoring:
                self.filter_help_label.setText(
                    "Waiting for activity… Open a browser, create a file, or start a program."
                )
            else:
                self.filter_help_label.setText(
                    "No activity yet. Click Start Monitoring to begin capturing."
                )
        elif key == "ALL":
            self.filter_help_label.setText(f"Showing all {total} captured events.")
        else:
            label = self.event_filter_combo.currentText()
            self.filter_help_label.setText(
                f"Showing {visible} of {total} events ({label}). "
                f"Choose “All activity” to see everything."
            )

    def apply_event_filter(self):
        filter_key = self._current_filter_key()
        all_suspicious = self.cached_suspicious
        incidents = self.cached_incidents

        incident_evidence_ids = set()
        for inc in incidents:
            incident_evidence_ids.update(inc.get("evidence_ids", []))

        for list_widget in (self.live_stream, self.timeline_list):
            for i in range(list_widget.count()):
                item = list_widget.item(i)
                event = item.data(Qt.UserRole)
                if not event:
                    item.setHidden(False)
                    continue
                res = self.classification_engine.classify_event(
                    event, self._analysis_graph(), all_suspicious, self.graph_version
                )
                show = filter_matches(
                    filter_key,
                    res["classification"],
                    event.evidence_id,
                    incident_evidence_ids,
                )
                item.setHidden(not show)
        self._update_filter_help()

    @Slot(object)
    def on_new_event(self, event: ForensicEvent):
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
        filter_key = self._current_filter_key()
        incident_evidence_ids = set()
        for inc in self.cached_incidents:
            incident_evidence_ids.update(inc.get("evidence_ids", []))
        
        for event in batch:
            stream_text = format_event_sentence(event)
            color = event_item_color(event)

            item_live = QListWidgetItem(stream_text)
            item_live.setData(Qt.UserRole, event)
            item_live.setForeground(color)
            self.live_stream.insertItem(0, item_live)
            
            item_timeline = QListWidgetItem(stream_text)
            item_timeline.setData(Qt.UserRole, event)
            item_timeline.setForeground(color.darker(120))
            self.timeline_list.insertItem(0, item_timeline)

            res = self.classification_engine.classify_event(
                event, self._analysis_graph(), all_suspicious, self.graph_version
            )
            if event.evidence_id not in self.evidence_classifications:
                self.evidence_classifications[event.evidence_id] = res["classification"]

            if filter_key != "ALL":
                is_visible = filter_matches(
                    filter_key,
                    res["classification"],
                    event.evidence_id,
                    incident_evidence_ids,
                )
                item_live.setHidden(not is_visible)
                item_timeline.setHidden(not is_visible)
                
        while self.live_stream.count() > 5000:
            self.live_stream.takeItem(5000)
        while self.timeline_list.count() > 500:
            self.timeline_list.takeItem(500)
            
        self._stat_events += len(batch)
        self._stat_evidence += len(batch)
        self._session_event_count += len(batch)
        self._last_event_at = datetime.datetime.utcnow()
        self.batch_ready.emit(batch)
        self._update_filter_help()
        
        elapsed = (time.perf_counter() - start_time) * 1000
        print(f"[PERF] GUI refresh: {elapsed:.2f} ms")
            
    @Slot(list)
    def on_correlations_found(self, relationships):
        self.graph_version += 1
        
    @Slot(object)
    def on_graph_updated(self, graph_snapshot):
        self.graph_version += 1
        self._latest_graph_snapshot = graph_snapshot
        self._graph_refresh_timer.start()
        
    @Slot(list)
    def on_suspicious_updated(self, suspicious):
        self.cached_suspicious = suspicious
        self._graph_refresh_timer.start()
        
    @Slot(list)
    def on_incidents_updated(self, incidents):
        self.cached_incidents = incidents
        self._graph_refresh_timer.start()
        self.update_incidents_ui()

    def _analysis_graph(self):
        if self._latest_graph_snapshot is not None:
            return self._latest_graph_snapshot
        return self.graph_db.graph

    def _refresh_graph_view(self):
        graph = self._analysis_graph()
        self.graph_widget.update_graph(
            graph,
            self.cached_suspicious,
            self.cached_incidents,
            self.evidence_classifications,
        )
        self.poll_stats()
        
    def update_incidents_ui(self):
        from PySide6.QtWidgets import QListWidgetItem

        all_suspicious = self.cached_suspicious
        self.suspicious_list.clear()
        if not all_suspicious:
            self.suspicious_list.addItem(
                "Nothing unusual flagged yet.\n\n"
                "Normal Chrome, Cursor, and GitHub traffic is usually expected and may not appear here.\n"
                "Open the Activity tab to see everything being captured."
            )
        for act in all_suspicious:
            item = QListWidgetItem(format_suspicious_item(act))
            item.setData(Qt.UserRole, act)
            score = act.get("score", 0)
            item.setForeground(QColor(severity_color(score)))
            self.suspicious_list.addItem(item)

        self.incident_view.setHtml(format_incidents_page_html(self.cached_incidents))

    def _refresh_stat_counts_from_db(self):
        try:
            self._stat_events = (
                self.db.query(ForensicEvent)
                .filter(ForensicEvent.case_id == self.current_case.id)
                .count()
            )
            self._stat_evidence = (
                self.db.query(EvidenceArtifact)
                .filter(EvidenceArtifact.case_id == self.current_case.id)
                .count()
            )
        except Exception as e:
            print(f"Stat count query failed: {e}")

    def poll_stats(self):
        # Avoid COUNT(*) on the UI thread while collectors are writing to SQLite.
        if not self.is_monitoring:
            self._refresh_stat_counts_from_db()

        self.lbl_events.setText(str(self._stat_events))
        self.lbl_evidence.setText(str(self._stat_evidence))
        
        rel_count = self._analysis_graph().number_of_edges()
        
        suspicious_count = len(self.cached_suspicious)
        inc_count = len(self.cached_incidents)
        
        self.lbl_relations.setText(str(rel_count))
        self.lbl_incidents.setText(str(inc_count))
        self.lbl_suspicious.setText(str(suspicious_count))
        
        user_acts = sum(1 for v in self.classification_engine._cache.values() if v["classification"] == "USER_ACTIVITY")
        bg_acts = sum(1 for v in self.classification_engine._cache.values() if v["classification"] == "BACKGROUND_ACTIVITY")
        
        self.lbl_user_acts.setText(str(user_acts))
        self.lbl_bg_acts.setText(str(bg_acts))
        self._update_monitor_banner()

    @Slot(object)
    def on_event_clicked(self, item):
        event = item.data(Qt.UserRole)
        if not event:
            return
            
        all_suspicious = self.cached_suspicious
        res = self.classification_engine.classify_event(
            event, self._analysis_graph(), all_suspicious, self.graph_version
        )

        html = format_event_summary_html(event, res)

        integrity_block = ""
        ev_artifact = self.db.query(EvidenceArtifact).filter_by(id=event.evidence_id).first()
        if ev_artifact:
            integrity_block = (
                f"<hr style='border: 1px dashed #555;'>"
                f"<h4>Saved evidence copy</h4>"
                f"<b>Status:</b> {ev_artifact.integrity_status or 'Unknown'}<br/>"
                f"<b>Fingerprint (SHA-256):</b> {ev_artifact.sha256_hash}<br/>"
                f"<b>Saved as:</b> {ev_artifact.filename}<br/>"
                f"<b>Collected:</b> "
                f"{ev_artifact.collection_timestamp.strftime('%Y-%m-%d %H:%M:%S') if ev_artifact.collection_timestamp else 'N/A'}<br/>"
            )
        else:
            integrity_block = (
                "<hr/><p style='color:#888;'>No saved evidence file was found for this event.</p>"
            )

        html += format_event_advanced_html(event, integrity_block)
        self.event_details_view.setHtml(html)
        self.right_tabs.setCurrentIndex(2)

    def on_suspicious_clicked(self, item):
        data = item.data(Qt.UserRole)
        if not data:
            return
        self.show_suspicious_provenance(data)
        self._open_suspicious_in_graph()

    def _open_suspicious_in_graph(self):
        self.graph_widget.filter_combo.setCurrentText("Needs attention")
        self.right_tabs.setCurrentIndex(0)

    def show_suspicious_provenance(self, act):
        html = format_suspicious_detail_html(act)
        html += (
            "<p><i>Tip: the Evidence Graph tab is already filtered to “Needs attention” "
            "so you can see linked programs and services.</i></p>"
        )
        self.event_details_view.setHtml(html)
        self.right_tabs.setCurrentIndex(2)

    def _integrity_status_item(self, status: str) -> QTableWidgetItem:
        display = map_status_display(status)
        item = QTableWidgetItem(display)
        item.setToolTip(STATUS_HELP.get(status, display))
        if status == "VALID":
            item.setForeground(QColor("#2e7d32"))
        elif status == "MODIFIED":
            item.setForeground(QColor("#c62828"))
        elif status == "UNVERIFIABLE":
            item.setForeground(QColor("#e67e22"))
        else:
            item.setForeground(QColor("#757575"))
        return item

    def _fill_integrity_row(self, row: int, art: EvidenceArtifact, current_hash: str = None, checked_at: str = None):
        self.integrity_table.setItem(row, 0, QTableWidgetItem(art.id))
        self.integrity_table.setItem(row, 1, QTableWidgetItem(human_source_label(art, self.db)))

        orig_hash_short = (art.sha256_hash[:16] + "...") if art.sha256_hash else "N/A"
        self.integrity_table.setItem(row, 2, QTableWidgetItem(orig_hash_short))

        status = art.integrity_status or "UNVERIFIED"
        if current_hash and current_hash not in ("N/A", "Not checked yet"):
            cur_display = current_hash[:16] + "..." if len(current_hash) > 16 else current_hash
        elif status == "VALID":
            cur_display = orig_hash_short
        else:
            cur_display = "Not checked yet"
        self.integrity_table.setItem(row, 3, QTableWidgetItem(cur_display))
        self.integrity_table.setItem(row, 4, self._integrity_status_item(status))

        ts = art.collection_timestamp
        ts_str = checked_at or (ts.strftime("%Y-%m-%d %H:%M:%S") if ts else "—")
        self.integrity_table.setItem(row, 5, QTableWidgetItem(ts_str))

    def populate_integrity_table(self):
        artifacts = self.db.query(EvidenceArtifact).filter(
            EvidenceArtifact.case_id == self.current_case.id
        ).all()

        self.integrity_table.setRowCount(0)
        for row, art in enumerate(artifacts):
            self.integrity_table.insertRow(row)
            self._fill_integrity_row(row, art)

    def verify_integrity(self, silent: bool = False):
        from core.services.integrity import verify_all_evidence
        try:
            results = verify_all_evidence(self.db, self.current_case.id)
        except Exception as e:
            print(f"Integrity verification failed: {e}")
            if not silent:
                QMessageBox.warning(self, "Integrity check", f"Could not verify evidence:\n{e}")
            return

        self.integrity_table.setRowCount(0)
        artifacts_by_id = {
            art.id: art
            for art in self.db.query(EvidenceArtifact).filter(
                EvidenceArtifact.case_id == self.current_case.id
            ).all()
        }

        for row, res in enumerate(results):
            self.integrity_table.insertRow(row)
            art = artifacts_by_id.get(res["evidence_id"])
            if art:
                self._fill_integrity_row(
                    row,
                    art,
                    current_hash=res.get("current_hash"),
                    checked_at=res.get("time"),
                )
            else:
                self.integrity_table.setItem(row, 0, QTableWidgetItem(res["evidence_id"]))
                self.integrity_table.setItem(row, 1, QTableWidgetItem(res.get("source", "")))
                orig = res.get("original_hash") or ""
                self.integrity_table.setItem(
                    row, 2, QTableWidgetItem((orig[:16] + "...") if orig else "N/A")
                )
                cur = res.get("current_hash") or ""
                self.integrity_table.setItem(
                    row,
                    3,
                    QTableWidgetItem(
                        (cur[:16] + "...") if cur and cur != "N/A" else "Not checked yet"
                    ),
                )
                self.integrity_table.setItem(row, 4, self._integrity_status_item(res["status"]))
                self.integrity_table.setItem(row, 5, QTableWidgetItem(res.get("time") or "—"))

        if not silent:
            modified = sum(1 for r in results if r["status"] == "MODIFIED")
            missing = sum(1 for r in results if r["status"] == "UNVERIFIABLE")
            if modified or missing:
                QMessageBox.warning(
                    self,
                    "Integrity check",
                    f"Checked {len(results)} evidence files.\n"
                    f"{modified} changed on disk · {missing} missing or unreadable.",
                )
            else:
                QMessageBox.information(
                    self,
                    "Integrity check",
                    f"Checked {len(results)} evidence files — all unchanged.",
                )

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
        self._latest_graph_snapshot = self.graph_db.graph.copy()

        ev_cls = {}
        for ev in result.events:
            r = self.classification_engine.classify_event(
                ev, self._analysis_graph(), self.cached_suspicious, self.graph_version
            )
            ev_cls[ev.evidence_id] = r["classification"]
        self.evidence_classifications.update(ev_cls)

        self.graph_widget.update_graph(
            self._analysis_graph(),
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
        filter_key = self._current_filter_key()
        incident_evidence_ids = set()
        for inc in self.cached_incidents:
            incident_evidence_ids.update(inc.get("evidence_ids", []))

        for event in result.events:
            stream_text = format_event_sentence(event)
            color = event_item_color(event)

            item_live = QListWidgetItem(stream_text)
            item_live.setData(Qt.UserRole, event)
            item_live.setForeground(color)
            self.live_stream.insertItem(0, item_live)

            item_timeline = QListWidgetItem(stream_text)
            item_timeline.setData(Qt.UserRole, event)
            self.timeline_list.insertItem(0, item_timeline)

            res = self.classification_engine.classify_event(
                event, self._analysis_graph(), all_suspicious, self.graph_version
            )
            if filter_key != "ALL":
                is_visible = filter_matches(
                    filter_key,
                    res["classification"],
                    event.evidence_id,
                    incident_evidence_ids,
                )
                item_live.setHidden(not is_visible)
                item_timeline.setHidden(not is_visible)

        while self.live_stream.count() > 10000:
            self.live_stream.takeItem(10000)
        while self.timeline_list.count() > 1000:
            self.timeline_list.takeItem(1000)

    def _populate_suspicious_list(self, result: OfflineAnalysisResult):
        from PySide6.QtWidgets import QListWidgetItem
        self.suspicious_list.clear()
        for act in result.suspicious_activities:
            item = QListWidgetItem(format_suspicious_item(act))
            item.setData(Qt.UserRole, act)
            item.setForeground(QColor(severity_color(act.get("score", 0))))
            self.suspicious_list.addItem(item)
