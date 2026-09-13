# Digital Forensics Monitoring and Correlation Platform

A Python-based forensic monitoring and digital evidence analysis application designed for capturing live system telemetry, normalizing events, correlating suspicious behavior, and reconstructing incidents from evidence.

This project combines desktop monitoring, evidence integrity validation, graph-based analysis, and offline evidence ingestion into a single investigative workflow. It is intended for cybersecurity, forensic investigation, academic research, and digital evidence triage.

## Overview

The application is built around a forensic evidence pipeline:

1. Collect raw telemetry from the local machine.
2. Persist evidence artifacts to disk with deterministic SHA-256 hashing.
3. Normalize heterogeneous events into a common event schema.
4. Correlate related events using rule-based logic.
5. Build a relationship graph for investigation and incident reconstruction.
6. Classify suspicious activity and present findings in a desktop dashboard.

The project is implemented in Python using PySide6 for the GUI, SQLAlchemy for metadata storage, and NetworkX for graph construction and evidence linkage.

## Key Features

### Live Monitoring
- Process activity collection
- File system event tracking
- Live network connection monitoring
- Real-time evidence capture
- Event stream and timeline visualization

### Evidence Handling
- Evidence artifact creation for every captured event
- SHA-256 hashing of captured evidence files
- Traceability between events and their original evidence
- Integrity verification against stored hashes

### Analysis and Correlation
- Normalization of multiple source types into a single event model
- Rule-based correlation of suspicious or related events
- Multi-relationship graph construction with evidence nodes and event links
- Incident reconstruction from connected event patterns
- Suspicious activity identification and classification

### Offline Investigation Support
- Support for preserved evidence files in structured forensic formats
- Evidence ingestion from imported artifacts
- Offline parsing and event normalization
- Graph-based analysis on imported evidence

### Desktop Interface
- Main monitoring dashboard
- Evidence graph visualization
- Incident summary display
- Event detail inspection
- Integrity verification table

## System Architecture

The project follows a layered design:

- Core database layer for case and evidence storage
- Monitoring layer for process, file, and network collection
- Normalization layer for converting raw data into forensic events
- Correlation and graph services for connecting related activity
- Integrity and suspicious activity analysis modules
- GUI layer for visualization and investigator workflows

## Project Structure

```text
.
├── core/
│   ├── database/
│   │   ├── __init__.py
│   │   ├── engine.py
│   │   └── models.py
│   ├── monitoring/
│   │   ├── base.py
│   │   ├── filesystem.py
│   │   ├── manager.py
│   │   ├── network.py
│   │   └── process.py
│   └── services/
│       ├── classification.py
│       ├── correlation.py
│       ├── graph.py
│       ├── ingestion.py
│       ├── integrity.py
│       ├── normalization.py
│       ├── offline_analysis.py
│       ├── reconstruction.py
│       ├── report_parser.py
│       ├── suspicious.py
│       ├── sysmon_adapter.py
│       └── timeline.py
├── gui/
│   ├── __init__.py
│   ├── graph_view.py
│   ├── main_window.py
│   └── offline_analysis_window.py
├── data/
│   └── evidence/
├── evaluation/
│   └── run_evaluation.py
├── main.py
├── requirements.txt
├── technical_audit_report.md
├── test_phase1.py
├── test_fs.py
├── test_offline_analysis.py
├── test_sysmon_adapter.py
├── test_csv_and_imports.py
├── burst_test.py
├── forensics.db
└── README.md
```

## Requirements

Python 3.10+ is recommended.

Install all project dependencies with:

```bash
pip install -r requirements.txt
```

### Dependency Highlights

- PySide6: GUI framework
- SQLAlchemy: database ORM
- networkx: evidence graph modeling
- pandas: data handling
- psutil: system process and resource information
- watchdog: file system event monitoring
- neo4j: graph database support integration
- pydantic: data validation

## Installation and Setup

1. Clone the repository
2. Create a virtual environment
3. Activate the environment
4. Install dependencies
5. Run the application

### Example

```bash
git clone https://github.com/Kamalika-k/Digital_forensics.git
cd Digital_forensics
python -m venv venv
source venv/bin/activate   # Linux/macOS
# or
venv\Scripts\activate      # Windows
pip install -r requirements.txt
python main.py
```

## Running the Application

Launch the desktop application using:

```bash
python main.py
```

This starts the forensics dashboard, where the investigator can:
- start or stop live monitoring
- inspect events in the event stream
- review suspicious activity
- examine the evidence graph
- inspect incident summaries
- validate evidence integrity

## Testing

The repository includes several test scripts to validate monitoring, offline evidence ingestion, file-system behavior, and Sysmon compatibility.

Run tests individually or as a suite using Python modules such as:

```bash
python -m pytest
```

Example targeted checks:

```bash
python test_phase1.py
python test_fs.py
python test_offline_analysis.py
python test_sysmon_adapter.py
```

## Evidence Workflow

The project follows a typical forensic evidence lifecycle:

```text
Collect raw events
    ↓
Persist artifact to disk
    ↓
Compute SHA-256 hash
    ↓
Normalize into forensic schema
    ↓
Store in database
    ↓
Correlate and graph related events
    ↓
Classify suspicious activity
    ↓
Reconstruct incident timeline
```

## Data Model

The system uses a relational database with evidence and event tables:

- Case
- EvidenceArtifact
- ForensicEvent
- AuditLog

Each event references its associated evidence artifact, making it easier to trace the event back to the original preserved source record.

## Known Notes and Limitations

This project is a research-oriented forensic monitoring prototype. Some components are still under active development and may have limitations depending on the operating system and environment.

Examples include:
- live monitoring precision depending on polling intervals
- Windows-specific privilege requirements for deeper network inspection
- graph correlation performance for large event volumes
- extension of evidence integrity features for all live telemetry sources

The technical audit report in this repository documents many implementation observations and improvement opportunities.

## Related Documentation

- [technical_audit_report.md](technical_audit_report.md) – project audit and technical observations
- [evaluation/run_evaluation.py](evaluation/run_evaluation.py) – evaluation automation entry point

## Contribution

This repository is suitable for academic use and forensic tool experimentation. Contributions, improvements, and refinements are welcome.

## Notes

This project is designed as a forensic monitoring and evidence exploration platform. It should be used responsibly and only in environments where you have proper authorization to investigate system activity.

---

For any forensic or research use, maintain chain-of-custody discipline and preserve original evidence before making changes or reprocessing files.
