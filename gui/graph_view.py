import math
import re
import socket
import networkx as nx
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGraphicsView, QGraphicsScene,
    QGraphicsEllipseItem, QGraphicsLineItem, QGraphicsTextItem, QGraphicsItem,
    QTextEdit, QLabel, QSplitter, QComboBox
)
from PySide6.QtCore import Qt, QLineF, QThread, Signal, QObject, Slot, QTimer
from PySide6.QtGui import QColor, QPen, QBrush, QFont, QTransform, QPainter

NODE_COLORS = {
    "Process": QColor("#e74c3c"),
    "File": QColor("#f1c40f"),
    "IP": QColor("#3498db"),
    "User": QColor("#2ecc71"),
    "Device": QColor("#9b59b6"),
    "unknown": QColor("#95a5a6")
}

TYPE_TITLES = {
    "Process": "Process",
    "File": "File",
    "IP": "Remote IP",
    "User": "User",
    "Device": "Device",
}

EDGE_LABELS = {
    "CONNECTED_TO": "connected to",
    "EXECUTED_AS": "executed as",
    "DOWNLOADED": "downloaded",
    "EXECUTED_BY": "started by",
    "EXFILTRATED_VIA": "copied via",
    "SAME_HASH_AS": "same hash as",
}

IP_RE = re.compile(r"^\d{1,3}(?:\.\d{1,3}){3}$")
PROCESS_ID_RE = re.compile(r"^(?P<host>.+)_(?P<pid>\d+)_(?P<name>.+)$")
DNS_CACHE = {}


def infer_node_type(node_id, node_data=None):
    if node_data and node_data.get("type"):
        return node_data["type"]
    text = str(node_id)
    if IP_RE.match(text):
        return "IP"
    if PROCESS_ID_RE.match(text):
        return "Process"
    if "_USB_" in text:
        return "Device"
    return "unknown"


def friendly_service_name(hostname: str) -> str:
    """Turn noisy reverse-DNS into a short service name for the canvas."""
    if not hostname:
        return ""
    host = hostname.lower().rstrip(".")
    rules = (
        ("github.com", "GitHub"),
        ("githubusercontent.com", "GitHub"),
        ("amazonaws.com", "Amazon AWS"),
        (".compute-1.", "Amazon AWS"),
        (".compute.amazonaws", "Amazon AWS"),
        ("1e100.net", "Google"),
        ("google.com", "Google"),
        ("googleapis.com", "Google"),
        ("gvt2.com", "Google"),
        ("microsoft.com", "Microsoft"),
        ("office.com", "Microsoft"),
        ("live.com", "Microsoft"),
        ("msn.com", "Microsoft"),
        ("azure.com", "Microsoft Azure"),
        ("cloudflare.com", "Cloudflare"),
        ("cursor.sh", "Cursor"),
        ("cursor.com", "Cursor"),
        ("openai.com", "OpenAI"),
        ("anthropic.com", "Anthropic"),
        ("facebook.com", "Facebook"),
        ("fbcdn.net", "Facebook"),
        ("whatsapp.net", "WhatsApp"),
        ("apple.com", "Apple"),
        ("icloud.com", "Apple"),
        ("akamai", "Akamai CDN"),
        ("fastly.net", "Fastly CDN"),
        ("cloudfront.net", "Amazon CloudFront"),
    )
    for needle, label in rules:
        if needle in host:
            return label
    parts = [p for p in host.split(".") if p]
    if len(parts) >= 2:
        if parts[-2] in {"co", "com", "net", "org", "gov"} and len(parts) >= 3:
            return ".".join(parts[-3:])
        return ".".join(parts[-2:])
    return host


def node_display(node_id, node_data=None):
    """Return (primary_label, subtitle, node_type) for canvas drawing."""
    node_data = node_data or {}
    ntype = infer_node_type(node_id, node_data)

    if ntype == "Process":
        name = node_data.get("process") or node_data.get("label")
        pid = node_data.get("pid")
        if not name or name == node_id:
            match = PROCESS_ID_RE.match(str(node_id))
            if match:
                name = match.group("name")
                pid = pid or match.group("pid")
            else:
                name = str(node_id)
        subtitle = node_data.get("subtitle") or (f"PID {pid}" if pid else "Process")
        return name, subtitle, ntype

    if ntype == "IP":
        ip = node_data.get("ip") or str(node_id)
        hostname = node_data.get("hostname") or DNS_CACHE.get(ip)
        if hostname:
            service = friendly_service_name(hostname)
            return service or hostname, ip, ntype
        return ip, "Remote IP", ntype

    if ntype == "File":
        name = node_data.get("file") or node_data.get("label")
        if not name or name == node_id:
            text = str(node_id)
            name = text.split("_", 1)[-1] if "_" in text else text
        return name, node_data.get("subtitle") or "File", ntype

    if ntype == "User":
        name = node_data.get("user") or node_data.get("label") or str(node_id)
        return name, "User", ntype

    if ntype == "Device":
        name = node_data.get("label") or "USB device"
        if name == node_id:
            name = "USB device"
        return name, node_data.get("subtitle") or "Device", ntype

    label = node_data.get("label") or str(node_id)
    if len(label) > 28:
        label = label[:25] + "..."
    return label, ntype, ntype


class ReverseDnsWorker(QObject):
    resolved = Signal(str, str)

    @Slot(list)
    def resolve_many(self, ips):
        for ip in ips:
            if not ip or ip in DNS_CACHE:
                cached = DNS_CACHE.get(ip)
                if cached:
                    self.resolved.emit(ip, cached)
                continue
            try:
                socket.setdefaulttimeout(0.8)
                hostname, _, _ = socket.gethostbyaddr(ip)
                DNS_CACHE[ip] = hostname
                self.resolved.emit(ip, hostname)
            except Exception:
                DNS_CACHE[ip] = ""

class GraphNodeItem(QGraphicsEllipseItem):
    def __init__(self, node_id, node_data, widget_ref):
        radius = 16
        super().__init__(-radius, -radius, radius * 2, radius * 2)
        self.node_id = node_id
        self.node_data = dict(node_data or {})
        self.widget_ref = widget_ref
        self.radius = radius
        
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setZValue(1)
        
        node_type = infer_node_type(node_id, self.node_data)
        self.node_data["type"] = node_type
        color = NODE_COLORS.get(node_type, NODE_COLORS["unknown"])
        
        self.setBrush(QBrush(color))
        self.setPen(QPen(Qt.GlobalColor.black, 1))
        
        self.label = QGraphicsTextItem(self)
        self.label.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        self.edges = []
        self.refresh_label()
        
    def refresh_label(self):
        primary, subtitle, _ = node_display(self.node_id, self.node_data)
        if len(primary) > 28:
            primary = primary[:25] + "..."
        self.label.setHtml(
            f"<div style='text-align:center;'>"
            f"<span style='font-weight:700; color:#1a1a1a;'>{primary}</span><br/>"
            f"<span style='font-size:7pt; color:#555555;'>{subtitle}</span>"
            f"</div>"
        )
        br = self.label.boundingRect()
        self.label.setPos(-br.width() / 2, self.radius + 1)
        
    def add_edge(self, edge):
        self.edges.append(edge)
        
    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            for edge in self.edges:
                edge.update_position()
        return super().itemChange(change, value)
        
    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        self.widget_ref.show_node_details(self.node_id, self.node_data)
        
class GraphEdgeItem(QGraphicsLineItem):
    def __init__(self, source_item, target_item, edge_data, widget_ref, show_label=False):
        super().__init__()
        self.source_item = source_item
        self.target_item = target_item
        self.edge_data = edge_data
        self.widget_ref = widget_ref
        
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setAcceptHoverEvents(True)
        self.setZValue(0)
        
        self.setPen(QPen(QColor("#7f8c8d"), 2, Qt.PenStyle.SolidLine))
        
        rel = edge_data.get("relationship_type") or edge_data.get("type") or ""
        friendly = EDGE_LABELS.get(rel, rel.replace("_", " ").lower())
        self.label = QGraphicsTextItem(friendly, self)
        self.label.setFont(QFont("Segoe UI", 7))
        self.label.setDefaultTextColor(QColor("#555555"))
        self.label.setVisible(bool(show_label))
        
        self.source_item.add_edge(self)
        self.target_item.add_edge(self)
        
        self.update_position()

    def hoverEnterEvent(self, event):
        self.label.setVisible(True)
        self.setPen(QPen(QColor("#2c3e50"), 3, Qt.PenStyle.SolidLine))
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        if not self.isSelected():
            self.label.setVisible(False)
            self.setPen(QPen(QColor("#7f8c8d"), 2, Qt.PenStyle.SolidLine))
        super().hoverLeaveEvent(event)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemSelectedHasChanged:
            selected = bool(value)
            self.label.setVisible(selected)
            if selected:
                self.setPen(QPen(QColor("#2c3e50"), 3, Qt.PenStyle.SolidLine))
            else:
                self.setPen(QPen(QColor("#7f8c8d"), 2, Qt.PenStyle.SolidLine))
        return super().itemChange(change, value)
        
    def update_position(self):
        line = QLineF(self.source_item.scenePos(), self.target_item.scenePos())
        self.setLine(line)
        
        # Move label to center of the line
        center = line.center()
        br = self.label.boundingRect()
        self.label.setPos(center.x() - br.width() / 2, center.y() - br.height() / 2)
        
    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        self.widget_ref.show_edge_details(self.source_item.node_id, self.target_item.node_id, self.edge_data)

class ZoomableView(QGraphicsView):
    def __init__(self, scene):
        super().__init__(scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        
    def wheelEvent(self, event):
        zoom_in_factor = 1.15
        zoom_out_factor = 1 / zoom_in_factor
        if event.angleDelta().y() > 0:
            zoom_factor = zoom_in_factor
        else:
            zoom_factor = zoom_out_factor
        self.scale(zoom_factor, zoom_factor)

class GraphLayoutWorker(QObject):
    finished = Signal(int, object)

    @Slot(int, object)
    def compute(self, request_id: int, nx_graph):
        """Run a cheap layout on a simple Graph snapshot. Must not touch the live MultiDiGraph."""
        try:
            simple = nx.Graph()
            simple.add_nodes_from(list(nx_graph.nodes(data=True)))
            for u, v in list(nx_graph.edges()):
                if not simple.has_edge(u, v):
                    simple.add_edge(u, v)

            n = simple.number_of_nodes()
            if n == 0:
                self.finished.emit(request_id, {})
                return
            if n == 1:
                node = next(iter(simple.nodes()))
                self.finished.emit(request_id, {node: (0.0, 0.0)})
                return

            iterations = 35 if n < 40 else 22 if n < 100 else 12
            k = 4.0 / max(n ** 0.5, 1.0)
            pos = nx.spring_layout(simple, k=k, iterations=iterations, seed=42)
            self.finished.emit(request_id, pos)
        except Exception as e:
            print(f"Error in layout thread: {e}")
            self.finished.emit(request_id, None)


class InteractiveGraphWidget(QWidget):
    _layout_request = Signal(int, object)
    _dns_request = Signal(list)

    def __init__(self):
        super().__init__()
        self.full_graph = nx.MultiDiGraph()
        self.cached_suspicious = []
        self.cached_incidents = []
        self.evidence_classifications = {}
        self._current_graph = nx.Graph()
        self._is_layout_running = False
        self._layout_request_id = 0
        self._active_request_id = 0
        self._pending_refresh = False
        self._node_items = {}
        self.simple_mode = True
        self.setup_ui()
        self._setup_layout_thread()
        self._setup_dns_thread()

        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(250)
        self._debounce_timer.timeout.connect(self._flush_pending_update)
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("View:"))
        self.view_mode_combo = QComboBox()
        self.view_mode_combo.addItems(["Simple (easier to read)", "Detailed (each process ID)"])
        self.view_mode_combo.setCurrentIndex(0)
        self.view_mode_combo.currentIndexChanged.connect(self.on_view_mode_changed)
        controls.addWidget(self.view_mode_combo)

        controls.addWidget(QLabel("  Filter:"))
        self.filter_combo = QComboBox()
        self.filter_combo.addItems([
            "All links", "Needs attention", "Part of an incident",
            "User actions", "Background noise", "Linked activity", "Unclear"
        ])
        self.filter_combo.setCurrentText("All links")
        self.filter_combo.currentTextChanged.connect(self.on_filter_changed)
        controls.addWidget(self.filter_combo)
        controls.addStretch()
        left_layout.addLayout(controls)
        
        self.summary_label = QLabel("No linked activity yet.")
        self.summary_label.setStyleSheet(
            "background-color: #eef5ff; color: #1a237e; font-size: 12px; "
            "padding: 6px 8px; border: 1px solid #90caf9; border-radius: 3px;"
        )
        self.summary_label.setWordWrap(True)
        left_layout.addWidget(self.summary_label)

        self.diagnostic_label = QLabel("")
        self.diagnostic_label.hide()

        self.legend_label = QLabel(
            "<span style='color:#e74c3c;'>● Program</span> · "
            "<span style='color:#3498db;'>● Internet</span> · "
            "<span style='color:#f1c40f;'>● File</span> · "
            "Hover a line for link type · click a circle for the story"
        )
        self.legend_label.setStyleSheet("color: #555; font-size: 11px; padding: 0 4px;")
        self.legend_label.setWordWrap(True)
        
        self.scene = QGraphicsScene()
        self.view = ZoomableView(self.scene)
        self.view.setMinimumHeight(360)
        
        left_layout.addWidget(self.legend_label)
        left_layout.addWidget(self.view, stretch=1)
        
        self.empty_label = QLabel("", self.view)
        self.empty_label.setStyleSheet(
            "color: #555; font-size: 14px; font-weight: bold; background: rgba(255,255,255,210); padding: 12px;"
        )
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setWordWrap(True)
        self._set_empty_waiting()
        
        self.details_pane = QTextEdit()
        self.details_pane.setReadOnly(True)
        self.details_pane.setMaximumHeight(110)
        self.details_pane.setHtml(
            "<p style='color: gray; margin:0;'>"
            "Click a <b style='color:#e74c3c;'>red program</b> or "
            "<b style='color:#3498db;'>blue internet service</b> for a short story.</p>"
        )

        graph_splitter = QSplitter(Qt.Orientation.Vertical)
        graph_splitter.addWidget(left_widget)
        graph_splitter.addWidget(self.details_pane)
        graph_splitter.setStretchFactor(0, 5)
        graph_splitter.setStretchFactor(1, 1)
        graph_splitter.setCollapsible(1, True)

        layout.addWidget(graph_splitter, stretch=1)

    def _set_empty_waiting(self):
        self.empty_label.setText(
            "Events are being captured.\n\n"
            "Links appear here when a program contacts the internet,\n"
            "or when a file is created and then run.\n\n"
            "Tip: open Chrome or Cursor while monitoring is LIVE."
        )

    def on_view_mode_changed(self, index):
        self.simple_mode = index == 0
        self._pending_refresh = True
        self._debounce_timer.start()
        
    def _setup_layout_thread(self):
        self._layout_thread = QThread(self)
        self._layout_worker = GraphLayoutWorker()
        self._layout_worker.moveToThread(self._layout_thread)
        self._layout_request.connect(self._layout_worker.compute, Qt.ConnectionType.QueuedConnection)
        self._layout_worker.finished.connect(self.on_layout_finished, Qt.ConnectionType.QueuedConnection)
        self._layout_thread.start()

    def _setup_dns_thread(self):
        self._dns_thread = QThread(self)
        self._dns_worker = ReverseDnsWorker()
        self._dns_worker.moveToThread(self._dns_thread)
        self._dns_request.connect(self._dns_worker.resolve_many, Qt.ConnectionType.QueuedConnection)
        self._dns_worker.resolved.connect(self.on_hostname_resolved, Qt.ConnectionType.QueuedConnection)
        self._dns_thread.start()

    def cleanup(self):
        """Stop the persistent layout thread. Call from MainWindow.closeEvent."""
        self._debounce_timer.stop()
        self._pending_refresh = False
        try:
            self._layout_request.disconnect()
        except Exception:
            pass
        try:
            self._layout_worker.finished.disconnect()
        except Exception:
            pass
        try:
            self._dns_request.disconnect()
        except Exception:
            pass
        try:
            self._dns_worker.resolved.disconnect()
        except Exception:
            pass
        self._layout_thread.quit()
        if not self._layout_thread.wait(1500):
            self._layout_thread.terminate()
            self._layout_thread.wait(500)
        self._dns_thread.quit()
        if not self._dns_thread.wait(1500):
            self._dns_thread.terminate()
            self._dns_thread.wait(500)

    def on_filter_changed(self, text):
        self._pending_refresh = True
        self._debounce_timer.start()
            
    def filter_graph(self, nx_graph, cached_suspicious, cached_incidents, evidence_classifications=None):
        if evidence_classifications is None:
            evidence_classifications = {}

        filter_text = self.filter_combo.currentText()
        if filter_text in ("All links", "ALL"):
            return nx_graph

        nodes_to_keep = set()
        friendly_map = {
            "Needs attention": "SUSPICIOUS",
            "Part of an incident": "INCIDENT RELATED",
            "User actions": "USER ACTIVITY",
            "Background noise": "BACKGROUND",
            "Linked activity": "CORRELATED",
            "Unclear": "UNKNOWN",
        }
        key = friendly_map.get(filter_text, filter_text)

        if key == "SUSPICIOUS":
            for act in cached_suspicious:
                nodes_to_keep.update(act["nodes"])
        elif key == "INCIDENT RELATED":
            for inc in cached_incidents:
                for node in inc["nodes"]:
                    nodes_to_keep.add(node["id"] if isinstance(node, dict) else node)
        elif key in ("USER ACTIVITY", "BACKGROUND", "CORRELATED", "UNKNOWN"):
            target = {
                "USER ACTIVITY": "USER_ACTIVITY",
                "BACKGROUND": "BACKGROUND_ACTIVITY",
                "CORRELATED": "CORRELATED_ACTIVITY",
                "UNKNOWN": "UNKNOWN",
            }[key]
            for u, v, data in nx_graph.edges(data=True):
                ev_ids = data.get("evidence_ids", [])
                if any(evidence_classifications.get(eid) == target for eid in ev_ids):
                    nodes_to_keep.add(u)
                    nodes_to_keep.add(v)
        else:
            return nx_graph

        return nx_graph.subgraph(nodes_to_keep)

    def _collapse_simple(self, graph):
        """Merge process nodes that share the same program name into one bubble."""
        if not self.simple_mode:
            return graph

        mapping = {}
        collapsed = nx.Graph()

        for node_id, data in graph.nodes(data=True):
            ntype = infer_node_type(node_id, data)
            if ntype == "Process":
                primary, _sub, _ = node_display(node_id, data)
                key = f"proc:{primary.lower()}"
                mapping[node_id] = key
                if not collapsed.has_node(key):
                    collapsed.add_node(
                        key,
                        type="Process",
                        label=primary,
                        process=primary,
                        subtitle="program",
                        pid=data.get("pid"),
                        collapsed=True,
                        pids=[data.get("pid")] if data.get("pid") else [],
                    )
                else:
                    existing = collapsed.nodes[key]
                    pids = existing.setdefault("pids", [])
                    pid = data.get("pid")
                    if pid and pid not in pids:
                        pids.append(pid)
                    if pids:
                        existing["subtitle"] = f"{len(pids)} process IDs"
            else:
                mapping[node_id] = node_id
                if not collapsed.has_node(node_id):
                    collapsed.add_node(node_id, **dict(data))

        for u, v, data in graph.edges(data=True):
            su, sv = mapping.get(u, u), mapping.get(v, v)
            if su == sv:
                continue
            attrs = {
                k: data[k]
                for k in ("evidence_ids", "reasons", "confidence", "relationship_type", "type")
                if k in data
            }
            if collapsed.has_edge(su, sv):
                edge_data = collapsed[su][sv]
                for eid in attrs.get("evidence_ids", []):
                    edge_data.setdefault("evidence_ids", [])
                    if eid not in edge_data["evidence_ids"]:
                        edge_data["evidence_ids"].append(eid)
                edge_data["confidence"] = max(
                    edge_data.get("confidence", 0.0), attrs.get("confidence", 0.0)
                )
                if "relationship_type" not in edge_data and attrs.get("relationship_type"):
                    edge_data["relationship_type"] = attrs["relationship_type"]
            else:
                collapsed.add_edge(su, sv, **attrs)
        return collapsed

    def _update_summary(self, graph):
        processes = sum(1 for n, d in graph.nodes(data=True) if infer_node_type(n, d) == "Process")
        ips = sum(1 for n, d in graph.nodes(data=True) if infer_node_type(n, d) == "IP")
        files = sum(1 for n, d in graph.nodes(data=True) if infer_node_type(n, d) == "File")
        links = graph.number_of_edges()
        mode = "Simple view" if self.simple_mode else "Detailed view"
        parts = []
        if processes:
            parts.append(f"{processes} program{'s' if processes != 1 else ''}")
        if ips:
            parts.append(f"{ips} internet destination{'s' if ips != 1 else ''}")
        if files:
            parts.append(f"{files} file{'s' if files != 1 else ''}")
        if not parts:
            self.summary_label.setText("No linked activity yet.")
        else:
            self.summary_label.setText(
                f"{mode}: {' · '.join(parts)} · {links} connection{'s' if links != 1 else ''}. "
                f"Click a circle to read what happened."
            )
        self.diagnostic_label.setText(
            f"Graph: {processes} programs · {ips} destinations · {links} links · "
            f"Filter: {self.filter_combo.currentText()}"
        )

    def update_graph(self, nx_graph, cached_suspicious=None, cached_incidents=None, evidence_classifications=None):
        self.full_graph = nx_graph
        if cached_suspicious is not None:
            self.cached_suspicious = cached_suspicious
        if cached_incidents is not None:
            self.cached_incidents = cached_incidents
        if evidence_classifications is not None:
            self.evidence_classifications = evidence_classifications
        self._pending_refresh = True
        self._debounce_timer.start()

    def _snapshot_for_layout(self, filtered_graph):
        snapshot = nx.Graph()
        snapshot.add_nodes_from(list(filtered_graph.nodes(data=True)))
        for u, v, data in list(filtered_graph.edges(data=True)):
            keep = ("evidence_ids", "reasons", "confidence", "relationship_type", "type")
            attrs = {k: data[k] for k in keep if k in data}
            if snapshot.has_edge(u, v):
                existing = snapshot[u][v]
                existing.setdefault("evidence_ids", [])
                for eid in attrs.get("evidence_ids", []):
                    if eid not in existing["evidence_ids"]:
                        existing["evidence_ids"].append(eid)
                existing["confidence"] = max(existing.get("confidence", 0.0), attrs.get("confidence", 0.0))
            else:
                snapshot.add_edge(u, v, **attrs)
        return snapshot

    def _clear_scene(self):
        for item in self.scene.items():
            item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, False)
        self.scene.clear()

    def _flush_pending_update(self):
        if not self._pending_refresh:
            return
        self._pending_refresh = False

        nx_graph = self.full_graph
        cached_suspicious = self.cached_suspicious
        cached_incidents = self.cached_incidents
        evidence_classifications = self.evidence_classifications

        if nx_graph.number_of_edges() == 0:
            self._clear_scene()
            self._set_empty_waiting()
            self.empty_label.show()
            self.empty_label.resize(self.view.size())
            self._update_summary(nx_graph)
            return

        filtered_graph = self.filter_graph(
            nx_graph, cached_suspicious, cached_incidents, evidence_classifications
        )
        filtered_graph = self._collapse_simple(filtered_graph)
        self._update_summary(filtered_graph)

        if filtered_graph.number_of_edges() == 0 or filtered_graph.number_of_nodes() == 0:
            self._clear_scene()
            self.empty_label.setText(
                "No links match this filter.\n\n"
                "Choose “All links” or switch to Simple view."
            )
            self.empty_label.show()
            self.empty_label.resize(self.view.size())
            return

        snapshot = self._snapshot_for_layout(filtered_graph)

        if self._is_layout_running:
            self._pending_refresh = True
            return

        self._current_graph = snapshot

        self.empty_label.setText("Arranging the graph…")
        self.empty_label.show()
        self.empty_label.resize(self.view.size())

        self._is_layout_running = True
        self._layout_request_id += 1
        self._active_request_id = self._layout_request_id
        self._layout_request.emit(self._active_request_id, snapshot)

    @Slot(int, object)
    def on_layout_finished(self, request_id: int, pos):
        if request_id != self._active_request_id:
            return

        self._is_layout_running = False

        if pos is None:
            self.empty_label.setText("Error computing layout.")
            self.empty_label.show()
            if self._pending_refresh:
                QTimer.singleShot(50, self._flush_pending_update)
            return

        self._clear_scene()
        self.empty_label.hide()
        self._node_items = {}

        node_items = {}
        scale_factor = 520

        for node, data in self._current_graph.nodes(data=True):
            item = GraphNodeItem(node, data, self)
            if node in pos:
                x, y = pos[node]
                item.setPos(x * scale_factor, y * scale_factor)
            self.scene.addItem(item)
            node_items[node] = item

        for u, v, data in self._current_graph.edges(data=True):
            if u in node_items and v in node_items:
                item = GraphEdgeItem(
                    node_items[u], node_items[v], data, self, show_label=False
                )
                self.scene.addItem(item)

        self._node_items = node_items
        self._request_dns_for_visible_ips()
        QTimer.singleShot(0, self._fit_graph_to_view)

        if self._pending_refresh:
            QTimer.singleShot(50, self._flush_pending_update)

    def _fit_graph_to_view(self):
        """Zoom so the whole graph is visible. Called after a fresh layout only."""
        if not self._node_items:
            return
        self.view.resetTransform()
        rect = self.scene.itemsBoundingRect()
        if rect.isNull() or rect.width() < 1 or rect.height() < 1:
            return
        margin = 80
        padded = rect.adjusted(-margin, -margin, margin, margin)
        self.view.fitInView(padded, Qt.AspectRatioMode.KeepAspectRatio)

    def _request_dns_for_visible_ips(self):
        ips = []
        for node_id, data in self._current_graph.nodes(data=True):
            if infer_node_type(node_id, data) != "IP":
                continue
            ip = data.get("ip") or str(node_id)
            if ip and ip not in DNS_CACHE:
                ips.append(ip)
            elif DNS_CACHE.get(ip):
                self.on_hostname_resolved(ip, DNS_CACHE[ip])
        if ips:
            self._dns_request.emit(ips)

    @Slot(str, str)
    def on_hostname_resolved(self, ip: str, hostname: str):
        if not hostname:
            return
        item = self._node_items.get(ip)
        if item is None:
            for node_id, node_item in self._node_items.items():
                if infer_node_type(node_id, node_item.node_data) == "IP" and (
                    node_item.node_data.get("ip") == ip or str(node_id) == ip
                ):
                    item = node_item
                    break
        if item is None:
            return
        item.node_data["hostname"] = hostname
        item.refresh_label()
        if self._current_graph.has_node(item.node_id):
            self._current_graph.nodes[item.node_id]["hostname"] = hostname
        if self.full_graph.has_node(item.node_id):
            self.full_graph.nodes[item.node_id]["hostname"] = hostname
                
    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Do not re-fit on every resize — that resets the user's zoom/pan.
        if self.empty_label.isVisible():
            self.empty_label.resize(self.view.size())

    def show_node_details(self, node_id, node_data):
        primary, subtitle, ntype = node_display(node_id, node_data)
        type_title = TYPE_TITLES.get(ntype, ntype or "Entity")
        color = NODE_COLORS.get(ntype, NODE_COLORS["unknown"]).name()

        html = f"<h3 style='color:{color};'>Story</h3>"
        html += f"<div style='font-size:16px; font-weight:bold; margin-bottom:8px;'>{primary}</div>"

        graph = self._current_graph if self._current_graph.number_of_nodes() else self.full_graph
        out_lines = []
        in_lines = []
        if graph is not None and node_id in graph:
            for _, target, data in graph.out_edges(node_id, data=True):
                rel = data.get("relationship_type") or data.get("type") or "related"
                t_primary, _, t_type = node_display(target, graph.nodes.get(target, {}))
                out_lines.append(
                    f"{primary} {EDGE_LABELS.get(rel, rel)} {t_primary}"
                )
            for source, _, data in graph.in_edges(node_id, data=True):
                rel = data.get("relationship_type") or data.get("type") or "related"
                s_primary, _, s_type = node_display(source, graph.nodes.get(source, {}))
                in_lines.append(
                    f"{s_primary} {EDGE_LABELS.get(rel, rel)} {primary}"
                )

        if ntype == "Process":
            html += (
                f"<p><b>{primary}</b> is a program that ran on this PC.</p>"
            )
            if out_lines:
                html += "<p>What it did:</p><ul>"
                for line in out_lines:
                    html += f"<li>{line}</li>"
                html += "</ul>"
            else:
                html += "<p style='color:#666;'>No internet links from this program in the current view.</p>"
            if node_data.get("collapsed") or node_data.get("pids"):
                pids = node_data.get("pids") or []
                html += (
                    f"<p style='color:#666;'>Simple view combines every copy of this program. "
                    f"Switch to Detailed view to see each process ID separately"
                )
                if pids:
                    html += f" ({', '.join(str(p) for p in pids[:8])})"
                html += ".</p>"
            elif node_data.get("pid"):
                html += f"<p style='color:#666;'>Process ID: {node_data.get('pid')}</p>"
        elif ntype == "IP":
            ip = node_data.get("ip") or str(node_id)
            hostname = node_data.get("hostname") or DNS_CACHE.get(ip) or ""
            service = friendly_service_name(hostname) if hostname else primary
            html += (
                f"<p><b>{service}</b> is an internet destination. "
                f"A local program opened a connection to it.</p>"
            )
            html += f"<p><b>IP:</b> {ip}<br/><b>DNS name:</b> {hostname or 'not resolved'}</p>"
            if in_lines:
                html += "<p>Who contacted it:</p><ul>"
                for line in in_lines:
                    html += f"<li>{line}</li>"
                html += "</ul>"
            html += (
                "<p style='color:#666;'>Common services (GitHub, Google, AWS) are usually normal. "
                "Unexpected destinations may need a closer look.</p>"
            )
        elif ntype == "File":
            html += f"<p>This is a file on disk: <b>{primary}</b>.</p>"
            if out_lines or in_lines:
                html += "<ul>"
                for line in in_lines + out_lines:
                    html += f"<li>{line}</li>"
                html += "</ul>"
        elif ntype == "User":
            html += f"<p>User account: <b>{primary}</b>.</p>"
        elif ntype == "Device":
            html += f"<p>Removable / USB device related to nearby file or program activity.</p>"
        else:
            html += f"<p>{type_title}: {primary}</p>"

        html += f"<hr style='border: 1px dashed #555;'>"
        html += f"<span style='color:#888; font-size:11px;'>Internal ID: {node_id}</span>"

        incident_links = []
        for inc in getattr(self, 'cached_incidents', []):
            for n in inc.get('nodes', []):
                nid = n.get('id') if isinstance(n, dict) else n
                if nid == node_id or (self.simple_mode and ntype == "Process" and str(nid).endswith(f"_{primary}")):
                    incident_links.append(inc)
                    break
        if incident_links:
            html += f"<h4>Related incident cards</h4>"
            for inc in incident_links:
                html += f"<div style='padding: 4px; background-color: #1e1e1e; margin-bottom: 4px;'>"
                html += f"<b>{inc.get('incident_id')}</b> — {inc.get('status','')}<br/>"
                html += f"</div>"

        self.details_pane.setHtml(html)

    def show_edge_details(self, source_id, target_id, edge_data):
        rel = edge_data.get("relationship_type", edge_data.get("type", "Unknown"))
        friendly = EDGE_LABELS.get(rel, rel.replace("_", " ").lower())
        src_primary, _, src_type = node_display(source_id, self._current_graph.nodes.get(source_id, {}))
        dst_primary, _, dst_type = node_display(target_id, self._current_graph.nodes.get(target_id, {}))

        html = f"<h3>Relationship</h3>"
        html += f"<p style='font-size:14px;'><b>{src_primary}</b> {friendly} <b>{dst_primary}</b></p>"
        html += f"<b>From:</b> {TYPE_TITLES.get(src_type, src_type)} — {src_primary}<br/>"
        html += f"<b>To:</b> {TYPE_TITLES.get(dst_type, dst_type)} — {dst_primary}<br/>"
        html += f"<b>Confidence:</b> {edge_data.get('confidence', 'N/A')}<br/><br/>"

        reasons = edge_data.get("reasons", [])
        if reasons:
            html += "<b>Correlation Reasons:</b><ul>"
            for r in reasons:
                html += f"<li>{r}</li>"
            html += "</ul><br/>"

        ev_ids = edge_data.get("evidence_ids", [])
        if ev_ids:
            html += "<hr style='border: 1px dashed #555;'>"
            html += "<h4>Evidence Provenance</h4>"
            html += "<b>Supporting Evidence IDs:</b><ul>"
            for eid in ev_ids:
                html += f"<li>{eid}</li>"
            html += "</ul>"

        incidents_cache = getattr(self, 'cached_incidents', [])
        incident_matches = []
        for inc in incidents_cache:
            inc_evs = set(inc.get('evidence_ids', []))
            if inc_evs & set(ev_ids):
                incident_matches.append(inc)
        if incident_matches:
            html += "<br/><b>Incident(s) Supported by This Evidence:</b><ul>"
            for inc in incident_matches:
                html += f"<li>{inc.get('incident_id')} - {inc.get('status','')}</li>"
            html += "</ul>"

        self.details_pane.setHtml(html)
