from .engine import engine, Base, SessionLocal, get_db
from .models import Case, EvidenceArtifact, ForensicEvent, AuditLog

def init_db():
    Base.metadata.create_all(bind=engine)
    # create_all skips indexes on tables that already exist (older databases).
    for table in Base.metadata.sorted_tables:
        for index in table.indexes:
            index.create(bind=engine, checkfirst=True)
