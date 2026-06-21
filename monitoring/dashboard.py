import threading
import time
import logging
from flask import Flask, render_template_string, jsonify
from stats import StatsManager
import json

class Dashboard:
    def __init__(self, stats_manager: StatsManager, port: int = 8080):
        self.stats_manager = stats_manager
        self.port = port
        self.app = Flask(__name__)
        self.setup_routes()
        self.logger = logging.getLogger(__name__)
        
    def setup_routes(self):
        """Configurer les routes du dashboard"""
        
        @self.app.route('/')
        def index():
            return render_template_string("""
<!DOCTYPE html>
<html>
<head>
    <title>IP Rotator Dashboard</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background-color: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .stat-card {
            background-color: #f8f9fa;
            padding: 20px;
            border-radius: 6px;
            border-left: 4px solid #007bff;
        }
        .stat-card h3 {
            margin-top: 0;
            color: #333;
        }
        .stat-value {
            font-size: 2em;
            font-weight: bold;
            color: #007bff;
        }
        .chart-container {
            height: 300px;
            margin-bottom: 30px;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }
        th, td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }
        th {
            background-color: #f8f9fa;
            font-weight: bold;
        }
        tr:hover {
            background-color: #f5f5f5;
        }
        .status {
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 0.9em;
        }
        .status-success {
            background-color: #d4edda;
            color: #155724;
        }
        .status-failed {
            background-color: #f8d7da;
            color: #721c24;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>IP Rotator Dashboard</h1>
        
        <!-- Statistiques principales -->
        <div class="stats-grid" id="main-stats">
            <div class="stat-card">
                <h3>Total Requêtes</h3>
                <div class="stat-value" id="total-requests">0</div>
            </div>
            <div class="stat-card">
                <h3>Requêtes Réussies</h3>
                <div class="stat-value" id="successful-requests">0</div>
            </div>
            <div class="stat-card">
                <h3>Requêtes Échouées</h3>
                <div class="stat-value" id="failed-requests">0</div>
            </div>
            <div class="stat-card">
                <h3>IPs Bannies</h3>
                <div class="stat-value" id="banned-ips">0</div>
            </div>
        </div>

        <!-- IPs Actives -->
        <div class="stat-card">
            <h3>IPs Actives</h3>
            <div class="stat-value" id="active-ips">0</div>
        </div>

        <!-- Requêtes par seconde -->
        <div class="stat-card">
            <h3>Requêtes/Seconde</h3>
            <div class="stat-value" id="rps">0.0</div>
        </div>

        <!-- Utilisation des IPs -->
        <h2>Utilisation des IPs</h2>
        <table id="ip-usage-table">
            <thead>
                <tr>
                    <th>IP Address</th>
                    <th>Nombre de Requêtes</th>
                    <th>Pourcentage</th>
                </tr>
            </thead>
            <tbody id="ip-usage-body">
                <!-- Les données seront insérées ici par JavaScript -->
            </tbody>
        </table>

        <!-- Statistiques détaillées -->
        <h2>Statistiques Détaillées</h2>
        <div class="stat-card" id="detailed-stats">
            <!-- Les statistiques détaillées seront insérées ici -->
        </div>
    </div>

    <script>
        function updateDashboard() {
            fetch('/stats')
                .then(response => response.json())
                .then(data => {
                    // Mettre à jour les statistiques principales
                    document.getElementById('total-requests').textContent = data.stats.total_requests;
                    document.getElementById('successful-requests').textContent = data.stats.successful_requests;
                    document.getElementById('failed-requests').textContent = data.stats.failed_requests;
                    document.getElementById('banned-ips').textContent = data.stats.banned_ips;
                    document.getElementById('active-ips').textContent = data.stats.active_ips;
                    document.getElementById('rps').textContent = data.stats.requests_per_second.toFixed(2);
                    
                    // Mettre à jour le tableau des IPs
                    const tbody = document.getElementById('ip-usage-body');
                    tbody.innerHTML = '';
                    
                    if (data.ip_usage) {
                        let total_requests = data.stats.total_requests;
                        
                        Object.entries(data.ip_usage).forEach(([ip, count]) => {
                            const row = tbody.insertRow();
                            const ipCell = row.insertCell(0);
                            const countCell = row.insertCell(1);
                            const percentCell = row.insertCell(2);
                            
                            ipCell.textContent = ip;
                            countCell.textContent = count;
                            percentCell.textContent = total_requests > 0 ? ((count / total_requests) * 100).toFixed(2) + '%' : '0.00%';
                        });
                    }
                    
                    // Mettre à jour les statistiques détaillées
                    const detailedStats = document.getElementById('detailed-stats');
                    detailedStats.innerHTML = `
                        <h3>Détails</h3>
                        <p><strong>Uptime:</strong> ${Math.floor(data.uptime / 60)} minutes</p>
                        <p><strong>Dernière mise à jour:</strong> ${new Date().toLocaleString()}</p>
                    `;
                })
                .catch(error => {
                    console.error('Erreur lors de la récupération des données:', error);
                });
        }

        // Mettre à jour toutes les 5 secondes
        setInterval(updateDashboard, 5000);
        
        // Mise à jour immédiate au chargement
        updateDashboard();
    </script>
</body>
</html>
            """)
            
        @self.app.route('/stats')
        def stats():
            """Endpoint pour obtenir les statistiques"""
            try:
                detailed_stats = self.stats_manager.get_detailed_stats()
                return jsonify(detailed_stats)
            except Exception as e:
                return jsonify({"error": str(e)}), 500
                
        @self.app.route('/health')
        def health():
            """Endpoint de santé"""
            return jsonify({"status": "healthy"})
            
    def start(self):
        """Démarrer le dashboard"""
        self.logger.info(f"Démarrage du dashboard sur le port {self.port}")
        
        # Démarrer dans un thread séparé
        def run_dashboard():
            try:
                self.app.run(host='0.0.0.0', port=self.port, debug=False, threaded=True)
            except Exception as e:
                self.logger.error(f"Erreur lors du démarrage du dashboard: {e}")
                
        thread = threading.Thread(target=run_dashboard, daemon=True)
        thread.start()
        
        return thread

# Utilisation exemple
if __name__ == "__main__":
    # Pour test local uniquement
    from stats import StatsManager
    
    stats_manager = StatsManager()
    dashboard = Dashboard(stats_manager, port=8080)
    
    # Démarrer le dashboard
    dashboard_thread = dashboard.start()
    
    print("Dashboard démarré sur http://localhost:8080")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Arrêt du dashboard...")
