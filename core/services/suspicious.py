import ipaddress
import ntpath
import re
import networkx as nx
from typing import List, Dict, Any, Iterable, Optional
from datetime import datetime

from core.services.graph import make_process_entity, make_ip_entity, make_file_entity

# A file created and executed within this window counts as "rapid" execution.
RAPID_EXECUTION_SECONDS = 300

# User-writable locations where legitimate software rarely runs from.
UNUSUAL_EXEC_DIR_RE = re.compile(r"\\(appdata|temp|tmp|downloads|\$recycle\.bin)\\|\\users\\public\\", re.IGNORECASE)

# Documents, readers, browsers and script hosts that should not start shells/script engines.
RISKY_PARENTS = {
    "winword.exe": 0.85, "excel.exe": 0.85, "powerpnt.exe": 0.85, "outlook.exe": 0.85,
    "msaccess.exe": 0.85, "mspub.exe": 0.85, "onenote.exe": 0.85, "visio.exe": 0.85,
    "acrord32.exe": 0.85, "acrobat.exe": 0.85, "foxitpdfreader.exe": 0.85,
    "wscript.exe": 0.8, "cscript.exe": 0.8, "mshta.exe": 0.8,
    "chrome.exe": 0.7, "msedge.exe": 0.7, "firefox.exe": 0.7, "iexplore.exe": 0.7,
}
SHELL_CHILDREN = {
    "cmd.exe", "powershell.exe", "pwsh.exe", "wscript.exe", "cscript.exe", "mshta.exe",
    "rundll32.exe", "regsvr32.exe", "certutil.exe", "bitsadmin.exe",
}

# Built-in Windows tools abused to download payloads ("living off the land").
LOLBIN_NETWORK_SCORES = {
    "certutil.exe": 0.75, "bitsadmin.exe": 0.75, "mshta.exe": 0.75, "rundll32.exe": 0.75,
    "regsvr32.exe": 0.75, "wscript.exe": 0.75, "cscript.exe": 0.75,
    # PowerShell is also used legitimately (scripts, package managers).
    "powershell.exe": 0.6, "pwsh.exe": 0.6,
}

# Core Windows programs that only ever run from the Windows folder.
SYSTEM_BINARIES = {
    "svchost.exe", "lsass.exe", "csrss.exe", "smss.exe", "wininit.exe", "winlogon.exe",
    "services.exe", "explorer.exe", "spoolsv.exe", "taskhostw.exe", "dllhost.exe",
    "conhost.exe", "lsm.exe",
}
WINDOWS_DIR_RE = re.compile(r"^(\\\\\?\\|\\\?\?\\)?[a-z]:\\windows\\|^\\systemroot\\|^%systemroot%\\", re.IGNORECASE)
EXE_PATH_RE = re.compile(r'^"?([a-z]:\\[^"]*?\.exe)', re.IGNORECASE)

STARTUP_FOLDER_MARKER = "\\start menu\\programs\\startup\\"
AUTORUN_REGISTRY_MARKERS = (
    "\\currentversion\\run",  # also matches RunOnce
    "\\currentversion\\policies\\explorer\\run",
    "\\currentversion\\winlogon\\userinit",
    "\\currentversion\\winlogon\\shell",
    "\\image file execution options\\",
)

DOUBLE_EXTENSION_RE = re.compile(
    r"\.(pdf|docx?|xlsx?|pptx?|txt|rtf|jpe?g|png|gif|zip|rar|mp3|mp4)\.(exe|scr|com|bat|cmd|js|jse|vbs|vbe|hta|lnk|ps1|pif|wsf)$",
    re.IGNORECASE,
)
RISKY_SCRIPT_EXTENSIONS = (".scr", ".hta", ".js", ".jse", ".vbs", ".vbe", ".wsf", ".pif")
USER_DROP_DIR_RE = re.compile(r"\\(downloads|desktop)\\", re.IGNORECASE)

# PowerShell -EncodedCommand accepts any prefix of the flag name.
PS_ENCODED_RE = re.compile(r"\s[-/](e|ec|en|enc|enco|encod|encode|encoded|encodedc\w*)\s+[a-z0-9+/=]{16,}", re.IGNORECASE)
PS_HIDDEN_RE = re.compile(r"\s[-/]w(i|in|ind|indo|indow|indows|indowst|indowsty|indowstyl|indowstyle)?\s+h(i|id|idd|idde|idden)?\b", re.IGNORECASE)
PS_BYPASS_RE = re.compile(r"\s[-/](ep|ex|exe|exec|execu|execut|executi|executio|execution|executionp\w*)\s+bypass\b", re.IGNORECASE)
PS_INVOKE_RE = re.compile(r"\biex\b|invoke-expression", re.IGNORECASE)
PS_DOWNLOAD_RE = re.compile(r"downloadstring|downloadfile|net\.webclient|invoke-webrequest|\biwr\b|invoke-restmethod|\birm\b|start-bitstransfer", re.IGNORECASE)
PS_BASE64_RE = re.compile(r"frombase64string", re.IGNORECASE)

# Ports associated with attack tooling / command-and-control, not normal services.
SUSPICIOUS_PORTS = {
    4444: "Metasploit default listener",
    1337: "common hacker-tool port",
    31337: "common backdoor port",
    6666: "IRC (often used by botnets)",
    6667: "IRC (often used by botnets)",
    6697: "IRC over TLS (often used by botnets)",
    12345: "known backdoor port",
    54321: "known backdoor port",
    9001: "Tor relay",
    9030: "Tor directory",
}


def _now_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _event_time(event) -> str:
    ts = getattr(event, "timestamp", None)
    return ts.isoformat() + "Z" if ts else _now_iso()


def _lower(value: Any) -> str:
    return str(value).lower() if value not in (None, "", "Unavailable") else ""


def _host(event) -> str:
    return event.host or "localhost"


def _is_public_ip(ip: Any) -> bool:
    try:
        addr = ipaddress.ip_address(str(ip))
    except ValueError:
        return False
    return not (addr.is_private or addr.is_loopback or addr.is_link_local
                or addr.is_multicast or addr.is_reserved or addr.is_unspecified)


def _executable_path(event) -> str:
    """Executable path from the event (path may hold a full command line in some sources)."""
    raw = str(event.path or "").strip()
    if not raw or raw == "Unavailable":
        return ""
    match = EXE_PATH_RE.match(raw)
    return match.group(1) if match else raw.strip('"')


def _command_line(event) -> str:
    meta = event.metadata_json if isinstance(event.metadata_json, dict) else {}
    for key in ("cmdline", "command_line", "commandline", "CommandLine"):
        value = meta.get(key)
        if isinstance(value, (list, tuple)):
            value = " ".join(str(part) for part in value)
        if value and value != "Unavailable":
            return str(value)
    return ""


def _finding(activity_id, score, rule_name, reason, evidence_ids, nodes, timestamp=None, relationships=None):
    return {
        "activity_id": activity_id,
        "score": round(min(score, 1.0), 2),
        "rule_name": rule_name,
        "reason": reason,
        "timestamp": timestamp or _now_iso(),
        "evidence_ids": [e for e in dict.fromkeys(evidence_ids) if e],
        "relationships": relationships or [],
        "nodes": list(nodes),
    }


# ---------------------------------------------------------------------------
# Graph rules (work on the evidence graph alone)
# ---------------------------------------------------------------------------

def _node_attr(graph, node_id, edge_data, side, attr) -> str:
    value = graph.nodes[node_id].get(attr)
    if not value and isinstance(edge_data.get(side), dict):
        value = edge_data[side].get(attr)
    return _lower(value)


def _graph_findings(graph: nx.MultiDiGraph) -> List[Dict[str, Any]]:
    findings = []
    seen = set()

    def add(finding):
        if finding["activity_id"] not in seen:
            seen.add(finding["activity_id"])
            findings.append(finding)

    for u, v, key, data in graph.edges(keys=True, data=True):
        rel = [{"source": u, "target": v, "type": key, "confidence": data.get("confidence", 0.0)}]
        evidence = list(data.get("evidence_ids", []))

        # Rules 1 & 2: Unusual Directory Execution & Rapid Execution
        if key == 'EXECUTED_AS':
            # EvidenceGraph edges carry merged lists; graphs built directly from relationship
            # dicts carry the single-relationship fields.
            file_paths = data.get("file_paths") or ([data["file_path"]] if data.get("file_path") else [])
            reasons = data.get("reasons") or ([data["reason"]] if data.get("reason") else [])
            # Older saved graphs have no structured path; fall back to the reason text.
            location_text = " ".join(file_paths) if file_paths else " ".join(reasons)
            time_diff = data.get("min_time_diff_seconds", data.get("time_diff_seconds"))

            if UNUSUAL_EXEC_DIR_RE.search(location_text):
                add(_finding(
                    f"SUSP-DIR-{v}", 0.70, "Unusual Directory Execution",
                    "Process executed from a user-writable or temporary directory.",
                    evidence, [u, v], relationships=rel))
            elif time_diff is None or time_diff <= RAPID_EXECUTION_SECONDS:
                add(_finding(
                    f"SUSP-EXEC-{v}", 0.40, "Rapid Execution",
                    "Executable file was created and executed shortly afterward.",
                    evidence, [u, v], relationships=rel))

        if key == 'CONNECTED_TO':
            process_node_id, ip_node_id = u, v

            # Rule 3: Network Execution
            executed_edges = [edge for edge in graph.in_edges(process_node_id, keys=True, data=True) if edge[2] == 'EXECUTED_AS']
            if executed_edges:
                file_node_id = executed_edges[0][0]
                exec_data = executed_edges[0][3]
                add(_finding(
                    f"SUSP-NET-{process_node_id}-{ip_node_id}", 0.85, "Network Execution",
                    "A newly created or dropped file was executed and established an outbound network connection.",
                    evidence + list(exec_data.get("evidence_ids", [])),
                    [file_node_id, process_node_id, ip_node_id],
                    relationships=[
                        {"source": file_node_id, "target": process_node_id, "type": "EXECUTED_AS", "confidence": exec_data.get("confidence", 0.0)},
                        rel[0],
                    ]))

            # Rule: built-in Windows tool contacting the internet
            name = _node_attr(graph, process_node_id, data, "source", "process")
            ip = _node_attr(graph, ip_node_id, data, "target", "ip") or ip_node_id
            if name in LOLBIN_NETWORK_SCORES and _is_public_ip(ip):
                add(_finding(
                    f"SUSP-LOLBIN-{process_node_id}-{ip_node_id}", LOLBIN_NETWORK_SCORES[name],
                    "Built-in Tool Contacting Internet",
                    f"{name} connected to internet address {ip}. Attackers often use this built-in Windows tool to download malware.",
                    evidence, [process_node_id, ip_node_id], relationships=rel))

        # Rule: same executable under a different program name (renamed copy)
        if key == 'SAME_HASH_AS':
            name_u = _node_attr(graph, u, data, "source", "process")
            name_v = _node_attr(graph, v, data, "target", "process")
            if name_u and name_v and name_u != name_v:
                pair = "-".join(sorted((u, v)))
                add(_finding(
                    f"SUSP-RENAMED-{pair}", 0.70, "Renamed Program Copy",
                    f"{name_u} and {name_v} are the same file (identical SHA-256) running under different names, "
                    "a common way to disguise a tool.",
                    evidence, [u, v], relationships=rel))

    return findings


# ---------------------------------------------------------------------------
# Event rules (need the normalized events: parent process, command line, path, port)
# ---------------------------------------------------------------------------

def _parent_child_finding(event) -> Optional[Dict[str, Any]]:
    parent = _lower(event.parent_process)
    child = _lower(event.process)
    if parent in RISKY_PARENTS and child in SHELL_CHILDREN:
        node = make_process_entity(_host(event), event.pid, event.process)["id"]
        return _finding(
            f"SUSP-PARENT-{node}", RISKY_PARENTS[parent], "Suspicious Program Launch",
            f"{parent} started {child}. Documents, PDF readers and browsers normally never launch "
            "command shells or script engines; this is typical of a malicious attachment or download.",
            [event.evidence_id], [node], timestamp=_event_time(event))
    return None


def _masquerade_finding(event) -> Optional[Dict[str, Any]]:
    name = _lower(event.process)
    if name not in SYSTEM_BINARIES:
        return None
    exe = _executable_path(event)
    if not exe or "\\" not in exe or WINDOWS_DIR_RE.match(exe):
        return None
    node = make_process_entity(_host(event), event.pid, event.process)["id"]
    return _finding(
        f"SUSP-MASQ-{node}", 0.80, "Disguised System Program",
        f"{name} is a core Windows program but ran from {exe} instead of the Windows folder. "
        "Malware often borrows system program names to blend in.",
        [event.evidence_id], [node], timestamp=_event_time(event))


def _powershell_finding(event) -> Optional[Dict[str, Any]]:
    cmd = _command_line(event)
    if not cmd:
        return None
    padded = " " + cmd
    lower = padded.lower()
    if _lower(event.process) not in ("powershell.exe", "pwsh.exe", "powershell_ise.exe") \
            and "powershell" not in lower and "pwsh" not in lower:
        return None

    indicators = []
    score = 0.0
    if PS_ENCODED_RE.search(padded):
        indicators.append("encoded (hidden) command")
        score = max(score, 0.85)
    if PS_INVOKE_RE.search(padded) and PS_DOWNLOAD_RE.search(padded):
        indicators.append("downloads and runs code from the internet")
        score = max(score, 0.85)
    if PS_BASE64_RE.search(padded):
        indicators.append("decodes Base64 data")
        score = max(score, 0.6)
    hidden = bool(PS_HIDDEN_RE.search(padded))
    bypass = bool(PS_BYPASS_RE.search(padded))
    if hidden:
        indicators.append("hidden window")
    if bypass:
        indicators.append("execution policy bypass")
    # Hidden window or policy bypass alone is common in legitimate installers/updaters.
    if score == 0.0 and hidden and bypass:
        score = 0.6
    if score == 0.0:
        return None
    score += 0.05 * (len(indicators) - 1)

    node = make_process_entity(_host(event), event.pid, event.process)["id"]
    return _finding(
        f"SUSP-PS-{node}", min(score, 0.95), "Obfuscated PowerShell",
        "PowerShell was started with: " + ", ".join(indicators) + ". "
        "These options are commonly used to hide what a script does.",
        [event.evidence_id], [node], timestamp=_event_time(event))


def _persistence_finding(event) -> Optional[Dict[str, Any]]:
    path = _lower(event.path)
    if not path:
        return None
    if event.event_type in ("file_created", "file_moved") and STARTUP_FOLDER_MARKER in path:
        name = event.file or ntpath.basename(path)
        if name.lower() == "desktop.ini":
            return None
        node = make_file_entity(_host(event), name)["id"]
        return _finding(
            f"SUSP-PERSIST-{path}", 0.75, "Startup Persistence",
            f"{name} was added to the Startup folder, so it will run automatically every time the user logs in.",
            [event.evidence_id], [node], timestamp=_event_time(event))
    if event.event_type == "registry_modified" and any(m in path for m in AUTORUN_REGISTRY_MARKERS):
        value_name = ntpath.basename(str(event.path))
        node = make_file_entity(_host(event), value_name)["id"]
        return _finding(
            f"SUSP-PERSIST-{path}", 0.75, "Autorun Registry Change",
            f"An autorun registry location was changed ({event.path}); programs listed there start automatically.",
            [event.evidence_id], [node], timestamp=_event_time(event))
    return None


def _disguised_file_finding(event) -> Optional[Dict[str, Any]]:
    if event.event_type not in ("file_created", "file_moved", "download"):
        return None
    name = str(event.file or ntpath.basename(str(event.path or "")))
    if not name:
        return None
    lower = name.lower()
    node = make_file_entity(_host(event), name)["id"]
    if "\u202e" in name or DOUBLE_EXTENSION_RE.search(lower):
        return _finding(
            f"SUSP-FILE-{_lower(event.path) or lower}", 0.75, "Disguised Executable",
            f"{name} looks like a document or media file but is actually a program or script "
            "(double extension or reversed-text trick).",
            [event.evidence_id], [node], timestamp=_event_time(event))
    in_drop_dir = event.event_type == "download" or bool(USER_DROP_DIR_RE.search(str(event.path or "")))
    if in_drop_dir and lower.endswith(RISKY_SCRIPT_EXTENSIONS):
        return _finding(
            f"SUSP-FILE-{_lower(event.path) or lower}", 0.55, "Risky Script File",
            f"{name} is a script/screensaver file type that runs code when opened, "
            "and it appeared in Downloads or Desktop.",
            [event.evidence_id], [node], timestamp=_event_time(event))
    return None


def _port_finding(event) -> Optional[Dict[str, Any]]:
    try:
        port = int(event.port)
    except (TypeError, ValueError):
        return None
    if port not in SUSPICIOUS_PORTS or not event.ip:
        return None
    try:
        if ipaddress.ip_address(str(event.ip)).is_loopback:
            return None
    except ValueError:
        return None
    proc = make_process_entity(_host(event), event.pid, event.process)["id"]
    ip = make_ip_entity(event.ip)["id"]
    return _finding(
        f"SUSP-PORT-{proc}-{ip}-{port}", 0.60, "Suspicious Network Port",
        f"{event.process or 'A program'} connected to {event.ip} on port {port} ({SUSPICIOUS_PORTS[port]}). "
        "Normal applications rarely use this port.",
        [event.evidence_id], [proc, ip], timestamp=_event_time(event))


def detect_event_findings(events: Iterable[Any]) -> List[Dict[str, Any]]:
    """Rules that need per-event fields not kept on the graph."""
    findings = []
    for event in events:
        if event.event_type == "process_started":
            checks = (_parent_child_finding, _masquerade_finding, _powershell_finding)
        elif event.event_type == "connection":
            checks = (_port_finding,)
        elif event.event_type in ("file_created", "file_moved", "download", "registry_modified"):
            checks = (_persistence_finding, _disguised_file_finding)
        else:
            continue
        for check in checks:
            finding = check(event)
            if finding:
                findings.append(finding)
    return findings


def merge_findings(*finding_lists: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Deduplicate by activity_id (keeping the highest score) and sort by score."""
    merged: Dict[str, Dict[str, Any]] = {}
    for findings in finding_lists:
        for f in findings:
            existing = merged.get(f["activity_id"])
            if existing is None or f["score"] > existing["score"]:
                merged[f["activity_id"]] = f
    result = list(merged.values())
    result.sort(key=lambda x: x["score"], reverse=True)
    return result


def detect_suspicious_activity(graph: nx.MultiDiGraph, events: Optional[Iterable[Any]] = None) -> List[Dict[str, Any]]:
    """
    Evaluates the graph (nodes and relationships), and optionally the normalized events,
    against suspicious activity rules.
    Returns a list of suspicious activities with deterministically calculated scores.
    """
    findings = _graph_findings(graph)
    if events is not None:
        return merge_findings(findings, detect_event_findings(events))
    return merge_findings(findings)
