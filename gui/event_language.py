"""Plain-language helpers for event stream and details panels."""
from __future__ import annotations

import os
from typing import Any, Dict, Optional, Tuple

from PySide6.QtGui import QColor

from gui.graph_view import friendly_service_name, DNS_CACHE

# Filter UI label -> internal classification / special key
FILTER_OPTIONS = [
    ("All activity", "ALL"),
    ("User actions", "USER_ACTIVITY"),
    ("Background noise", "BACKGROUND_ACTIVITY"),
    ("Needs attention", "SUSPICIOUS_ACTIVITY"),
    ("Linked activity", "CORRELATED_ACTIVITY"),
    ("Unclear", "UNKNOWN"),
    ("Part of an incident", "INCIDENT"),
]

FILTER_LABEL_TO_KEY = {label: key for label, key in FILTER_OPTIONS}
FILTER_KEY_TO_LABEL = {key: label for label, key in FILTER_OPTIONS}

CLASSIFICATION_LABELS = {
    "USER_ACTIVITY": "User action",
    "BACKGROUND_ACTIVITY": "Background noise",
    "SUSPICIOUS_ACTIVITY": "Needs attention",
    "CORRELATED_ACTIVITY": "Linked activity",
    "UNKNOWN": "Unclear",
}

SOURCE_COLORS = {
    "process": QColor("#ffcc80"),
    "filesystem": QColor("#fff59d"),
    "network": QColor("#90caf9"),
    "browser": QColor("#ce93d8"),
    "usb": QColor("#b39ddb"),
    "windows_log": QColor("#a5d6a7"),
}


def _safe(val: Any, fallback: str = "") -> str:
    if val is None or val == "" or val == "Unavailable":
        return fallback
    return str(val)


def _basename(path: Optional[str]) -> str:
    if not path:
        return ""
    return os.path.basename(path.replace("/", os.sep))


def _pretty_process(name: Optional[str]) -> str:
    n = _safe(name)
    if not n:
        return "a program"
    if n.lower().endswith(".exe"):
        return n[:-4]
    return n


def _service_for_ip(ip: Optional[str]) -> str:
    if not ip:
        return "the internet"
    host = DNS_CACHE.get(ip) or ""
    service = friendly_service_name(host) if host else ""
    if service:
        return service
    return str(ip)


def format_event_sentence(event) -> str:
    """One-line human sentence for the live stream."""
    et = (event.event_type or "").lower()
    st = (event.source_type or "").lower()
    ts = event.timestamp.strftime("%H:%M:%S") if event.timestamp else "??:??:??"
    process = _pretty_process(event.process)
    file_name = _safe(event.file) or _basename(event.path)
    path = _safe(event.path)
    ip = _safe(event.ip)
    user = _safe(event.user)

    if et in ("process_started", "process_created"):
        return f"{ts}  {process} started"
    if et in ("process_terminated", "process_stopped"):
        return f"{ts}  {process} closed"
    if et == "connection":
        service = _service_for_ip(ip)
        who = process if process != "a program" else "A program"
        return f"{ts}  {who} contacted {service}"
    if et == "file_created":
        where = ""
        low = path.lower()
        if "download" in low:
            where = " in Downloads"
        elif "desktop" in low:
            where = " on Desktop"
        elif "document" in low:
            where = " in Documents"
        return f"{ts}  New file{where}: {file_name or path or 'unknown'}"
    if et == "file_modified":
        return f"{ts}  File changed: {file_name or path or 'unknown'}"
    if et == "file_deleted":
        return f"{ts}  File deleted: {file_name or path or 'unknown'}"
    if et == "file_moved":
        meta = event.metadata_json or {}
        dest = _basename(meta.get("path") or path) or file_name
        return f"{ts}  File moved/renamed: {dest or 'unknown'}"
    if et == "download":
        return f"{ts}  Download: {file_name or 'a file'}"
    if et in ("login", "logon"):
        return f"{ts}  User signed in: {user or 'someone'}"
    if et in ("usb_connected", "device_connected"):
        return f"{ts}  USB device connected"
    if et in ("usb_disconnected", "device_disconnected"):
        return f"{ts}  USB device removed"
    if st == "network":
        return f"{ts}  Network activity: {process} → {ip or 'remote host'}"
    if st == "filesystem":
        return f"{ts}  File activity: {file_name or path or et or 'change'}"
    if st == "process":
        return f"{ts}  Program activity: {process} ({et or 'update'})"
    return f"{ts}  {st or 'activity'}: {et or 'event'} {file_name or process or ip}".strip()


def format_event_summary_html(event, classification: Optional[Dict[str, str]] = None) -> str:
    """Short summary block for Event Details (plain language first)."""
    sentence = format_event_sentence(event)
    # Drop timestamp prefix for the heading sentence
    parts = sentence.split("  ", 1)
    headline = parts[1] if len(parts) > 1 else sentence
    et = (event.event_type or "").lower()
    tip = ""
    if et == "connection":
        tip = "This means a program on this PC opened a network link to another computer on the internet."
    elif et in ("process_started", "process_created"):
        tip = "A program began running on this PC."
    elif et.startswith("file_"):
        tip = "Something changed a file on disk (create, edit, move, or delete)."
    elif et in ("process_terminated", "process_stopped"):
        tip = "A program finished or was closed."

    cls = (classification or {}).get("classification", "UNKNOWN")
    cls_label = CLASSIFICATION_LABELS.get(cls, cls)
    reason = (classification or {}).get("reason", "")

    html = f"<h3 style='margin-bottom:4px;'>What happened</h3>"
    html += f"<p style='font-size:15px; font-weight:bold;'>{headline}</p>"
    if tip:
        html += f"<p style='color:#555;'>{tip}</p>"
    html += f"<p><b>Category:</b> {cls_label}<br/>"
    if reason:
        html += f"<b>Why:</b> {reason}</p>"
    else:
        html += "</p>"

    html += "<hr style='border:1px dashed #555;'/>"
    html += "<h4>Quick facts</h4>"
    html += f"<b>Time:</b> {event.timestamp.strftime('%Y-%m-%d %H:%M:%S') if event.timestamp else 'Unknown'}<br/>"
    if event.process:
        html += f"<b>Program:</b> {event.process}"
        if event.pid:
            html += f" (ID {event.pid})"
        html += "<br/>"
    if event.file or event.path:
        html += f"<b>File:</b> {event.file or _basename(event.path)}<br/>"
        if event.path:
            html += f"<b>Location:</b> {event.path}<br/>"
    if event.ip:
        html += f"<b>Internet destination:</b> {_service_for_ip(event.ip)} ({event.ip})"
        if event.port:
            html += f" port {event.port}"
        html += "<br/>"
    if event.user:
        html += f"<b>User:</b> {event.user}<br/>"
    return html


def format_event_advanced_html(event, integrity_block: str = "") -> str:
    """Technical fields collapsed under Advanced."""
    def safe_get(val):
        return val if val else "Unavailable"

    html = "<details open><summary><b>Advanced technical details</b></summary>"
    html += "<div style='margin-top:8px; font-family: Consolas, monospace; font-size:12px;'>"
    html += f"Event ID: {safe_get(event.id)}<br/>"
    html += f"Evidence ID: {safe_get(event.evidence_id)}<br/>"
    html += f"Source type: {safe_get(event.source_type)}<br/>"
    html += f"Event type: {safe_get(event.event_type)}<br/>"
    html += f"Host: {safe_get(event.host)}<br/>"
    html += f"Parent process: {safe_get(event.parent_process)}<br/>"
    meta = event.metadata_json if event.metadata_json else {}
    if meta.get("old_path"):
        html += f"Old path: {meta.get('old_path')}<br/>"
    if meta.get("cmdline"):
        html += f"Command line: {meta.get('cmdline')}<br/>"
    html += "</div></details>"
    if integrity_block:
        html += integrity_block
    return html


def event_item_color(event) -> QColor:
    return SOURCE_COLORS.get((event.source_type or "").lower(), QColor("#cfd8dc"))


def filter_matches(
    filter_key: str,
    classification: str,
    evidence_id: Optional[str],
    incident_evidence_ids: set,
) -> bool:
    if filter_key == "ALL":
        return True
    if filter_key == "INCIDENT":
        return evidence_id in incident_evidence_ids if evidence_id else False
    return classification == filter_key
