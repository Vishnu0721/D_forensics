from typing import List, Dict, Any
from sqlalchemy.orm import Session
from core.database.models import ForensicEvent

def generate_timeline(db: Session, case_id: str) -> List[Dict[str, Any]]:
    """
    Generates a chronological timeline of events for a given case.
    """
    events = db.query(ForensicEvent).filter(ForensicEvent.case_id == case_id).order_by(ForensicEvent.timestamp).all()
    
    timeline = []
    for event in events:
        desc = ""
        # Human-readable descriptions based on event type
        if event.event_type == 'login': 
            desc = f"User {event.user} logged in"
        elif event.event_type == 'download': 
            desc = f"User {event.user} downloaded {event.file} from {event.domain}"
        elif event.event_type == 'file_created': 
            desc = f"File {event.file} created at {event.path}"
        elif event.event_type == 'process_started': 
            desc = f"Process {event.process} executed (PID: {event.pid})"
        elif event.event_type == 'connection': 
            desc = f"Process {event.process} connected to {event.ip}:{event.port}"
        elif event.event_type == 'usb_connected': 
            desc = f"USB device {event.device_id} connected"
        else: 
            desc = f"Event: {event.event_type}"
        
        timeline.append({
            "timestamp": event.timestamp.isoformat(),
            "source": event.source_type,
            "event_type": event.event_type,
            "description": desc,
            "evidence_id": event.evidence_id,
            "original_id": event.id
        })
        
    return timeline
