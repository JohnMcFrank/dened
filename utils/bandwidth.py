import psutil
import time
import threading
from typing import Dict, List

class BandwidthManager:
    def __init__(self):
        self.bandwidth_history = []
        self.max_bandwidth = 1000  # Mbps par défaut
        self.buffer = 0.85
        
    def calculate_bandwidth_limit(self, config: Dict) -> float:
        """Calculer la limite de bande passante"""
        max_bandwidth = config.get('max_bandwidth_mb', 1000)
        buffer = config.get('bandwidth_buffer', 0.85)
        
        return max_bandwidth * buffer
    
    def get_current_bandwidth_usage(self) -> float:
        """Obtenir l'utilisation actuelle de la bande passante"""
        try:
            net_io = psutil.net_io_counters()
            # Calculer l'utilisation en Mbps
            return (net_io.bytes_sent + net_io.bytes_recv) / (1024 * 1024) * 8
        except:
            return 0.0
    
    def monitor_bandwidth(self, interval: int = 1):
        """Surveiller la bande passante en continu"""
        while True:
            try:
                current_usage = self.get_current_bandwidth_usage()
                self.bandwidth_history.append(current_usage)
                
                if len(self.bandwidth_history) > 100:  # Garder seulement 100 valeurs
                    self.bandwidth_history.pop(0)
                
                time.sleep(interval)
            except Exception as e:
                time.sleep(interval)
