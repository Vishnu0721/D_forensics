import os
import time
from PySide6.QtWidgets import QApplication
from core.database import init_db, get_db, Case
from core.monitoring.manager import MonitoringManager
from core.services.integrity import verify_all_evidence

def test_phase1():
    app = QApplication([])
    init_db()
    db = next(get_db())
    
    case = db.query(Case).first()
    if not case:
        case = Case(name="Test Case", description="Testing Phase 1")
        db.add(case)
        db.commit()

    print("Starting monitor...")
    monitor = MonitoringManager(case.id)
    monitor.start_all()
    
    # Wait for 3 seconds to collect some events
    for _ in range(30):
        app.processEvents()
        time.sleep(0.1)
        
    monitor.stop_all()
    print("Monitor stopped.")
    
    # Check if files were created
    evidence_dir = os.path.join("data", "evidence", str(case.id))
    if not os.path.exists(evidence_dir):
        print(f"Directory not found: {evidence_dir}")
        return
        
    files = os.listdir(evidence_dir)
    print(f"Found {len(files)} evidence files.")
    
    if files:
        # Modify the first file to simulate tampering
        target_file = os.path.join(evidence_dir, files[0])
        print(f"Modifying {target_file} to test integrity failure...")
        with open(target_file, "a") as f:
            f.write("\ntampered data")
            
        # Verify integrity
        results = verify_all_evidence(db, case.id)
        print("Integrity verification results:")
        for res in results:
            print(f"ID: {res['evidence_id']}, Status: {res['status']}")
            if res['status'] == 'MODIFIED':
                print("SUCCESS: Found modified file!")
    else:
        print("No files were created to modify.")

if __name__ == "__main__":
    test_phase1()
