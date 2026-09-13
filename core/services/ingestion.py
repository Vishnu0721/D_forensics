import os
import shutil
import uuid
import mimetypes
from datetime import datetime
from typing import Tuple
from sqlalchemy.orm import Session
from core.database.models import EvidenceArtifact, AuditLog
from core.services.integrity import calculate_sha256


def preserve_evidence_file(source_path: str, case_id: str, evidence_id: str = None) -> Tuple[str, str, int, str]:
    """
    Copies the source evidence file to a unique, immutable preserved location.
    Returns: (preserved_path, sha256_hash, file_size, mime_type)
    The SHA-256 is calculated from the exact preserved bytes.
    """
    if not os.path.exists(source_path):
        raise FileNotFoundError(f"Evidence file not found: {source_path}")

    if evidence_id is None:
        evidence_id = str(uuid.uuid4())

    original_filename = os.path.basename(source_path)
    file_size = os.path.getsize(source_path)
    mime_type, _ = mimetypes.guess_type(source_path)

    preserve_dir = os.path.join("data", "evidence", case_id, "preserved")
    os.makedirs(preserve_dir, exist_ok=True)

    name, ext = os.path.splitext(original_filename)
    preserved_filename = f"{evidence_id}{ext}" if ext else evidence_id
    preserved_path = os.path.abspath(os.path.join(preserve_dir, preserved_filename))

    counter = 1
    while os.path.exists(preserved_path):
        preserved_filename = f"{evidence_id}_{counter}{ext}" if ext else f"{evidence_id}_{counter}"
        preserved_path = os.path.abspath(os.path.join(preserve_dir, preserved_filename))
        counter += 1

    shutil.copy2(source_path, preserved_path)

    file_hash = calculate_sha256(preserved_path)

    return preserved_path, file_hash, file_size, (mime_type or "application/octet-stream")


def ingest_preserved_evidence(
    db: Session,
    case_id: str,
    source_file_path: str,
    source_type: str,
    actor: str,
    upload_timestamp: datetime = None
) -> EvidenceArtifact:
    """
    Ingests a raw evidence file:
      1. copies it to a preserved location
      2. calculates SHA-256 from the preserved bytes
      3. creates an EvidenceArtifact record
      4. creates an AuditLog entry
    """
    if upload_timestamp is None:
        upload_timestamp = datetime.utcnow()

    evidence_id = str(uuid.uuid4())
    original_filename = os.path.basename(source_file_path)

    preserved_path, file_hash, file_size, mime_type = preserve_evidence_file(
        source_file_path, case_id, evidence_id
    )

    evidence = EvidenceArtifact(
        id=evidence_id,
        case_id=case_id,
        filename=original_filename,
        source_type=source_type,
        original_path=preserved_path,
        collection_timestamp=upload_timestamp,
        file_size=file_size,
        sha256_hash=file_hash,
        mime_type=mime_type,
        created_by=actor,
        integrity_status="VALID"
    )

    audit = AuditLog(
        actor=actor,
        action="EVIDENCE_INGESTED",
        object_id=evidence.id,
        description=f"Ingested offline evidence {original_filename} (Hash: {file_hash[:16]}..., Size: {file_size}B)"
    )

    db.add(evidence)
    db.add(audit)
    db.commit()
    db.refresh(evidence)

    return evidence


def ingest_evidence(db: Session, case_id: str, file_path: str, source_type: str, actor: str) -> EvidenceArtifact:
    """
    Legacy wrapper - preserves file then creates EvidenceArtifact.
    """
    return ingest_preserved_evidence(db, case_id, file_path, source_type, actor)
