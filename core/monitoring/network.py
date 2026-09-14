import psutil
import time
from datetime import datetime
from .base import BaseCollector

class NetworkCollector(BaseCollector):
    def __init__(self, case_id: str, poll_interval: int = 3):
        super().__init__(case_id)
        self.poll_interval = poll_interval
        self._seen_connections = set()
        
    def run(self):
        # Capture baseline to avoid spamming existing connections
        try:
            for conn in psutil.net_connections(kind='inet'):
                if conn.raddr:
                    self._seen_connections.add((conn.laddr.ip, conn.laddr.port, conn.raddr.ip, conn.raddr.port))
        except psutil.AccessDenied:
            print("NetworkCollector requires administrative privileges to map all connections.")
            pass
            
        while self._is_running:
            try:
                current_conns = set()
                raw_conns = psutil.net_connections(kind='inet')
                
                for conn in raw_conns:
                    if not conn.raddr:
                        continue
                        
                    conn_tuple = (conn.laddr.ip, conn.laddr.port, conn.raddr.ip, conn.raddr.port)
                    current_conns.add(conn_tuple)
                    
                    if conn_tuple not in self._seen_connections:
                        # New outbound or established connection!
                        process_name = "Unavailable"
                        executable_path = "Unavailable"
                        user = "Unavailable"
                        pid = conn.pid if conn.pid else "Unavailable"
                        
                        if conn.pid:
                            try:
                                p = psutil.Process(conn.pid)
                                process_name = p.name()
                                executable_path = p.exe() if hasattr(p, 'exe') and p.exe() else "Unavailable"
                                try:
                                    u = p.username()
                                    if '\\' in u: u = u.split('\\')[1]
                                    user = u
                                except:
                                    pass
                            except (psutil.NoSuchProcess, psutil.AccessDenied):
                                pass
                                
                        event = {
                            "timestamp": datetime.utcnow().isoformat() + "Z",
                            "source_type": "network",
                            "event_type": "connection",
                            "process": process_name,
                            "pid": pid,
                            "path": executable_path,
                            "user": user,
                            "ip": conn.raddr.ip,
                            "port": conn.raddr.port,
                            "protocol": "TCP" if conn.type == 1 else "UDP"
                        }
                        self.event_captured.emit(event)
                        
                self._seen_connections = current_conns
            except psutil.AccessDenied:
                # If psutil.net_connections itself fails, we could fallback to netstat, but for now we note it.
                print("NetworkCollector: AccessDenied when polling connections. PID mapping unavailable.")
                self.interruptible_sleep(self.poll_interval * 2)
            except Exception as e:
                print(f"NetworkCollector error: {e}")
                
            self.interruptible_sleep(self.poll_interval)
