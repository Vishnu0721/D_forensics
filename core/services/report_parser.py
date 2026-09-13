import os
import json
import csv
import re
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime
from core.services import sysmon_adapter


SUPPORTED_FORMATS = {
    ".json": "JSON",
    ".csv": "CSV",
    ".txt": "TXT",
    ".log": "TXT",
    ".evtx": "EVTX",
}

AUTO_SOURCE_HINTS = {
    "process": ["process", "pid", "parent_process", "command_line", "executable"],
    "filesystem": ["file", "path", "old_path", "new_path", "file_created", "file_deleted", "file_modified", "file_accessed"],
    "network": ["ip", "port", "destination_ip", "source_ip", "destination_port", "source_port", "connection", "protocol", "domain"],
    "browser": ["url", "download", "browser", "tab", "visited", "downloaded_file"],
    "windows_log": ["event_id", "event_record_id", "logon", "logoff", "security_id", "task_category", "keywords"],
    "usb": ["device_id", "usb", "serial_number", "vendor_id", "product_id", "drive_letter", "usb_connected"],
}

SOURCE_TYPE_ORDER = ["process", "network", "browser", "usb", "windows_log", "filesystem"]


def detect_format(file_path: str) -> str:
    ext = os.path.splitext(file_path)[1].lower()
    if ext in SUPPORTED_FORMATS:
        return SUPPORTED_FORMATS[ext]
    return "UNKNOWN"


def detect_source_type(records: List[Dict[str, Any]], sample_size: int = 50) -> str:
    if not records:
        return "filesystem"

    sample = records[:sample_size]
    first_keys = set()
    event_types = set()
    for rec in sample:
        if isinstance(rec, dict):
            first_keys.update(k.lower() for k in rec.keys())
            if "event_type" in rec:
                event_types.add(str(rec["event_type"]).lower())

    scores: Dict[str, int] = {st: 0 for st in SOURCE_TYPE_ORDER}

    for source_type, hints in AUTO_SOURCE_HINTS.items():
        for hint in hints:
            if any(hint in k for k in first_keys):
                scores[source_type] += 2
        for et in event_types:
            for hint in hints:
                if hint in et:
                    scores[source_type] += 1

    best = max(SOURCE_TYPE_ORDER, key=lambda s: scores[s])
    if scores[best] > 0:
        return best
    return "filesystem"


def _coerce_record_types(rec: Dict[str, Any]) -> Dict[str, Any]:
    int_fields = ["pid", "port", "destination_port", "source_port", "event_id"]
    for f in int_fields:
        if f in rec and rec[f] is not None and rec[f] != "":
            try:
                rec[f] = int(rec[f])
            except (ValueError, TypeError):
                pass
    return rec


def parse_json(file_path: str) -> Tuple[List[Dict[str, Any]], int]:
    records: List[Dict[str, Any]] = []
    failed = 0
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                f.seek(0)
                data = []
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data.append(json.loads(line))
                    except json.JSONDecodeError:
                        failed += 1

        if isinstance(data, dict):
            if "events" in data and isinstance(data["events"], list):
                data = data["events"]
            elif "records" in data and isinstance(data["records"], list):
                data = data["records"]
            else:
                data = [data]

        if isinstance(data, list):
            for rec in data:
                if isinstance(rec, dict):
                    if sysmon_adapter.is_winlog_record(rec):
                        rec = sysmon_adapter.flatten_winlog_record(rec)
                        
                    # Normalize keys
                    cleaned = {}
                    for k, v in rec.items():
                        if k is not None:
                            new_k = str(k).strip().lower().replace(" ", "_").replace("-", "_")
                            cleaned[new_k] = v
                    records.append(_coerce_record_types(cleaned))
                else:
                    failed += 1
        else:
            failed += 1
    except Exception:
        failed += max(1, 1 - len(records))
    return records, failed


def parse_csv(file_path: str) -> Tuple[List[Dict[str, Any]], int]:
    records: List[Dict[str, Any]] = []
    failed = 0
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace", newline="") as f:
            reader = csv.DictReader(f)
            for rec in reader:
                if not rec:
                    continue
                try:
                    # Normalize keys
                    cleaned = {}
                    for k, v in rec.items():
                        if k is not None:
                            new_k = str(k).strip().lower().replace(" ", "_").replace("-", "_")
                            cleaned[new_k] = v
                    records.append(_coerce_record_types(cleaned))
                except Exception:
                    failed += 1
    except Exception:
        failed += max(1, 1 - len(records))
    return records, failed


TS_PATTERNS = [
    (re.compile(r"^(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)\s*(.*)$"), 1, 2),
    (re.compile(r"^\[?(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}[^\]]*)\]?\s*(.*)$"), 1, 2),
    (re.compile(r"^(\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}:\d{2}(?:\s*[AP]M)?)\s*(.*)$"), 1, 2),
    (re.compile(r"^(\d{2}:\d{2}:\d{2})\s+(.*)$"), 1, 2),
]

KV_PATTERN = re.compile(r"(\w+)=([^,\s]+(?:\"[^\"]*\"|'[^']*')?)")
CSV_INLINE_PATTERN = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_,\s=]*$")


def _parse_text_line(line: str, line_no: int) -> Optional[Dict[str, Any]]:
    line = line.strip()
    if not line:
        return None

    timestamp = None
    remainder = line
    for pat, ts_idx, rest_idx in TS_PATTERNS:
        m = pat.match(line)
        if m:
            timestamp = m.group(ts_idx)
            remainder = m.group(rest_idx).strip()
            break

    record: Dict[str, Any] = {"metadata_json_original_line": line, "metadata_json_line_no": line_no}
    if timestamp:
        record["timestamp"] = timestamp

    kv_pairs = dict(KV_PATTERN.findall(remainder))
    if len(kv_pairs) >= 2:
        for k, v in kv_pairs.items():
            v = v.strip('"').strip("'")
            record[k.lower()] = v
        return _coerce_record_types(record)

    lower = remainder.lower()
    if any(token in lower for token in ["pid=", "process=", "file=", "ip=", "port=", "user=", "event_type=", "host=", "path="]):
        return _coerce_record_types(record)

    return None


def parse_txt(file_path: str) -> Tuple[List[Dict[str, Any]], int]:
    records: List[Dict[str, Any]] = []
    failed = 0
    total = 0
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            for line_no, line in enumerate(f, start=1):
                if not line.strip():
                    continue
                total += 1
                rec = _parse_text_line(line, line_no)
                if rec is not None:
                    records.append(rec)
                else:
                    failed += 1
    except Exception:
        failed += max(1, total - len(records))
    return records, failed


def parse_evtx(file_path: str) -> Tuple[List[Dict[str, Any]], int]:
    try:
        import Evtx  # type: ignore
    except ImportError:
        return [], -1

    records: List[Dict[str, Any]] = []
    failed = 0
    try:
        from Evtx.Evtx import Evtx as EvtxReader
        with EvtxReader(file_path) as log:
            for record in log.records():
                try:
                    xml_str = record.xml()
                    rec = {"raw_xml": xml_str, "timestamp": record.timestamp().isoformat()}
                    records.append(_coerce_record_types(rec))
                except Exception:
                    failed += 1
    except Exception:
        failed += max(1, 1 - len(records))
    return records, failed


PARSERS = {
    "JSON": parse_json,
    "CSV": parse_csv,
    "TXT": parse_txt,
    "EVTX": parse_evtx,
}


class ParseResult:
    def __init__(self):
        self.success = False
        self.format_detected: str = "UNKNOWN"
        self.source_type_detected: str = "filesystem"
        self.records: List[Dict[str, Any]] = []
        self.records_parsed = 0
        self.records_failed = 0
        self.error_message: Optional[str] = None

    def summary(self) -> str:
        if not self.success:
            return f"Parse failed: {self.error_message or 'Unknown error'}"
        if self.records_failed < 0:
            return f"EVTX parser not available (install python-evtx)."
        if self.records_parsed == 0 and self.records_failed == 0:
            return "No records found in evidence file."
        if self.records_failed > 0:
            return f"{self.records_parsed} events parsed, {self.records_failed} records could not be parsed."
        return f"{self.records_parsed} events parsed."


def parse_report(file_path: str) -> ParseResult:
    result = ParseResult()

    if not os.path.exists(file_path):
        result.error_message = f"Evidence file not found: {file_path}"
        return result

    fmt = detect_format(file_path)
    result.format_detected = fmt

    if fmt not in PARSERS:
        result.error_message = "Unsupported or unparseable evidence format"
        return result

    parser = PARSERS[fmt]
    try:
        records, failed = parser(file_path)
    except Exception as e:
        result.error_message = f"{fmt} parser error: {e}"
        return result

    if failed < 0:
        result.error_message = "Unsupported or unparseable evidence format (EVTX library not installed)"
        result.records_failed = 0
        return result

    result.records = records
    result.records_parsed = len(records)
    result.records_failed = max(0, failed)
    result.source_type_detected = detect_source_type(records)
    result.success = True
    return result
