import os
import time
import shutil
from PySide6.QtCore import QCoreApplication
from core.monitoring.filesystem import FilesystemCollector

def print_event(data):
    # This will just prove the events are emitted. Diagnostic logs inside the collector will also print.
    pass

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
    time.sleep(2) # Give watchdog time to initialize
    
    test_file_path = os.path.join(test_dir_1, "test.txt")
    renamed_file_path = os.path.join(test_dir_1, "renamed_test.txt")
    moved_file_path = os.path.join(test_dir_2, "renamed_test.txt")
    
    # Create
    print("\n--- Creating ---")
    with open(test_file_path, "w") as f:
        f.write("Hello")
    time.sleep(1)
    
    # Modify
    print("\n--- Modifying ---")
    with open(test_file_path, "a") as f:
        f.write(" World")
    time.sleep(1)
    
    # Rename
    print("\n--- Renaming ---")
    os.rename(test_file_path, renamed_file_path)
    time.sleep(1)
    
    # Move
    print("\n--- Moving ---")
    shutil.move(renamed_file_path, moved_file_path)
    time.sleep(1)
    
    # Delete
    print("\n--- Deleting ---")
    os.remove(moved_file_path)
    time.sleep(2)
    
    print("\nStopping monitoring...")
    collector.stop_monitoring()
    print("Done.")
