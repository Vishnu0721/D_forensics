import json
import csv
from datetime import datetime
from typing import List, Dict, Any, Generator, Optional
from sqlalchemy.orm import Session
from core.database.models import ForensicEvent, AuditLog

MAX_TIMESTAMP_FALLBACK_DATETIME = None

def parse_iso_datetime(dt_str: Any) -> datetime:
    if not dt_str:
        return datetime.utcnow()
    if isinstance(dt_str, datetime):
        return dt_str
    s = str(dt_str).strip()
    try:
        cleaned = s.replace('Z', '+00:00').replace('/', '-')
        return datetime.fromisoformat(cleaned)
    except (ValueError, TypeError):
        pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%m/%d/%Y %H:%M:%S", "%d-%m-%Y %H:%M:%S",
                "%Y-%m-%dT%H:%M:%S", "%m/%d/%Y %I:%M:%S %p", "%H:%M:%S"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return datetime.utcnow()


def _get(record: Dict[str, Any], *keys: str, default: Any = None) -> Any:
    for k in keys:
        if k in record and record[k] not in (None, ""):
            return record[k]
    return default

def _get_event_type(record: Dict[str, Any], *keys: str, default: str = 'unknown') -> str:
    val = _get(record, *keys, default=default)
    if not val:
        return default
    return str(val).strip().lower().replace(" ", "_").replace("-", "_")


def normalize_windows_log(record: Dict[str, Any], case_id: str, evidence_id: str) -> ForensicEvent:
    return ForensicEvent(
        case_id=case_id,
        evidence_id=evidence_id,
        timestamp=parse_iso_datetime(_get(record, 'timestamp', 'time_created', 'time')),
        source_type='windows_log',
        event_type=_get_event_type(record, 'event_type', 'event_id_name', 'type', default='unknown'),
        user=_get(record, 'user', 'username', 'target_user_name'),
        host=_get(record, 'host', 'computer', 'computer_name', 'hostname'),
        metadata_json=record
    )

def normalize_browser_log(record: Dict[str, Any], case_id: str, evidence_id: str) -> ForensicEvent:
    return ForensicEvent(
        case_id=case_id,
        evidence_id=evidence_id,
        timestamp=parse_iso_datetime(_get(record, 'timestamp', 'time', 'visit_time', 'download_time')),
        source_type='browser',
        event_type=_get_event_type(record, 'event_type', 'action', default='unknown'),
        user=_get(record, 'user', 'username'),
        host=_get(record, 'host', 'hostname'),
        file=_get(record, 'file', 'filename', 'downloaded_file', 'target_path'),
        domain=_get(record, 'url', 'domain', 'host', 'site'),
        metadata_json=record
    )

def normalize_filesystem_log(record: Dict[str, Any], case_id: str, evidence_id: str) -> ForensicEvent:
    return ForensicEvent(
        case_id=case_id,
        evidence_id=evidence_id,
        timestamp=parse_iso_datetime(_get(record, 'timestamp', 'time', 'creation_time', 'modification_time')),
        source_type='filesystem',
        event_type=_get_event_type(record, 'event_type', 'action', 'change_type', default='unknown'),
        user=_get(record, 'user', 'username', 'owner'),
        host=_get(record, 'host', 'hostname'),
        file=_get(record, 'file', 'filename', 'name', 'basename'),
        path=_get(record, 'path', 'full_path', 'filepath', 'new_path'),
        file_hash=_get(record, 'file_hash', 'sha256', 'hash'),
        metadata_json=record
    )

def normalize_process_log(record: Dict[str, Any], case_id: str, evidence_id: str) -> ForensicEvent:
    return ForensicEvent(
        case_id=case_id,
        evidence_id=evidence_id,
        timestamp=parse_iso_datetime(_get(record, 'timestamp', 'time', 'start_time', 'creation_time')),
        source_type='process',
        event_type=_get_event_type(record, 'event_type', 'action', default='unknown'),
        user=_get(record, 'user', 'username', 'owner', 'logon_user'),
        host=_get(record, 'host', 'hostname', 'computer'),
        process=_get(record, 'process', 'process_name', 'name', 'executable', 'image'),
        pid=_get(record, 'pid', 'process_id'),
        parent_process=_get(record, 'parent_process', 'parent', 'parent_name', 'parent_process_name'),
        path=_get(record, 'path', 'command_line', 'image_path', 'exe_path'),
        file_hash=_get(record, 'sha256', 'file_hash', 'hash', 'md5'),
        metadata_json=record
    )

def normalize_network_log(record: Dict[str, Any], case_id: str, evidence_id: str) -> ForensicEvent:
    return ForensicEvent(
        case_id=case_id,
        evidence_id=evidence_id,
        timestamp=parse_iso_datetime(_get(record, 'timestamp', 'time', 'connection_time')),
        source_type='network',
        event_type=_get_event_type(record, 'event_type', 'action', default='unknown'),
        user=_get(record, 'user', 'username', 'owner'),
        host=_get(record, 'host', 'hostname', 'local_host'),
        process=_get(record, 'process', 'process_name', 'image', 'owning_process'),
        pid=_get(record, 'pid', 'process_id', 'owning_pid'),
        ip=_get(record, 'ip', 'destination_ip', 'dest_ip', 'remote_ip', 'dst_ip'),
        port=_get(record, 'port', 'destination_port', 'dest_port', 'remote_port', 'dst_port'),
        domain=_get(record, 'domain', 'remote_host', 'hostname'),
        metadata_json=record
    )

def normalize_usb_log(record: Dict[str, Any], case_id: str, evidence_id: str) -> ForensicEvent:
    return ForensicEvent(
        case_id=case_id,
        evidence_id=evidence_id,
        timestamp=parse_iso_datetime(_get(record, 'timestamp', 'time', 'insertion_time', 'connection_time')),
        source_type='usb',
        event_type=_get_event_type(record, 'event_type', 'action', default='unknown'),
        user=_get(record, 'user', 'username', 'last_user'),
        host=_get(record, 'host', 'hostname', 'computer'),
        device_id=_get(record, 'device_id', 'serial_number', 'device', 'instance_id'),
        path=_get(record, 'drive_letter', 'volume', 'mount_point'),
        metadata_json=record
    )

NORMALIZERS = {
    'windows_log': normalize_windows_log,
    'browser': normalize_browser_log,
    'filesystem': normalize_filesystem_log,
    'process': normalize_process_log,
    'network': normalize_network_log,
    'usb': normalize_usb_log
}


def normalize_record(record: Dict[str, Any], source_type: str, case_id: str, evidence_id: str) -> ForensicEvent:
    normalizer = NORMALIZERS.get(source_type)
    if normalizer is None:
        normalizer = normalize_filesystem_log
    return normalizer(record, case_id, evidence_id)


def _has_value(record: Dict[str, Any], *keys: str) -> bool:
    for k in keys:
        v = record.get(k)
        if v is not None and str(v) != "":
            return True
    return False


def _infer_record_source_type(record: Dict[str, Any]) -> str:
    et = str(record.get("event_type", "")).lower() if _has_value(record, "event_type") else ""

    if et in ("connection", "disconnection") or \
       _has_value(record, "destination_ip", "remote_ip", "dst_ip", "ip"):
        return "network"

    if et in ("download", "visited", "url_visited") or \
       _has_value(record, "url", "browser", "tab"):
        return "browser"

    if et in ("usb_connected", "usb_disconnected", "device_connected") or \
       _has_value(record, "device_id", "usb", "serial_number", "drive_letter"):
        return "usb"

    if et in ("login", "logoff", "logon", "security_event") or \
       _has_value(record, "task_category", "security_id", "logon_id"):
        return "windows_log"

    if et in ("process_started", "process_stopped", "process_terminated", "process_created") or \
       _has_value(record, "parent_process", "command_line", "executable"):
        return "process"

    if et in ("file_created", "file_deleted", "file_modified", "file_accessed", "file_moved") or \
       (et == "download" and (_has_value(record, "file") or _has_value(record, "path"))):
        return "filesystem"

    if _has_value(record, "process", "pid"):
        return "process"

    if _has_value(record, "file", "path"):
        return "filesystem"

    return "filesystem"


def normalize_records(
    records: List[Dict[str, Any]],
    source_type: str,
    case_id: str,
    evidence_id: str
) -> Generator[ForensicEvent, None, None]:
    for rec in records:
        if not isinstance(rec, dict):
            continue
        try:
            per_record_source = _infer_record_source_type(rec)
            use_source = per_record_source if per_record_source in NORMALIZERS else source_type
            yield normalize_record(rec, use_source, case_id, evidence_id)
        except Exception:
            continue


def parse_and_normalize(file_path: str, source_type: str, case_id: str, evidence_id: str) -> Generator[ForensicEvent, None, None]:
    normalizer = NORMALIZERS.get(source_type)
    if not normalizer:
        raise ValueError(f"No normalizer registered for source type: {source_type}")
        
    if file_path.endswith('.json'):
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, dict):
                data = [data]
            for record in data:
                yield normalizer(record, case_id, evidence_id)
                
    elif file_path.endswith('.csv'):
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for record in reader:
                if 'pid' in record and record['pid']:
                    try: record['pid'] = int(record['pid'])
                    except: pass
                if 'destination_port' in record and record['destination_port']:
                    try: record['destination_port'] = int(record['destination_port'])
                    except: pass
                yield normalizer(record, case_id, evidence_id)
    else:
        raise ValueError(f"Unsupported file format for normalization: {file_path}")

def normalize_and_store(db: Session, file_path: str, source_type: str, case_id: str, evidence_id: str, actor: str) -> int:
    events = list(parse_and_normalize(file_path, source_type, case_id, evidence_id))
    if events:
        db.bulk_save_objects(events)
        
        audit = AuditLog(
            actor=actor,
            action="EVIDENCE_NORMALIZED",
            object_id=evidence_id,
            description=f"Normalized {len(events)} events from evidence {evidence_id}"
        )
        db.add(audit)
        db.commit()
    return len(events)


def bulk_store_events(db: Session, events: List[ForensicEvent], evidence_id: str, actor: str) -> int:
    if not events:
        return 0
    db.bulk_save_objects(events)
    audit = AuditLog(
        actor=actor,
        action="EVIDENCE_NORMALIZED",
        object_id=evidence_id,
        description=f"Normalized {len(events)} events from offline evidence {evidence_id}"
    )
    db.add(audit)
    db.commit()
    return len(events)

