import uuid
import datetime
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Float, JSON
from sqlalchemy.orm import relationship
from .engine import Base

def generate_uuid():
    return str(uuid.uuid4())

class Case(Base):
    __tablename__ = "cases"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    evidence = relationship("EvidenceArtifact", back_populates="case")
    events = relationship("ForensicEvent", back_populates="case")

class EvidenceArtifact(Base):
    __tablename__ = "evidence_artifacts"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    case_id = Column(String, ForeignKey("cases.id"), nullable=False)
    filename = Column(String, nullable=False)
    source_type = Column(String, nullable=False)  # e.g., "windows_log", "browser", "network"
    original_path = Column(String, nullable=False)
    collection_timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    file_size = Column(Integer, nullable=False)
    sha256_hash = Column(String, nullable=False)
    mime_type = Column(String, nullable=True)
    created_by = Column(String, nullable=False)
    integrity_status = Column(String, default="VALID")  # "VALID" or "MODIFIED"
    
    case = relationship("Case", back_populates="evidence")
    events = relationship("ForensicEvent", back_populates="evidence")

class ForensicEvent(Base):
    __tablename__ = "forensic_events"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    case_id = Column(String, ForeignKey("cases.id"), nullable=False)
    evidence_id = Column(String, ForeignKey("evidence_artifacts.id"), nullable=False)
    
    timestamp = Column(DateTime, nullable=False)
    source_type = Column(String, nullable=False)
    event_type = Column(String, nullable=False)
    
    # Common extracted entities
    user = Column(String, nullable=True)
    host = Column(String, nullable=True)
    process = Column(String, nullable=True)
    pid = Column(Integer, nullable=True)
    parent_process = Column(String, nullable=True)
    file = Column(String, nullable=True)
    file_hash = Column(String, nullable=True)
    path = Column(String, nullable=True)
    ip = Column(String, nullable=True)
    domain = Column(String, nullable=True)
    port = Column(Integer, nullable=True)
    device_id = Column(String, nullable=True)
    
    metadata_json = Column(JSON, nullable=True)  # Store original unparsed fields
    
    case = relationship("Case", back_populates="events")
    evidence = relationship("EvidenceArtifact", back_populates="events")

class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    actor = Column(String, nullable=False)
    action = Column(String, nullable=False)
    object_id = Column(String, nullable=False)
    description = Column(String, nullable=True)
