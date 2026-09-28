import os
import time
import shutil
from PySide6.QtCore import QCoreApplication
from core.monitoring.filesystem import FilesystemCollector

captured = []

def print_event(data):
    captured.append(data['event_type'])
    print(f"[EVENT] {data['event_type']}: {data['path']}")

def wait(app, seconds):
    # Events are delivered through the Qt event loop, so keep it running while waiting.
    end = time.time() + seconds
    while time.time() < end:
        app.processEvents()
        time.sleep(0.05)

if __name__ == "__main__":
    app = QCoreApplication([])
    
    # We will monitor a local test directory instead of OneDrive paths
    test_dir_1 = os.path.abspath(os.path.join("scratch", "dir1"))
    test_dir_2 = os.path.abspath(os.path.join("scratch", "dir2"))
    os.makedirs(test_dir_1, exist_ok=True)
    os.makedirs(test_dir_2, exist_ok=True)
    
    collector = FilesystemCollector("test_case", monitored_dirs=[test_dir_1, test_dir_2])
    collector.event_captured.connect(print_event)
    collector.start_monitoring()
    
    print("Started monitoring...")
    wait(app, 2) # Give watchdog time to initialize
    
    test_file_path = os.path.join(test_dir_1, "test.txt")
    renamed_file_path = os.path.join(test_dir_1, "renamed_test.txt")
    moved_file_path = os.path.join(test_dir_2, "renamed_test.txt")
    
    # Create
    print("\n--- Creating ---")
    with open(test_file_path, "w") as f:
        f.write("Hello")
    wait(app, 1)
    
    # Modify
    print("\n--- Modifying ---")
    with open(test_file_path, "a") as f:
        f.write(" World")
    wait(app, 1)
    
    # Rename
    print("\n--- Renaming ---")
    os.rename(test_file_path, renamed_file_path)
    wait(app, 1)
    
    # Move
    print("\n--- Moving ---")
    shutil.move(renamed_file_path, moved_file_path)
    wait(app, 1)
    
    # Delete
    print("\n--- Deleting ---")
    os.remove(moved_file_path)
    wait(app, 2)
    
    print("\nStopping monitoring...")
    collector.stop_monitoring()
    collector.wait(3000)

    missing = {"file_created", "file_deleted"} - set(captured)
    if missing:
        print(f"FAILED: expected events not captured: {sorted(missing)}")
        raise SystemExit(1)
    print(f"Captured {len(captured)} events. Done.")
