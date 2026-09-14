"""Qt-free plain-language helpers for API DTOs."""

from __future__ import annotations

import os
from typing import Any, Optional

CLASSIFICATION_LABELS = {
    "USER_ACTIVITY": "User action",
    "BACKGROUND_ACTIVITY": "Background noise",
    "SUSPICIOUS_ACTIVITY": "Needs attention",
    "CORRELATED_ACTIVITY": "Linked activity",
    "UNKNOWN": "Unclear",
}

INTEGRITY_LABELS = {
    "VALID": "Unchanged",
    "MODIFIED": "Changed on disk",
    "UNVERIFIABLE": "File missing",
    "UNVERIFIED": "Not checked yet",
    "PENDING": "Not checked yet",
}

INTEGRITY_LEGEND = {
    "VALID": "The saved copy still matches its fingerprint.",
    "MODIFIED": "The file on disk no longer matches — do not trust it alone.",
    "UNVERIFIABLE": "The preserved file path cannot be read.",
    "PENDING": "Not checked yet — run Verify.",
}


def _safe(val: Any, fallback: str = "") -> str:
    if val is None or val == "" or val == "Unavailable":
        return fallback
    return str(val)


def _basename(path: Optional[str]) -> str:
    if not path:
        return ""
    return os.path.basename(str(path).replace("/", os.sep))


def _pretty_process(name: Optional[str]) -> str:
    n = _safe(name)
    if not n:
        return "a program"
    if n.lower().endswith(".exe"):
        return n[:-4]
    return n


def event_headline(event) -> str:
    et = (event.event_type or "").lower()
    st = (event.source_type or "").lower()
    process = _pretty_process(event.process)
    file_name = _safe(event.file) or _basename(event.path)
    path = _safe(event.path)
    ip = _safe(event.ip)
    user = _safe(event.user)

    if et in ("process_started", "process_created"):
        return f"{process} started"
    if et in ("process_terminated", "process_stopped"):
        return f"{process} closed"
    if et == "connection":
        who = process if process != "a program" else "A program"
        return f"{who} contacted {ip or 'the internet'}"
    if et == "file_created":
        where = ""
        low = path.lower()
        if "download" in low:
            where = " in Downloads"
        elif "desktop" in low:
            where = " on Desktop"
        elif "document" in low:
            where = " in Documents"
        return f"New file{where}: {file_name or path or 'unknown'}"
    if et == "file_modified":
        return f"File changed: {file_name or path or 'unknown'}"
    if et == "file_deleted":
        return f"File deleted: {file_name or path or 'unknown'}"
    if et == "download":
        return f"Download: {file_name or 'a file'}"
    if et in ("login", "logon"):
        return f"User signed in: {user or 'someone'}"
    if st == "network":
        return f"Network activity: {process} → {ip or 'remote host'}"
    if st == "filesystem":
        return f"File activity: {file_name or path or et or 'change'}"
    if st == "process":
        return f"Program activity: {process}"
    return f"{st or 'activity'}: {et or 'event'}"


def event_detail(event) -> str:
    et = (event.event_type or "").lower()
    if et == "connection":
        return "A program on this PC opened a network link to another computer."
    if et in ("process_started", "process_created"):
        return "A program began running on this PC."
    if et.startswith("file_"):
        return "Something changed a file on disk (create, edit, move, or delete)."
    if et in ("process_terminated", "process_stopped"):
        return "A program finished or was closed."
    if et in ("login", "logon"):
        return "A user session began on this host."
    return "Recorded forensic activity from imported evidence."


def severity_for_classification(classification: str) -> str:
    if classification == "SUSPICIOUS_ACTIVITY":
        return "Review recommended"
    return "Informational"


def technical_fields(event) -> dict:
    meta = event.metadata_json or {}
    return {
        "event_id": event.id,
        "evidence_id": event.evidence_id,
        "source_type": event.source_type,
        "event_type": event.event_type,
        "host": event.host,
        "user": event.user,
        "process": event.process,
        "pid": event.pid,
        "parent_process": event.parent_process,
        "file": event.file,
        "path": event.path,
        "ip": event.ip,
        "domain": event.domain,
        "port": event.port,
        "cmdline": meta.get("cmdline"),
        "old_path": meta.get("old_path"),
    }


def finding_from_suspicious(item: dict, index: int) -> dict:
    rule = item.get("rule_name") or item.get("rule") or item.get("type") or "Finding"
    reason = item.get("reason") or item.get("description") or ""
    score = float(item.get("score") or 0)
    label = "Review recommended" if score >= 0.5 else "Informational"
    related = item.get("evidence_ids") or item.get("event_ids") or []
    return {
        "id": str(item.get("activity_id") or f"rule-{index}-{rule}").replace(" ", "_"),
        "kind": "rule",
        "headline": str(rule).replace("_", " "),
        "detail": str(reason),
        "severity_label": label,
        "related_event_ids": [str(x) for x in related],
    }


def story_from_incident(item: dict, index: int) -> dict:
    title = (
        item.get("incident_id")
        or item.get("title")
        or item.get("summary")
        or f"Activity story {index + 1}"
    )
    timeline = item.get("timeline") or item.get("description") or item.get("reconstruction_reason") or ""
    if isinstance(timeline, list):
        timeline = " → ".join(str(x) for x in timeline[:8])
    review = (item.get("status") or "").lower() in ("requires investigation",) or bool(
        item.get("suspicious_activities")
    )
    related = item.get("evidence_ids") or item.get("event_ids") or []
    return {
        "id": str(item.get("incident_id") or f"story-{index}"),
        "kind": "story",
        "headline": str(title),
        "detail": str(timeline),
        "severity_label": "Review recommended" if review else "Informational",
        "related_event_ids": [str(x) for x in related],
    }
