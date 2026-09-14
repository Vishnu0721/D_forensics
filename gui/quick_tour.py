"""First-run quick tour for the forensic monitor."""
import os
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TOUR_FLAG_FILE = os.path.join(_ROOT, "data", ".quick_tour_seen")


def should_show_tour() -> bool:
    return not os.path.exists(TOUR_FLAG_FILE)


def mark_tour_seen():
    os.makedirs(os.path.dirname(TOUR_FLAG_FILE), exist_ok=True)
    with open(TOUR_FLAG_FILE, "w", encoding="utf-8") as f:
        f.write("1")


class QuickTourDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Quick tour — 30 seconds")
        self.setMinimumWidth(480)
        layout = QVBoxLayout(self)

        title = QLabel("How to use this app")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        layout.addWidget(title)

        steps = (
            "<ol style='line-height:1.6;'>"
            "<li>Click <b>Start Monitoring</b> — the banner turns green (LIVE).</li>"
            "<li>Open the <b>Activity</b> tab — plain sentences show what happens on this PC.</li>"
            "<li>Open a browser or save a file — you should see new lines within seconds.</li>"
            "<li>Open <b>Evidence Graph</b> — red = program, blue = internet service it contacted.</li>"
            "<li>Click <b>Stop Monitoring</b> when finished — evidence stays saved for review.</li>"
            "</ol>"
            "<p style='color:#555;'>This app watches <b>this computer only</b>. "
            "It is not a remote agent on other machines.</p>"
        )
        body = QLabel(steps)
        body.setWordWrap(True)
        body.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(body)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn = QPushButton("Got it — start using the app")
        btn.clicked.connect(self.accept)
        btn_row.addWidget(btn)
        layout.addLayout(btn_row)
