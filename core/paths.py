"""Filesystem locations for runtime data.

Everything is anchored to the project folder (not the current working directory)
so the filesystem collector can reliably exclude the app's own writes.
Set FORENSICS_DATA_DIR to relocate runtime data (tests use a temp folder).
"""
import os

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_ROOT = os.path.abspath(os.environ.get("FORENSICS_DATA_DIR") or PROJECT_ROOT)

DB_PATH = os.path.join(DATA_ROOT, "forensics.db")
DATA_DIR = os.path.join(DATA_ROOT, "data")
EVIDENCE_DIR = os.path.join(DATA_DIR, "evidence")
LOGS_DIR = os.path.join(DATA_ROOT, "logs")

DEBUG_LOGGING = os.environ.get("FORENSICS_DEBUG", "").strip().lower() in ("1", "true", "yes")
