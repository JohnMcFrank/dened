import socket
import threading
import time
from typing import List, Dict, Optional
import logging

class InternalProxyManager:
    def __init__(self):
        self.proxies = []
        self.proxy_lock = threading.Lock()
        self.logger = logging.getLogger(__name__)
        
    def create_internal_proxies(self, count: int = 10) -> List[str]:
        """Créer des proxies internes basés sur les IPs des pods"""
        internal_proxies = []
        
        # Utiliser l'IP du pod comme proxy
        try:
            hostname = socket.gethostname()
            local_ip = socket.gethostbyname(hostname)
            
            for i in range(count):
                # Créer un proxy interne unique pour chaque pod
                proxy_port = 8000 + i
                proxy_address = f"{local_ip}:{proxy_port}"
                internal_proxies.append(proxy_address)
                
        except Exception as e:
            self.logger.error(f"Erreur création proxies internes: {e}")
            # Fallback à des IPs de base
            for i in range(count):
                internal_proxies.append(f"127.0.0.{i+1}:8000")
                
        return internal_proxies
        
    def get_pod_proxy(self, pod_name: str) -> str:
        """Obtenir le proxy spécifique pour un pod"""
        # Utiliser l'IP du pod comme proxy
        try:
            pod_ip = socket.gethostbyname(pod_name)
            return f"{pod_ip}:8080"
        except:
            return "127.0.0.1:8080"
            
    def get_random_internal_proxy(self) -> Optional[str]:
        """Obtenir un proxy interne aléatoire"""
        with self.proxy_lock:
            if not self.proxies:
                return None
            import random
            return random.choice(self.proxies)
            
    def add_proxy(self, proxy: str):
        """Ajouter un proxy à la liste"""
        with self.proxy_lock:
            if proxy not in self.proxies:
                self.proxies.append(proxy)
                
    def remove_proxy(self, proxy: str):
        """Supprimer un proxy de la liste"""
        with self.proxy_lock:
            if proxy in self.proxies:
                self.proxies.remove(proxy)
