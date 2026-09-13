import math
import networkx as nx
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QGraphicsView, QGraphicsScene,
    QGraphicsEllipseItem, QGraphicsLineItem, QGraphicsTextItem, QGraphicsItem,
    QTextEdit, QLabel, QSplitter, QComboBox
)
from PySide6.QtCore import Qt, QLineF, QThread, Signal, QObject
from PySide6.QtGui import QColor, QPen, QBrush, QFont, QTransform, QPainter

# Colors for nodes
NODE_COLORS = {
    "Process": QColor("#e74c3c"),
    "File": QColor("#f1c40f"),
    "IP": QColor("#3498db"),
    "User": QColor("#2ecc71"),
    "Device": QColor("#9b59b6"),
    "unknown": QColor("#95a5a6")
}

class GraphNodeItem(QGraphicsEllipseItem):
    def __init__(self, node_id, node_data, widget_ref):
        radius = 15
        super().__init__(-radius, -radius, radius * 2, radius * 2)
        self.node_id = node_id
        self.node_data = node_data
        self.widget_ref = widget_ref
        
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setZValue(1) # Render on top of edges
        
        node_type = node_data.get("type", "unknown")
        color = NODE_COLORS.get(node_type, NODE_COLORS["unknown"])
        
        self.setBrush(QBrush(color))
        self.setPen(QPen(Qt.GlobalColor.black, 1))
        
        # Label
        label_text = str(self.node_id)
        # Truncate label if it's too long
        if len(label_text) > 25:
            label_text = label_text[:22] + "..."
            
        self.label = QGraphicsTextItem(label_text, self)
        font = QFont("Arial", 8, QFont.Weight.Bold)
        self.label.setFont(font)
        # Center the label below the node
        br = self.label.boundingRect()
        self.label.setPos(-br.width() / 2, radius + 2)
        
        self.edges = []
        
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
    def __init__(self, source_item, target_item, edge_data, widget_ref):
        super().__init__()
        self.source_item = source_item
        self.target_item = target_item
        self.edge_data = edge_data
        self.widget_ref = widget_ref
        
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setZValue(0) # Render below nodes
        
        self.setPen(QPen(Qt.GlobalColor.gray, 2, Qt.PenStyle.SolidLine))
        
        self.label = QGraphicsTextItem(f"{edge_data.get('relationship_type', '')}\nConf: {edge_data.get('confidence', '')}", self)
        self.label.setFont(QFont("Arial", 7))
        self.label.setDefaultTextColor(Qt.GlobalColor.darkGray)
        
        self.source_item.add_edge(self)
        self.target_item.add_edge(self)
        
        self.update_position()
        
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
    finished = Signal(object)
    
    def __init__(self, nx_graph):
        super().__init__()
        self.nx_graph = nx_graph.copy()
        
    def compute(self):
        try:
            pos = nx.spring_layout(self.nx_graph, k=2.0, iterations=50)
            self.finished.emit(pos)
        except Exception as e:
            print(f"Error in layout thread: {e}")
            self.finished.emit(None)

class InteractiveGraphWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left: Graph View and Filter
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        self.filter_combo = QComboBox()
        self.filter_combo.addItems([
            "ALL", "USER ACTIVITY", "BACKGROUND", "SUSPICIOUS",
            "CORRELATED", "UNKNOWN", "INCIDENT RELATED"
        ])
        self.filter_combo.setCurrentText("ALL")
        self.filter_combo.currentTextChanged.connect(self.on_filter_changed)
        
        self.diagnostic_label = QLabel("Graph Nodes: 0 | Graph Relationships: 0 | Current Filter: ALL")
        self.diagnostic_label.setStyleSheet("color: #888; font-size: 11px; padding: 2px;")
        
        self.scene = QGraphicsScene()
        self.view = ZoomableView(self.scene)
        
        left_layout.addWidget(self.filter_combo)
        left_layout.addWidget(self.diagnostic_label)
        left_layout.addWidget(self.view)
        
        # Empty state label inside view
        self.empty_label = QLabel("Waiting for correlations... (No relationships found yet)", self.view)
        self.empty_label.setStyleSheet("color: gray; font-size: 16px; font-weight: bold;")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Right: Details Pane
        self.details_pane = QTextEdit()
        self.details_pane.setReadOnly(True)
        self.details_pane.setHtml("<p style='color: gray;'>Select a node or edge to view details.</p>")
        
        splitter.addWidget(left_widget)
        splitter.addWidget(self.details_pane)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        
        layout.addWidget(splitter)
        
    def on_filter_changed(self, text):
        if hasattr(self, 'full_graph') and hasattr(self, 'cached_suspicious') and hasattr(self, 'cached_incidents'):
            evidence_class = getattr(self, 'evidence_classifications', {})
            self.update_graph(self.full_graph, self.cached_suspicious, self.cached_incidents, evidence_class)
            
    def filter_graph(self, nx_graph, cached_suspicious, cached_incidents, evidence_classifications=None):
        if evidence_classifications is None:
            evidence_classifications = {}

        filter_text = self.filter_combo.currentText()
        if filter_text == "ALL":
            return nx_graph

        nodes_to_keep = set()

        if filter_text == "SUSPICIOUS":
            for act in cached_suspicious:
                nodes_to_keep.update(act["nodes"])
        elif filter_text == "INCIDENT RELATED":
            for inc in cached_incidents:
                for node in inc["nodes"]:
                    nodes_to_keep.add(node["id"])
        elif filter_text in ("USER ACTIVITY", "BACKGROUND", "CORRELATED", "UNKNOWN"):
            target = {
                "USER ACTIVITY": "USER_ACTIVITY",
                "BACKGROUND": "BACKGROUND_ACTIVITY",
                "CORRELATED": "CORRELATED_ACTIVITY",
                "UNKNOWN": "UNKNOWN",
            }[filter_text]
            for u, v, data in nx_graph.edges(data=True):
                ev_ids = data.get("evidence_ids", [])
                if any(evidence_classifications.get(eid) == target for eid in ev_ids):
                    nodes_to_keep.add(u)
                    nodes_to_keep.add(v)
        elif filter_text == "PROCESSES":
            nodes_to_keep = {n for n, d in nx_graph.nodes(data=True) if d.get('type') == 'Process'}
        elif filter_text == "FILES":
            nodes_to_keep = {n for n, d in nx_graph.nodes(data=True) if d.get('type') == 'File'}
        elif filter_text == "NETWORK":
            nodes_to_keep = {n for n, d in nx_graph.nodes(data=True) if d.get('type') == 'IP'}
        elif filter_text == "USERS":
            nodes_to_keep = {n for n, d in nx_graph.nodes(data=True) if d.get('type') == 'User'}
        elif filter_text == "DEVICES":
            nodes_to_keep = {n for n, d in nx_graph.nodes(data=True) if d.get('type') == 'Device'}

        return nx_graph.subgraph(nodes_to_keep)

    def update_graph(self, nx_graph, cached_suspicious=[], cached_incidents=[], evidence_classifications=None):
        if evidence_classifications is None:
            evidence_classifications = {}
        self.full_graph = nx_graph
        self.cached_suspicious = cached_suspicious
        self.cached_incidents = cached_incidents
        self.evidence_classifications = evidence_classifications
        filtered_graph = self.filter_graph(nx_graph, cached_suspicious, cached_incidents, evidence_classifications)
        
        self.diagnostic_label.setText(f"Graph Nodes: {nx_graph.number_of_nodes()} | Graph Relationships: {nx_graph.number_of_edges()} | Current Filter: {self.filter_combo.currentText()}")
        
        if nx_graph.number_of_edges() == 0:
            self.scene.clear()
            self.empty_label.setText("No relationships have been generated from the available evidence.")
            self.empty_label.show()
            self.empty_label.resize(self.view.size())
            return
            
        if filtered_graph.number_of_edges() == 0 or filtered_graph.number_of_nodes() == 0:
            self.scene.clear()
            self.empty_label.setText("No relationships match the current filter.")
            self.empty_label.show()
            self.empty_label.resize(self.view.size())
            return
            
        self.empty_label.setText("Calculating Graph Layout...")
        self.empty_label.show()
        self.empty_label.resize(self.view.size())
        
        if getattr(self, '_is_layout_running', False):
            self.pending_graph = nx_graph
            return
            
        self._is_layout_running = True
        self.pending_graph = nx_graph
        self._current_graph = filtered_graph
        self.layout_thread = QThread(self)
        self.layout_worker = GraphLayoutWorker(filtered_graph)
        self.layout_worker.moveToThread(self.layout_thread)
        self.layout_thread.started.connect(self.layout_worker.compute)
        self.layout_worker.finished.connect(self.on_layout_finished)
        self.layout_worker.finished.connect(self.layout_thread.quit)
        self.layout_worker.finished.connect(self.layout_worker.deleteLater)
        self.layout_thread.finished.connect(self.layout_thread.deleteLater)
        self.layout_thread.start()

    def on_layout_finished(self, pos):
        self._is_layout_running = False
        
        if pos is None:
            self.empty_label.setText("Error computing layout.")
            return
            
        self.scene.clear()
        self.empty_label.hide()
        
        node_items = {}
        scale_factor = 400
        
        for node, data in self._current_graph.nodes(data=True):
            item = GraphNodeItem(node, data, self)
            if node in pos:
                x, y = pos[node]
                item.setPos(x * scale_factor, y * scale_factor)
            self.scene.addItem(item)
            node_items[node] = item
            
        for u, v, data in self._current_graph.edges(data=True):
            if u in node_items and v in node_items:
                item = GraphEdgeItem(node_items[u], node_items[v], data, self)
                self.scene.addItem(item)
                
        # Check if a new graph was requested while we were calculating
        if hasattr(self, 'pending_graph') and self.pending_graph != self._current_graph:
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, lambda: self.update_graph(self.pending_graph, self.cached_suspicious, self.cached_incidents))
                
    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.empty_label.isVisible():
            self.empty_label.resize(self.view.size())

    def show_node_details(self, node_id, node_data):
        html = f"<h3>Entity Node</h3>"
        html += f"<b>ID:</b> {node_id}<br/>"
        html += f"<b>Type:</b> {node_data.get('type', 'unknown')}<br/><br/>"
        for k, v in node_data.items():
            if k not in ['id', 'type', 'label']:
                html += f"<b>{str(k).capitalize()}:</b> {v}<br/>"

        full_graph = getattr(self, 'full_graph', None)
        incident_links = []
        incidents_cache = getattr(self, 'cached_incidents', [])
        for inc in incidents_cache:
            for n in inc.get('nodes', []):
                if isinstance(n, dict) and n.get('id') == node_id:
                    incident_links.append(inc)
                    break
        if incident_links:
            html += f"<hr style='border: 1px dashed #555;'>"
            html += f"<h4>Involved in Potential Incidents</h4>"
            for inc in incident_links:
                html += f"<div style='padding: 4px; background-color: #1e1e1e; margin-bottom: 4px;'>"
                html += f"<b>{inc.get('incident_id')}</b> - {inc.get('status','')}<br/>"
                ev_ids = inc.get('evidence_ids', [])
                if ev_ids:
                    html += f"Evidence IDs: {', '.join(ev_ids)}<br/>"
                html += f"</div>"

        self.details_pane.setHtml(html)

    def show_edge_details(self, source_id, target_id, edge_data):
        html = f"<h3>Relationship (Edge)</h3>"
        html += f"<b>Source Entity:</b> {source_id}<br/>"
        html += f"<b>Target Entity:</b> {target_id}<br/>"
        html += f"<b>Relationship Type:</b> {edge_data.get('relationship_type', edge_data.get('type', 'Unknown'))}<br/>"
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
