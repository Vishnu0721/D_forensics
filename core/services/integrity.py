import hashlib
import os

def calculate_sha256(file_path: str, chunk_size: int = 8192) -> str:
    """Calculates the SHA-256 hash of a file."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(chunk_size), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def verify_integrity(file_path: str, expected_hash: str):
    """Verifies if the file's current hash matches the expected hash."""
    if not os.path.exists(file_path):
        return "MISSING/UNVERIFIABLE", None
    
    try:
        current_hash = calculate_sha256(file_path)
        if current_hash == expected_hash:
            return "VALID", current_hash
        return "MODIFIED", current_hash
    except Exception:
        return "MISSING/UNVERIFIABLE", None

def verify_all_evidence(db, case_id: str):
    from core.database.models import EvidenceArtifact, AuditLog
    import datetime

    artifacts = db.query(EvidenceArtifact).filter(EvidenceArtifact.case_id == case_id).all()
    results = []

    for artifact in artifacts:
        status, current_hash = verify_integrity(artifact.original_path, artifact.sha256_hash)

        mapped_status = "VALID"
        if status == "MODIFIED":
            mapped_status = "MODIFIED"
        elif status == "MISSING/UNVERIFIABLE":
            mapped_status = "UNVERIFIABLE"

        if mapped_status != artifact.integrity_status:
            old_status = artifact.integrity_status
            artifact.integrity_status = mapped_status
            audit = AuditLog(
                actor="investigator",
                action="INTEGRITY_STATUS_CHANGED",
                object_id=artifact.id,
                description=f"Integrity status changed {old_status} -> {mapped_status} for {artifact.filename}"
            )
            db.add(audit)

        results.append({
            "evidence_id": artifact.id,
            "source": f"{artifact.source_type} ({artifact.filename})" if artifact.filename else artifact.source_type,
            "original_hash": artifact.sha256_hash,
            "current_hash": current_hash or "N/A",
            "status": mapped_status,
            "time": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        })

    db.commit()
    return results
