import requests
import random
import time
import threading
from typing import List, Dict, Optional
import logging

class ProxyManager:
    def __init__(self, proxy_list: List[str] = None):
        self.proxies = proxy_list or []
        self.current_index = 0
        self.failed_proxies = set()
        self.proxy_lock = threading.Lock()
        self.session = requests.Session()
        self.logger = logging.getLogger(__name__)
        
    def add_proxy(self, proxy: str):
        """Ajouter un proxy"""
        if proxy not in self.proxies:
            self.proxies.append(proxy)
            
    def remove_proxy(self, proxy: str):
        """Supprimer un proxy"""
        if proxy in self.proxies:
            self.proxies.remove(proxy)
            
    def get_random_proxy(self) -> Optional[str]:
        """Obtenir un proxy aléatoire"""
        with self.proxy_lock:
            if not self.proxies:
                return None
                
            # Filtrer les proxies échoués
            available_proxies = [p for p in self.proxies if p not in self.failed_proxies]
            
            if not available_proxies:
                return None
                
            return random.choice(available_proxies)
            
    def get_next_proxy(self) -> Optional[str]:
        """Obtenir le proxy suivant dans la liste"""
        with self.proxy_lock:
            if not self.proxies:
                return None
                
            proxy = self.proxies[self.current_index]
            self.current_index = (self.current_index + 1) % len(self.proxies)
            return proxy
            
    def test_proxy(self, proxy: str, timeout: int = 10) -> bool:
        """
        Tester si un proxy fonctionne
        
        Args:
            proxy: Proxy à tester
            timeout: Temps d'attente maximum
            
        Returns:
            True si le proxy fonctionne, False sinon
        """
        try:
            test_url = "http://httpbin.org/ip"
            proxy_dict = {
                "http": f"http://{proxy}",
                "https": f"http://{proxy}"
            }
            
            response = self.session.get(
                test_url, 
                proxies=proxy_dict, 
                timeout=timeout
            )
            
            return response.status_code == 200
            
        except Exception as e:
            self.logger.warning(f"Proxy test failed: {proxy} - {str(e)}")
            return False
            
    def mark_proxy_as_failed(self, proxy: str):
        """Marquer un proxy comme échoué"""
        with self.proxy_lock:
            self.failed_proxies.add(proxy)
            
    def mark_proxy_as_working(self, proxy: str):
        """Marquer un proxy comme fonctionnel"""
        with self.proxy_lock:
            if proxy in self.failed_proxies:
                self.failed_proxies.remove(proxy)
                
    def get_working_proxies_count(self) -> int:
        """Obtenir le nombre de proxies fonctionnels"""
        with self.proxy_lock:
            return len([p for p in self.proxies if p not in self.failed_proxies])
            
    def get_all_proxies_status(self) -> Dict:
        """Obtenir le statut de tous les proxies"""
        status = {}
        for proxy in self.proxies:
            status[proxy] = proxy not in self.failed_proxies
        return status
