from typing import Dict, Any
import threading
import time
import logging
from flask import Flask, jsonify
from prometheus_client import Counter, Gauge, Histogram, start_http_server
from monitoring.stats import StatsManager

class MonitoringService:
    def __init__(self, stats_manager: StatsManager):
        self.stats_manager = stats_manager
        self.app = Flask(__name__)
        self.setup_prometheus()
        self.setup_routes()
        
    def setup_prometheus(self):
        """Configurer Prometheus metrics"""
        self.total_requests = Counter('ip_rotator_requests_total', 'Total requests')
        self.successful_requests = Counter('ip_rotator_requests_success', 'Successful requests')
        self.failed_requests = Counter('ip_rotator_requests_failed', 'Failed requests')
        self.active_ips = Gauge('ip_rotator_active_ips', 'Number of active IPs')
        self.banned_ips = Gauge('ip_rotator_banned_ips', 'Number of banned IPs')
        self.requests_per_second = Gauge('ip_rotator_requests_per_second', 'Requests per second')
        
    def setup_routes(self):
        """Configurer les routes de monitoring"""
        @self.app.route('/')
        def index():
            return jsonify({
                "service": "ip-rotator-tool",
                "status": "running",
                "endpoints": ["/health", "/stats", "/metrics"]
            })

        @self.app.route('/metrics')
        def metrics():
            return jsonify(self.get_current_stats())
            
        @self.app.route('/stats')
        def stats():
            return jsonify(self.get_current_stats())
            
        @self.app.route('/health')
        def health():
            return jsonify({"status": "healthy"})
            
    def get_current_stats(self) -> Dict:
        """Obtenir les statistiques actuelles"""
        detailed_stats = self.stats_manager.get_detailed_stats()
        
        # Mettre à jour les métriques Prometheus
        self.total_requests.inc(detailed_stats['stats']['total_requests'])
        self.successful_requests.inc(detailed_stats['stats']['successful_requests'])
        self.failed_requests.inc(detailed_stats['stats']['failed_requests'])
        self.active_ips.set(detailed_stats['stats']['active_ips'])
        self.banned_ips.set(detailed_stats['stats']['banned_ips'])
        self.requests_per_second.set(detailed_stats['stats']['requests_per_second'])
        
        return detailed_stats
        
    def start_monitoring_server(self, port: int = 9090):
        """Démarrer le serveur de monitoring"""
        start_http_server(port)
        self.app.run(host='0.0.0.0', port=8080, debug=False)
        
    def start_monitoring_thread(self):
        """Démarrer le thread de monitoring"""
        def monitor():
            while True:
                try:
                    stats = self.get_current_stats()
                    logging.info(f"Monitoring stats: {stats}")
                    time.sleep(30)  # Mise à jour toutes les 30 secondes
                except Exception as e:
                    logging.error(f"Monitoring error: {e}")
                    time.sleep(30)
                    
        thread = threading.Thread(target=monitor, daemon=True)
        thread.start()
