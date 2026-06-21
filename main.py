import yaml
import time
import threading
import logging
import os
from typing import Dict, List
from utils.hardware import HardwareMonitor
from utils.bandwidth import BandwidthManager
from utils.proxy_manager import ProxyManager
from monitoring.stats import StatsManager
from monitoring.monitoring import MonitoringService
import requests

class IPRotatorTool:
    def __init__(self, config_file: str = "config.yaml"):
        self.load_config(config_file)
        self.hardware_monitor = HardwareMonitor()
        self.bandwidth_manager = BandwidthManager()
        self.proxy_manager = ProxyManager()
        self.stats_manager = StatsManager()
        self.monitoring = MonitoringService(self.stats_manager)
        self.logger = logging.getLogger(__name__)
        self.running = False
        
        # Initialisation des paramètres
        self.setup_logging()
        self.init_system_resources()
        self.setup_proxy_list()
        
    def load_config(self, config_file: str):
        """Charger la configuration"""
        with open(config_file, 'r') as f:
            self.config = yaml.safe_load(f)
            
    def setup_logging(self):
        """Configurer le logging"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
    def init_system_resources(self):
        """Initialiser les ressources système"""
        self.logger.info("Initialisation des ressources système...")
        
        # Calculer les limites
        self.bandwidth_limit = self.bandwidth_manager.calculate_bandwidth_limit(
            self.config.get('bandwidth', {})
        )
        
        self.logger.info(f"Limite de bande passante: {self.bandwidth_limit} Mbps")
        
        # Vérifier les limites de mémoire
        memory_info = self.hardware_monitor.get_memory_info()
        self.logger.info(f"Utilisation mémoire: {memory_info.get('memory_percent', 0)}%")
        
    def setup_proxy_list(self):
        """Configurer la liste des proxies"""
        proxy_list = self.config.get('proxy_list', [])
        if proxy_list:
            for proxy in proxy_list:
                self.proxy_manager.add_proxy(proxy)
            self.logger.info(f"Initialisation de {len(proxy_list)} proxies")
        else:
            self.logger.warning("Aucun proxy configuré")
            
    def calculate_pod_count(self) -> int:
        """Calculer le nombre de pods nécessaires"""
        # Calculer la bande passante par pod
        pod_bandwidth = 10  # Mbps par pod (exemple)
        
        # Calculer le nombre de pods
        max_pods = int(self.bandwidth_limit / pod_bandwidth)
        
        # Respecter les limites
        min_pods = self.config.get('pods', {}).get('min_pods', 5)
        max_pods_limit = self.config.get('pods', {}).get('max_pods', 100)
        
        pod_count = max(min_pods, min(max_pods, max_pods_limit))
        
        self.logger.info(f"Nombre de pods calculé: {pod_count}")
        return pod_count
        
    def start_monitoring(self):
        """Démarrer le monitoring"""
        self.monitoring.start_monitoring_thread()

        monitor_server = threading.Thread(
            target=self.monitoring.start_monitoring_server,
            kwargs={"port": 9090},
            daemon=True
        )
        monitor_server.start()

    def simulate_request(self, pod_id: str, target_url: str, proxy: str) -> Dict:
        """Simuler une requête HTTP"""
        try:
            start_time = time.time()
            
            # Configurer le proxy
            proxy_dict = {
                "http": f"http://{proxy}",
                "https": f"http://{proxy}"
            }
            
            # Effectuer la requête
            response = requests.get(
                target_url,
                proxies=proxy_dict,
                timeout=self.config.get('target', {}).get('timeout', 10)
            )
            
            end_time = time.time()
            
            # Enregistrer les statistiques
            self.stats_manager.increment_request(success=True, ip_used=proxy)
            
            return {
                "status": "success",
                "pod_id": pod_id,
                "proxy": proxy,
                "response_time": end_time - start_time,
                "status_code": response.status_code,
                "url": target_url
            }
            
        except Exception as e:
            self.stats_manager.increment_request(success=False, ip_used=proxy)
            return {
                "status": "failed",
                "pod_id": pod_id,
                "proxy": proxy,
                "error": str(e),
                "url": target_url
            }
            
    def check_ip_ban(self, response: Dict) -> bool:
        """Vérifier si l'IP est bannie"""
        # Logique de détection de ban
        # Par exemple: réponse timeout, code 429, ou délai très long
        
        if response.get('status') == 'failed':
            return True
            
        # Vérification basée sur le temps de réponse
        response_time = response.get('response_time', 0)
        if response_time > 30:  # Si le délai est très long
            return True
            
        return False
        
    def run_pods(self, pod_count: int = 10):
        """Exécuter les pods"""
        self.logger.info(f"Démarrage de {pod_count} pods")
        self.running = True
        
        def pod_worker(pod_id: int):
            """Worker pour un pod"""
            while self.running:
                try:
                    # Obtenir un proxy
                    proxy = self.proxy_manager.get_random_proxy()
                    
                    if not proxy:
                        self.logger.warning(f"Pod {pod_id}: Aucun proxy disponible")
                        time.sleep(10)
                        continue
                    
                    # Obtenir la cible
                    target_url = self.config.get('target', {}).get('url', 'https://httpbin.org/get')
                    
                    # Effectuer la requête
                    result = self.simulate_request(pod_id, target_url, proxy)
                    
                    # Vérifier si l'IP est bannie
                    if self.check_ip_ban(result):
                        self.logger.warning(f"Pod {pod_id}: IP bannie détectée: {proxy}")
                        self.proxy_manager.mark_proxy_as_failed(proxy)
                        # Changer d'IP
                        new_proxy = self.proxy_manager.get_random_proxy()
                        if new_proxy:
                            self.logger.info(f"Pod {pod_id}: Changement d'IP vers {new_proxy}")
                            # Réessayer avec le nouveau proxy
                            result = self.simulate_request(pod_id, target_url, new_proxy)
                    
                    self.logger.info(f"Pod {pod_id}: {result['status']}")
                    time.sleep(1)  # Pause entre les requêtes
                    
                except Exception as e:
                    self.logger.error(f"Erreur dans le pod {pod_id}: {e}")
                    time.sleep(5)
                    
        # Créer les threads pour les pods
        threads = []
        for i in range(pod_count):
            thread = threading.Thread(target=pod_worker, args=(i,))
            thread.daemon = True
            thread.start()
            threads.append(thread)
            
        return threads
        
    def start(self):
        """Démarrer l'outil"""
        self.logger.info("Démarrage de l'outil IP Rotator...")
        
        # Démarrer le monitoring
        self.start_monitoring()
        
        # Calculer le nombre de pods
        pod_count = self.calculate_pod_count()
        
        # Démarrer les pods
        threads = self.run_pods(pod_count)
        
        try:
            # Attendre que les threads s'exécutent
            for thread in threads:
                thread.join()
                
        except KeyboardInterrupt:
            self.logger.info("Arrêt demandé...")
            self.running = False
            
        self.logger.info("Outil arrêté")

# Point d'entrée
if __name__ == "__main__":
    tool = IPRotatorTool()
    tool.start()
