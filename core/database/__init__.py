from .engine import engine, Base, SessionLocal, get_db
from .models import Case, EvidenceArtifact, ForensicEvent, AuditLog

def init_db():
    Base.metadata.create_all(bind=engine)
