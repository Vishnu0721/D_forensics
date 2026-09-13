# Evidence-Backed Forensic Monitor - Technical Audit Report

## 1. System Components Audit (1-15)

1. **Current Process Collector**: Polling-based (`psutil.process_iter`), runs every 2s.
2. **Current Network Collector**: Polling-based (`psutil.net_connections`), runs every 3s.
3. **Current Filesystem Collector**: Event-based (`watchdog`), but only monitors user profiles (Downloads/Desktop/Documents).
4. **Live telemetry data structures**: Emits plain Python dictionaries containing raw fields which are serialized to JSON in memory.
5. **EvidenceArtifact creation & SHA-256**: Generates SHA-256 hashes from the in-memory JSON string of live events. Original path is set to a virtual `memory://live-telemetry`.
6. **Evidence provenance & evidence_ids**: Maintained logically in the database via foreign keys (`ForensicEvent.evidence_id`), but physically the raw evidence data is discarded after hashing.
7. **Normalization pipeline**: Maps heterogeneous data into a unified `ForensicEvent` schema. Support exists for windows_log, browser, filesystem, process, network, and usb.
8. **Correlation rules & confidence calculations**: Deterministic rules with sliding windows. Confidence is calculated using a weighted temporal score.
9. **NetworkX graph construction & persistence**: Uses `MultiDiGraph`. Saves to a JSON file on disk after every correlation run.
10. **Incident reconstruction algorithm**: Extremely rudimentary. Just groups weakly connected components in the graph.
11. **Timeline generation**: Basic chronological sorting of database events with human-readable formatting.
12. **PySide6 dashboard architecture**: Monolithic structure. Relies heavily on QTimer and UI-thread processing for expensive operations.
13. **Evidence Graph UI**: Uses `QGraphicsView` with `nx.spring_layout` for node positioning.
14. **Incident Summary UI**: Simple HTML text rendering populated by graph connected components.
15. **Evidence Integrity UI**: The UI table exists but is completely disconnected from backend logic (never populated).

---

## 2. Feature States & Risks (A-G)

### A. Fully Implemented
- The PySide6 base layout (tabs, splitters, lists).
- SQLAlchemy database schema and models.
- The Normalization pipeline architecture for static parsing.

### B. Partially Implemented
- **Graph Construction**: Works functionally but lacks efficiency and deduplication.
- **Process/Network/Filesystem Collectors**: Miss short-lived events (polling interval too long) and miss system directories.
- **Timeline & Reconstruction**: Too basic. Reconstruction treats any two connected events as an "incident".

### C. Broken
- **Evidence Integrity Verification**: `integrity.py` uses `os.path.exists()` which always fails for `memory://live-telemetry`. Live event hashes cannot be verified.
- **Integrity UI**: The "Verify Integrity" button is not connected, and the `integrity_table` is never updated.
- **Network Collector Process Mapping**: Requires administrative privileges on Windows to map PIDs to connections. Fails silently otherwise.

### D. Missing
- **Physical Persistence of Live Telemetry**: Live telemetry JSON is not saved to disk, breaking the chain of custody.
- **Threaded Layout Computation**: `nx.spring_layout` is missing a background thread implementation.
- **Graph Edge Deduplication**: No mechanism to prevent duplicate edges.

### E. Duplicate Relationship Risks
- **CRITICAL RISK in `main_window.py`**: On every new event, the system queries the last 50 events and runs `correlate_events`. It then calls `populate_from_correlations` which uses a `MultiDiGraph`. Because the 50-event window heavily overlaps with the previous tick, the exact same relationships are injected repeatedly, causing exponential edge duplication.

### F. Data-Flow Problems between Backend and GUI
- **UI Freezes**: `nx.spring_layout(nx_graph, iterations=50)` is executed on the main UI thread in `gui/graph_view.py`. As the graph grows, the UI will freeze on every new event.
- **I/O Bottlenecks**: Every correlation update calls `self.save()` in `graph.py` which dumps the entire graph to JSON on the main thread.

### G. Unsupported Forensic Inferences
- Cannot correlate a file hash on disk to a running process because the `ProcessCollector` doesn't hash the executables in memory.
- Lacks command-line arguments parsing for processes.

---

## 3. Traceability Analysis: Live Event to Graph

**Traceability Path:** Live Event → EvidenceArtifact → SHA-256 → ForensicEvent → Correlation Relationship → NetworkX Graph → Incident → Supporting Evidence

**Verdict:** **PROVENANCE IS LOST.** 

While the database correctly links `ForensicEvent` back to an `EvidenceArtifact` via `evidence_id`, the system destroys the physical evidence. In `manager.py`, live telemetry is converted to JSON, hashed, and stored as an `EvidenceArtifact` with `original_path="memory://live-telemetry"`. The JSON file is never actually written to disk. 
When attempting to prove the origin of an incident in court, the system provides a SHA-256 hash but cannot produce the original JSON file that generated that hash.

---

## 4. File-by-File Audit

| Filename | Existing Responsibility | Current Status | Required Changes | Priority |
| :--- | :--- | :--- | :--- | :--- |
| **`core/monitoring/manager.py`** | Coordinates collectors and creates artifacts. | **BROKEN / DATA LOSS** | Must save `raw_json` to a physical file in a secure directory instead of discarding it. | **CRITICAL** |
| **`gui/main_window.py`** | Main UI and event correlation loop. | **POOR PERFORMANCE / LOGIC FLAW** | Fix continuous correlation overlapping (pass only new events or deduplicate). Connect Integrity UI logic. | **CRITICAL** |
| **`gui/graph_view.py`** | Renders NetworkX graph. | **UI BLOCKING** | Move `nx.spring_layout` to a background `QThread` or `QRunnable` to prevent UI freezing. | **HIGH** |
| **`core/services/correlation.py`** | Rule-based event linking. | **PARTIAL** | Add edge deduplication logic to avoid `MultiDiGraph` explosion from overlapping sliding windows. | **HIGH** |
| **`core/services/integrity.py`** | Calculates and verifies SHA-256 hashes. | **BROKEN FOR LIVE DATA** | Needs to support reading from the physically saved JSON files (once `manager.py` is fixed). | **HIGH** |
| **`core/monitoring/process.py`** | Captures process executions. | **PARTIAL** | Should capture the SHA-256 hash of the binary and command-line arguments. | **MEDIUM** |
| **`core/monitoring/filesystem.py`**| Captures file creations/deletions. | **PARTIAL** | Needs to monitor more than just user profiles (e.g., AppData, System32, Temp). | **MEDIUM** |
| **`core/monitoring/network.py`** | Captures active connections. | **PARTIAL** | Polling misses fast connections. Needs ETW or similar for robust Windows network monitoring. | **LOW** |
| **`core/services/graph.py`** | NetworkX operations and JSON persistence. | **I/O BOTTLENECK** | Debounce `self.save()` calls or move to an asynchronous writer. | **MEDIUM** |
| **`core/services/reconstruction.py`**| Groups related events. | **PARTIAL** | Implement better heuristics than just weakly connected components. | **LOW** |
| **`core/services/timeline.py`** | Chronological event list. | **FUNCTIONAL** | N/A | **LOW** |
| **`core/services/normalization.py`**| Maps fields to schema. | **FUNCTIONAL** | N/A | **LOW** |
| **`core/database/models.py`** | SQLAlchemy schema. | **FUNCTIONAL** | N/A | **LOW** |
| **`core/database/engine.py`** | DB Connection. | **FUNCTIONAL** | N/A | **LOW** |
