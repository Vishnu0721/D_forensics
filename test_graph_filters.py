import os
import shutil
import tempfile
import atexit
from datetime import datetime, timedelta

_TEST_DATA_DIR = tempfile.mkdtemp(prefix="forensics_graphfilter_")
os.environ["FORENSICS_DATA_DIR"] = _TEST_DATA_DIR
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
atexit.register(shutil.rmtree, _TEST_DATA_DIR, ignore_errors=True)

from PySide6.QtWidgets import QApplication

from core.database.models import ForensicEvent
from core.services.classification import annotate_origins
from core.services.correlation import correlate_new_event
from core.services.graph import EvidenceGraph
from gui.graph_view import InteractiveGraphWidget

BASE = datetime(2026, 1, 1, 12, 0, 0)
CHROME_HASH = "a" * 64
_n = [0]


def ev(event_type, seconds, **fields):
    _n[0] += 1
    fields.setdefault("host", "PC-01")
    return ForensicEvent(case_id="c", evidence_id=f"ev{_n[0]}", source_type="test",
                         event_type=event_type, timestamp=BASE + timedelta(seconds=seconds), **fields)


def check(label, condition):
    assert condition, label
    print(f"PASS  {label}")


def build_graph():
    """Mirrors a real session: Chrome child processes, Chrome/Cursor/svchost connections."""
    events = [
        ev("process_started", 0, pid=101, process="chrome.exe", user="bob", file_hash=CHROME_HASH,
           path="C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"),
        ev("process_started", 1, pid=102, process="chrome.exe", user="bob", file_hash=CHROME_HASH,
           path="C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"),
        ev("process_started", 2, pid=103, process="chrome.exe", user="bob", file_hash=CHROME_HASH,
           path="C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"),
        ev("connection", 3, pid=100, process="chrome.exe", user="bob", ip="142.250.1.1", port=443),
        ev("connection", 4, pid=200, process="Cursor.exe", user="bob", ip="104.18.1.1", port=443),
        ev("connection", 5, pid=300, process="svchost.exe", ip="20.1.1.1", port=443),
    ]
    # Same path as the live CorrelationWorker (the batch correlator has no same-hash rule).
    rels = []
    for i, event in enumerate(events):
        rels.extend(correlate_new_event(event, events[:i], max_window_seconds=120))
    annotate_origins(rels, events)
    graph = EvidenceGraph("filters", storage_dir=tempfile.mkdtemp(dir=_TEST_DATA_DIR))
    graph.populate_from_correlations(rels)
    return graph


def programs(g):
    return sorted({d.get("process") for _n, d in g.nodes(data=True) if d.get("process")})


def main():
    app = QApplication.instance() or QApplication([])
    graph = build_graph()
    snap = graph.snapshot()
    widget = InteractiveGraphWidget()
    try:
        def filtered(option, simple=True):
            widget.filter_combo.setCurrentText(option)
            widget.simple_mode = simple
            return widget._collapse_simple(widget.filter_graph(snap, [], [], {}))

        check("'Linked activity' removed from graph filter (it equals 'All links')",
              widget.filter_combo.findText("Linked activity") == -1)

        g = filtered("User actions")
        check("User actions (Simple) shows Chrome contacting the internet",
              g.number_of_edges() == 1 and "142.250.1.1" in g.nodes)
        g = filtered("User actions", simple=False)
        check("User actions (Detailed) also shows the Chrome same-program links",
              g.number_of_edges() == 4 and programs(g) == ["chrome.exe"])

        g = filtered("Background noise")
        check("Background noise shows only svchost", programs(g) == ["svchost.exe"] and g.number_of_edges() == 1)

        g = filtered("Unclear")
        check("Unclear shows only Cursor", programs(g) == ["Cursor.exe"] and g.number_of_edges() == 1)

        # Restart: labels must come from the saved graph, not from this session's memory.
        graph.save(force=True)
        reloaded = EvidenceGraph("filters", storage_dir=graph.storage_dir).snapshot()
        widget.filter_combo.setCurrentText("Background noise")
        g = widget.filter_graph(reloaded, [], [], {})
        check("filters still work after reloading the saved graph", programs(g) == ["svchost.exe"])

        # Graphs saved before origins existed fall back to per-event labels.
        for _u, _v, d in reloaded.edges(data=True):
            d.pop("origins", None)
        widget.filter_combo.setCurrentText("Unclear")
        cursor_eid = next(e for _u, _v, d in reloaded.edges(data=True) for e in d["evidence_ids"]
                          if "Cursor" in str(d.get("reasons")))
        g = widget.filter_graph(reloaded, [], [], {cursor_eid: "UNKNOWN"})
        check("old graphs without origins fall back to event labels", programs(g) == ["Cursor.exe"])

        # Only same-program links match: Simple view explains instead of showing a blank graph.
        only_chrome = snap.copy()
        only_chrome.remove_nodes_from([n for n in list(only_chrome.nodes)
                                       if only_chrome.nodes[n].get("process") != "chrome.exe"
                                       or only_chrome.nodes[n].get("pid") == "100"])
        widget.filter_combo.setCurrentText("User actions")
        widget.simple_mode = True
        widget.full_graph = only_chrome
        widget._pending_refresh = True
        widget._flush_pending_update()
        check("Simple view explains merged same-program links", "Detailed" in widget.empty_label.text())
    finally:
        widget.cleanup()
    print("All graph filter tests passed.")


if __name__ == "__main__":
    main()
