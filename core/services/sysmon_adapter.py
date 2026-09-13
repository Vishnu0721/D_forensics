import ntpath
from typing import Dict, Any

def is_winlog_record(rec: Any) -> bool:
    if not isinstance(rec, dict):
        return False
    winlog = rec.get("winlog")
    if not isinstance(winlog, dict):
        return False
    return "event_data" in winlog

def _extract_sha256(hashes_str: str) -> str:
    if not hashes_str:
        return None
    for part in hashes_str.split(","):
        if part.startswith("SHA256="):
            return part[7:]
    return None

def flatten_winlog_record(rec: Dict[str, Any]) -> Dict[str, Any]:
    winlog = rec.get("winlog", {})
    event_id = winlog.get("event_id")
    event_data = winlog.get("event_data", {})
    
    timestamp = rec.get("@timestamp")
    host = winlog.get("computer_name")
    
    flat = {
        "timestamp": timestamp,
        "host": host
    }
    
    if event_id == 1:
        flat["event_type"] = "process_started"
        flat["pid"] = event_data.get("ProcessId")
        flat["process"] = event_data.get("Image")
        if flat["process"]:
            flat["process"] = ntpath.basename(flat["process"])
        flat["path"] = event_data.get("Image")
        flat["file"] = flat["process"] # Same as process for ID 1
        flat["parent_process"] = event_data.get("ParentImage")
        if flat["parent_process"]:
            flat["parent_process"] = ntpath.basename(flat["parent_process"])
        flat["parent_pid"] = event_data.get("ParentProcessId")
        flat["file_hash"] = _extract_sha256(event_data.get("Hashes"))
        flat["user"] = event_data.get("User")
        
    elif event_id == 5:
        flat["event_type"] = "process_stopped"
        flat["pid"] = event_data.get("ProcessId")
        flat["process"] = event_data.get("Image")
        if flat["process"]:
            flat["process"] = ntpath.basename(flat["process"])
            
    elif event_id == 3:
        flat["event_type"] = "connection"
        flat["pid"] = event_data.get("ProcessId")
        flat["process"] = event_data.get("Image")
        if flat["process"]:
            flat["process"] = ntpath.basename(flat["process"])
        flat["ip"] = event_data.get("DestinationIp")
        flat["port"] = event_data.get("DestinationPort")
        
    elif event_id == 11:
        flat["event_type"] = "file_created"
        flat["path"] = event_data.get("TargetFilename")
        if flat["path"]:
            flat["file"] = ntpath.basename(flat["path"])
        else:
            flat["file"] = None
        flat["user"] = event_data.get("User")
        
    elif event_id == 13:
        flat["event_type"] = "registry_modified"
        flat["path"] = event_data.get("TargetObject")
        
    else:
        # Fallback for unknown sysmon IDs, we just dump it as unknown
        flat["event_type"] = "unknown_sysmon"
        flat["event_id"] = event_id
        
    # Expose a normalized user if user is present
    if "user" in flat and flat["user"]:
        flat["normalized_user"] = flat["user"].split("\\")[-1]

    # Clean out None values so we don't insert literal Nones into keys that didn't exist
    return {k: v for k, v in flat.items() if v is not None}
