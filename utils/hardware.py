import psutil
import time
from typing import Dict, Tuple

class HardwareMonitor:
    def __init__(self):
        self.cpu_count = psutil.cpu_count()
        
    def get_bandwidth_info(self) -> Dict:
        """Obtenir les informations sur la bande passante"""
        try:
            # Récupérer les statistiques réseau
            net_io = psutil.net_io_counters()
            
            # Calculer la bande passante actuelle (en Mbps)
            current_bandwidth = (net_io.bytes_sent + net_io.bytes_recv) / (1024 * 1024) * 8
            
            return {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "bandwidth_mbps": current_bandwidth,
                "interfaces": list(psutil.net_if_addrs().keys())
            }
        except Exception as e:
            return {"error": str(e), "bandwidth_mbps": 0}
    
    def get_memory_info(self) -> Dict:
        """Obtenir les informations sur la mémoire"""
        try:
            memory = psutil.virtual_memory()
            
            return {
                "total_memory_mb": memory.total / (1024 * 1024),
                "available_memory_mb": memory.available / (1024 * 1024),
                "used_memory_mb": memory.used / (1024 * 1024),
                "memory_percent": memory.percent,
                "swap_total_mb": memory.swap_total / (1024 * 1024),
                "swap_used_mb": memory.swap_used / (1024 * 1024),
                "swap_percent": memory.swap_percent
            }
        except Exception as e:
            return {"error": str(e)}
    
    def get_cpu_info(self) -> Dict:
        """Obtenir les informations sur le CPU"""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()
            
            return {
                "cpu_percent": cpu_percent,
                "cpu_count": cpu_count,
                "cpu_freq": psutil.cpu_freq()._asdict() if psutil.cpu_freq() else None
            }
        except Exception as e:
            return {"error": str(e)}
    
    def get_system_stats(self) -> Dict:
        """Obtenir toutes les statistiques système"""
        return {
            "memory": self.get_memory_info(),
            "cpu": self.get_cpu_info(),
            "bandwidth": self.get_bandwidth_info(),
            "timestamp": time.time()
        }
    
    def check_limits(self, config: Dict) -> Tuple[bool, Dict]:
        """Vérifier si les limites sont respectées"""
        memory_info = self.get_memory_info()
        memory_percent = memory_info.get('memory_percent', 0)
        
        # Vérifier la mémoire
        memory_ok = memory_percent <= config.get('max_memory_percent', 50)
        
        return memory_ok, {
            "memory_percent": memory_percent,
            "memory_ok": memory_ok
        }
