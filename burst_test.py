import os
import time
import socket
from concurrent.futures import ThreadPoolExecutor

def generate_filesystem_events(count=500):
    print(f"Generating {count} filesystem events...")
    test_dir = os.path.join(os.getcwd(), "scratch", "burst_test_dir")
    os.makedirs(test_dir, exist_ok=True)
    for i in range(count):
        file_path = os.path.join(test_dir, f"test_file_{i}.txt")
        with open(file_path, "w") as f:
            f.write(f"This is test file {i}")
    time.sleep(1)
    for i in range(count):
        file_path = os.path.join(test_dir, f"test_file_{i}.txt")
        if os.path.exists(file_path):
            os.remove(file_path)
            
def generate_network_events(count=200):
    print(f"Generating {count} network events...")
    for i in range(count):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.01)
            # Connecting to a non-routable or safe test IP
            s.connect(("192.0.2.1", 80))
        except:
            pass
        finally:
            s.close()
            
if __name__ == "__main__":
    print("Starting burst test. Please ensure the forensic application is monitoring.")
    time.sleep(2)
    with ThreadPoolExecutor(max_workers=2) as executor:
        executor.submit(generate_filesystem_events, 500)
        executor.submit(generate_network_events, 200)
    print("Burst test complete.")
