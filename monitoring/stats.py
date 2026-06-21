import time
import threading
import json
from typing import Dict, List
from collections import defaultdict

class StatsManager:
    def __init__(self):
        self.stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'banned_ips': 0,
            'active_ips': 0,
            'requests_per_second': 0,
            'timestamp': time.time()
        }
        self.request_history = []
        self.ip_usage = defaultdict(int)
        self.lock = threading.Lock()
        self.start_time = time.time()
        
    def increment_request(self, success: bool = True, ip_used: str = None):
        """Incrémenter les statistiques de requêtes"""
        with self.lock:
            self.stats['total_requests'] += 1
            if success:
                self.stats['successful_requests'] += 1
            else:
                self.stats['failed_requests'] += 1
                
            if ip_used:
                self.ip_usage[ip_used] += 1
                
            self._update_rps()
            
    def mark_ip_banned(self):
        """Marquer un IP comme banni"""
        with self.lock:
            self.stats['banned_ips'] += 1
            
    def set_active_ips(self, count: int):
        """Définir le nombre d'IPs actives"""
        with self.lock:
            self.stats['active_ips'] = count
            
    def _update_rps(self):
        """Mettre à jour les requêtes par seconde"""
        elapsed = time.time() - self.start_time
        if elapsed > 0:
            self.stats['requests_per_second'] = self.stats['total_requests'] / elapsed
            
    def get_stats(self) -> Dict:
        """Obtenir les statistiques actuelles"""
        with self.lock:
            return self.stats.copy()
            
    def get_ip_usage(self) -> Dict:
        """Obtenir l'utilisation des IPs"""
        with self.lock:
            return dict(self.ip_usage)
            
    def get_detailed_stats(self) -> Dict:
        """Obtenir les statistiques détaillées"""
        with self.lock:
            return {
                'stats': self.stats.copy(),
                'ip_usage': dict(self.ip_usage),
                'uptime': time.time() - self.start_time,
                'timestamp': time.time()
            }
