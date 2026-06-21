import yaml
import time
import threading
import logging
import os
from typing import Dict, List
from utils.hardware import HardwareMonitor
from utils.bandwidth import BandwidthManager
from utils.proxy_manager import ProxyManager
from utils.internal_proxy import InternalProxyManager
from monitoring.stats import StatsManager
from monitoring.monitoring import MonitoringService
import requests

class IPRotatorTool:
    def __init__(self, config_file: str = "config.yaml"):
        self.load_config(config_file)
        self.hardware_monitor = HardwareMonitor()
        self.bandwidth_manager = BandwidthManager()
        self.proxy_manager = ProxyManager()
        self.internal_proxy_manager = InternalProxyManager()
        self.stats_manager = StatsManager()
        self.monitoring = MonitoringService(self.stats_manager)
        self.logger = logging.getLogger(__name__)
        self.running = False
        self.pod_name = os.environ.get('POD_NAME', 'unknown-pod')
        
        # Initialisation des paramètres
        self.setup_logging()
        self.init_system_resources()
        self.setup_internal_proxies()
        
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
        
    def setup_internal_proxies(self):
        """Configurer les proxies internes"""
        use_internal = os.environ.get('USE_INTERNAL_PROXY', 'false').lower() == 'true'
        
        if use_internal:
            self.logger.info("Configuration des proxies internes...")
            proxy_count = int(os.environ.get('INTERNAL_PROXY_COUNT', '10'))
            
            # Créer les proxies internes
            internal_proxies = self.internal_proxy_manager.create_internal_proxies(proxy_count)
            
            for proxy in internal_proxies:
                self.proxy_manager.add_proxy(proxy)
                
            self.logger.info(f"Initialisation de {len(internal_proxies)} proxies internes")
        else:
            # Utiliser les proxies externes traditionnels
            proxy_list = self.config.get('proxy_list', [])
            if proxy_list:
                for proxy in proxy_list:
                    self.proxy_manager.add_proxy(proxy)
                    
    def calculate_pod_count(self) -> int:
        """Calculer le nombre de pods nécessaires"""
        # Pour l'outil interne, on utilise un ratio basé sur la bande passante
        pod_bandwidth = 10  # Mbps par pod (exemple)
        
        max
