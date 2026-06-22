import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Optional

import requests
import yaml
from flask import Flask, Response, jsonify, request
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, generate_latest

from monitoring.stats import StatsManager
from utils.hardware import HardwareMonitor
from utils.proxy_manager import ProxyManager


logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
)

LOGGER = logging.getLogger("dened")

REQUESTS_TOTAL = Counter("dened_requests_total", "Total des requêtes traitées", ["result", "mode"])
PROXIES_AVAILABLE = Gauge("dened_proxies_available", "Nombre de proxys disponibles")
SYSTEM_MEMORY_PERCENT = Gauge("dened_memory_percent", "Utilisation mémoire en pourcentage")
SYSTEM_CPU_PERCENT = Gauge("dened_cpu_percent", "Utilisation CPU en pourcentage")
SCHEDULER_RUNNING = Gauge("dened_scheduler_running", "Scheduler actif")


UI_HTML = r"""
<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <title>DENED Control Center</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    :root {
      --bg: #0b1020;
      --panel: rgba(255,255,255,.08);
      --panel2: rgba(255,255,255,.12);
      --text: #f6f7fb;
      --muted: #aab2c8;
      --accent: #7c3aed;
      --good: #22c55e;
      --bad: #ef4444;
      --warn: #f59e0b;
      --border: rgba(255,255,255,.14);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--text);
      background:
        radial-gradient(circle at top left, rgba(124,58,237,.35), transparent 35%),
        radial-gradient(circle at bottom right, rgba(14,165,233,.25), transparent 30%),
        var(--bg);
      min-height: 100vh;
    }
    .wrap { max-width: 1180px; margin: 0 auto; padding: 28px; }
    .hero {
      display: flex; justify-content: space-between; gap: 20px; align-items: center;
      margin-bottom: 22px;
    }
    h1 { margin: 0; font-size: 34px; letter-spacing: -0.04em; }
    .subtitle { color: var(--muted); margin-top: 8px; }
    .badge {
      padding: 10px 14px; border: 1px solid var(--border); border-radius: 999px;
      background: var(--panel); color: var(--muted);
    }
    .grid {
      display: grid; grid-template-columns: 1.1fr .9fr; gap: 18px;
    }
    .cards {
      display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin-bottom: 18px;
    }
    .card, .panel {
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 22px;
      backdrop-filter: blur(14px);
      box-shadow: 0 20px 60px rgba(0,0,0,.25);
    }
    .card { padding: 16px; }
    .label { font-size: 12px; color: var(--muted); text-transform: uppercase; letter-spacing: .08em; }
    .value { font-size: 28px; font-weight: 800; margin-top: 8px; }
    .panel { padding: 20px; }
    .panel h2 { margin: 0 0 14px; font-size: 18px; }
    input, select {
      width: 100%;
      padding: 12px 13px;
      border-radius: 14px;
      border: 1px solid var(--border);
      background: rgba(0,0,0,.25);
      color: var(--text);
      outline: none;
    }
    option { color: #111; }
    .row { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 12px; }
    .full { margin-bottom: 12px; }
    button {
      border: 0;
      border-radius: 14px;
      padding: 12px 15px;
      color: white;
      font-weight: 700;
      cursor: pointer;
      background: var(--accent);
    }
    button.stop { background: var(--bad); }
    button.secondary { background: var(--panel2); border: 1px solid var(--border); }
    .actions { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 12px; }
    pre {
      background: rgba(0,0,0,.35);
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 14px;
      overflow: auto;
      max-height: 360px;
      color: #dbeafe;
    }
    .mode-help {
      display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-top: 14px;
    }
    .mode {
      background: rgba(255,255,255,.06);
      border: 1px solid var(--border);
      border-radius: 18px;
      padding: 14px;
    }
    .mode strong { display: block; margin-bottom: 6px; }
    .safe { color: var(--warn); font-size: 13px; line-height: 1.45; }
    @media (max-width: 900px) {
      .grid, .cards, .mode-help { grid-template-columns: 1fr; }
      .hero { flex-direction: column; align-items: flex-start; }
    }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="hero">
      <div>
        <h1>DENED Control Center</h1>
        <div class="subtitle">Pilotage des modes, monitoring, proxys et charge contrôlée.</div>
      </div>
      <div class="badge" id="statusBadge">Chargement...</div>
    </div>

    <div class="cards">
      <div class="card"><div class="label">État</div><div class="value" id="running">-</div></div>
      <div class="card"><div class="label">Requêtes</div><div class="value" id="total">-</div></div>
      <div class="card"><div class="label">Succès</div><div class="value" id="success">-</div></div>
      <div class="card"><div class="label">RPS</div><div class="value" id="rps">-</div></div>
    </div>

    <div class="grid">
      <div class="panel">
        <h2>Contrôle d’exécution</h2>

        <div class="full">
          <label class="label">URL cible autorisée</label>
          <input id="targetUrl" placeholder="https://httpbin.org/get">
        </div>

        <div class="row">
          <div>
            <label class="label">Mode</label>
            <select id="mode">
              <option value="basic">Basique</option>
              <option value="fast">Rapide</option>
              <option value="extreme">Extrême</option>
            </select>
          </div>
          <div>
            <label class="label">Méthode</label>
            <select id="method">
              <option value="GET">GET</option>
              <option value="POST">POST</option>
            </select>
          </div>
        </div>

        <div class="row">
          <div>
            <label class="label">Intervalle basique, en secondes</label>
            <input id="interval" type="number" min="1" value="5">
          </div>
          <div>
            <label class="label">Durée rapide, en secondes</label>
            <input id="duration" type="number" min="1" value="60">
          </div>
        </div>

        <div class="row">
          <div>
            <label class="label">RPS max</label>
            <input id="maxRps" type="number" min="1" value="20">
          </div>
          <div>
            <label class="label">Workers max</label>
            <input id="workers" type="number" min="1" value="8">
          </div>
        </div>

        <div class="actions">
          <button onclick="startRun()">Démarrer</button>
          <button class="stop" onclick="stopRun()">Arrêter</button>
          <button class="secondary" onclick="refresh()">Rafraîchir</button>
        </div>

        <div class="mode-help">
          <div class="mode"><strong>Basique</strong>1 requête toutes les X secondes. Cible mémoire : 25%.</div>
          <div class="mode"><strong>Rapide</strong>RPS élevé pendant une durée définie. Cible mémoire : 50%.</div>
          <div class="mode"><strong>Extrême</strong>RPS élevé sans durée. Arrêt manuel. Cible mémoire : 80%.</div>
        </div>

        <p class="safe">
          Utilisation prévue uniquement sur vos propres services, environnements de test ou cibles explicitement autorisées.
        </p>
      </div>

      <div class="panel">
        <h2>État runtime</h2>
        <pre id="runtime">{}</pre>
      </div>
    </div>

    <div class="panel" style="margin-top:18px;">
      <h2>Configuration & scaling Kubernetes</h2>
      <pre id="scaleHelp">Chargement...</pre>
    </div>
  </div>

<script>
async function api(path, options={}) {
  const res = await fetch(path, options);
  return await res.json();
}

async function refresh() {
  const data = await api('/api/runtime');
  document.getElementById('runtime').textContent = JSON.stringify(data, null, 2);

  const s = data.stats?.stats || {};
  document.getElementById('running').textContent = data.scheduler?.running ? 'ON' : 'OFF';
  document.getElementById('total').textContent = s.total_requests ?? 0;
  document.getElementById('success').textContent = s.successful_requests ?? 0;
  document.getElementById('rps').textContent = (s.requests_per_second ?? 0).toFixed(2);

  const badge = document.getElementById('statusBadge');
  badge.textContent = data.scheduler?.running ? 'Scheduler actif' : 'Scheduler arrêté';
  badge.style.color = data.scheduler?.running ? '#22c55e' : '#aab2c8';

  document.getElementById('scaleHelp').textContent =
`Commandes utiles :

# Voir les pods
kubectl get pods

# Adapter les pods selon la mémoire
./scripts/dened_scale.sh basic
./scripts/dened_scale.sh fast
./scripts/dened_scale.sh extreme

# Ou manuellement
kubectl scale deployment dened --replicas=N

Mode actuel : ${data.scheduler?.mode || 'aucun'}
Mémoire cible du mode : ${data.scheduler?.memory_target_percent || '-'} %
`;
}

async function loadDefaults() {
  const cfg = await api('/api/config');
  document.getElementById('targetUrl').value = cfg.target?.url || '';
  const mode = document.getElementById('mode').value;
  applyModeDefaults(cfg.modes?.[mode] || {});
}

async function applyModeDefaults(m) {
  if (m.request_interval_seconds !== undefined) document.getElementById('interval').value = m.request_interval_seconds || 1;
  if (m.duration_seconds !== undefined && m.duration_seconds !== null) document.getElementById('duration').value = m.duration_seconds;
  if (m.max_rps !== undefined) document.getElementById('maxRps').value = m.max_rps;
  if (m.max_workers !== undefined) document.getElementById('workers').value = m.max_workers;
}

document.getElementById('mode').addEventListener('change', async () => {
  const cfg = await api('/api/config');
  const mode = document.getElementById('mode').value;
  applyModeDefaults(cfg.modes?.[mode] || {});
});

async function startRun() {
  const payload = {
    target_url: document.getElementById('targetUrl').value,
    mode: document.getElementById('mode').value,
    method: document.getElementById('method').value,
    request_interval_seconds: Number(document.getElementById('interval').value),
    duration_seconds: document.getElementById('mode').value === 'extreme' ? null : Number(document.getElementById('duration').value),
    max_rps: Number(document.getElementById('maxRps').value),
    max_workers: Number(document.getElementById('workers').value)
  };

  const data = await api('/api/start', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(payload)
  });

  document.getElementById('runtime').textContent = JSON.stringify(data, null, 2);
  refresh();
}

async function stopRun() {
  const data = await api('/api/stop', { method: 'POST' });
  document.getElementById('runtime').textContent = JSON.stringify(data, null, 2);
  refresh();
}

loadDefaults().then(refresh);
setInterval(refresh, 2500);
</script>
</body>
</html>
"""


class LoadScheduler:
    def __init__(self, dened_app: "DenedApp"):
        self.dened_app = dened_app
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.runtime = {
            "running": False,
            "mode": None,
            "target_url": None,
            "started_at": None,
            "stopped_at": None,
            "duration_seconds": None,
            "max_rps": None,
            "max_workers": None,
            "request_interval_seconds": None,
            "memory_target_percent": None,
            "last_message": "Scheduler jamais démarré",
        }

    def is_running(self) -> bool:
        with self._lock:
            return bool(self.runtime["running"])

    def start(self, payload: Dict) -> Dict:
        with self._lock:
            if self.runtime["running"]:
                return {"ok": False, "error": "Scheduler déjà actif", "scheduler": self.runtime}

            mode = payload.get("mode", "basic")
            modes = self.dened_app.config.get("modes", {})

            if mode not in modes:
                return {"ok": False, "error": f"Mode inconnu: {mode}"}

            mode_cfg = dict(modes[mode])
            target_url = payload.get("target_url") or self.dened_app.config.get("target", {}).get("url")

            if not target_url:
                return {"ok": False, "error": "URL cible manquante"}

            if self.dened_app.config.get("limits", {}).get("require_explicit_target", True):
                if target_url in {"", "http://example.com", "https://example.com"}:
                    return {"ok": False, "error": "Définir une cible explicite autorisée"}

            request_interval = payload.get("request_interval_seconds", mode_cfg.get("request_interval_seconds"))
            duration = payload.get("duration_seconds", mode_cfg.get("duration_seconds"))
            max_rps = int(payload.get("max_rps", mode_cfg.get("max_rps", 1)))
            max_workers = int(payload.get("max_workers", mode_cfg.get("max_workers", 1)))
            method = payload.get("method", "GET")

            if mode == "basic":
                max_rps = 1
                max_workers = 1
                if not request_interval or float(request_interval) < 1:
                    request_interval = 1

            if mode == "fast":
                if not duration or int(duration) <= 0:
                    return {"ok": False, "error": "Le mode rapide exige une durée en secondes"}

            if mode == "extreme":
                duration = None

            self._stop_event.clear()
            self.runtime = {
                "running": True,
                "mode": mode,
                "target_url": target_url,
                "method": method,
                "started_at": time.time(),
                "stopped_at": None,
                "duration_seconds": duration,
                "max_rps": max_rps,
                "max_workers": max_workers,
                "request_interval_seconds": request_interval,
                "memory_target_percent": mode_cfg.get("memory_target_percent"),
                "last_message": "Scheduler démarré",
            }

            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()

            SCHEDULER_RUNNING.set(1)

            return {"ok": True, "scheduler": self.runtime}

    def stop(self) -> Dict:
        self._stop_event.set()

        with self._lock:
            self.runtime["running"] = False
            self.runtime["stopped_at"] = time.time()
            self.runtime["last_message"] = "Arrêt demandé"

        SCHEDULER_RUNNING.set(0)

        return {"ok": True, "scheduler": self.snapshot()}

    def snapshot(self) -> Dict:
        with self._lock:
            return dict(self.runtime)

    def _limits_allow_run(self) -> bool:
        limits = self.dened_app.config.get("limits", {})

        if not limits.get("safety_enabled", True):
            return True

        check = self.dened_app.hardware.limits_ok(
            max_memory_percent=float(limits.get("max_memory_percent", 85)),
            max_cpu_percent=float(limits.get("max_cpu_percent", 90)),
        )

        if not check["ok"]:
            with self._lock:
                self.runtime["last_message"] = "Pause sécurité: CPU ou mémoire trop élevé"
            time.sleep(2)
            return False

        return True

    def _run_one(self, target_url: str, method: str) -> None:
        self.dened_app.fetch_url(url=target_url, method=method)

    def _run(self) -> None:
        snap = self.snapshot()
        mode = snap["mode"]
        target_url = snap["target_url"]
        method = snap.get("method", "GET")
        started = time.time()
        duration = snap.get("duration_seconds")
        max_rps = max(1, int(snap.get("max_rps") or 1))
        max_workers = max(1, int(snap.get("max_workers") or 1))
        interval = snap.get("request_interval_seconds")

        LOGGER.info("Scheduler start mode=%s target=%s", mode, target_url)

        try:
            if mode == "basic":
                while not self._stop_event.is_set():
                    if duration and time.time() - started >= float(duration):
                        break

                    if self._limits_allow_run():
                        self._run_one(target_url, method)

                    time.sleep(max(1.0, float(interval or 1)))

            else:
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    while not self._stop_event.is_set():
                        if duration and time.time() - started >= float(duration):
                            break

                        if not self._limits_allow_run():
                            continue

                        loop_started = time.time()

                        for _ in range(max_rps):
                            if self._stop_event.is_set():
                                break
                            executor.submit(self._run_one, target_url, method)

                        elapsed = time.time() - loop_started
                        sleep_for = max(0, 1.0 - elapsed)
                        time.sleep(sleep_for)

        finally:
            with self._lock:
                self.runtime["running"] = False
                self.runtime["stopped_at"] = time.time()
                self.runtime["last_message"] = "Scheduler terminé"

            SCHEDULER_RUNNING.set(0)
            LOGGER.info("Scheduler stopped")


class DenedApp:
    def __init__(self, config_path: str):
        self.config_path = config_path
        self.config = self._load_config(config_path)

        proxy_cfg = self.config.get("proxy", {})

        self.proxy_manager = ProxyManager(
            proxies=proxy_cfg.get("proxies", []),
            rotation_mode=proxy_cfg.get("rotation_mode", "round_robin"),
        )

        self.proxy_manager.load_from_file(proxy_cfg.get("proxy_file", "/proxies/proxies.txt"))

        self.stats = StatsManager()
        self.hardware = HardwareMonitor()
        self.http = requests.Session()
        self.app = Flask(__name__)
        self.scheduler = LoadScheduler(self)
        self._setup_routes()

    @staticmethod
    def _load_config(path: str) -> Dict:
        with open(path, "r", encoding="utf-8") as handle:
            return yaml.safe_load(handle) or {}

    def _proxy_dict(self, proxy: Optional[str]) -> Optional[Dict[str, str]]:
        if not proxy:
            return None
        return {"http": proxy, "https": proxy}

    def _safe_response_body(self, response: requests.Response) -> str:
        max_bytes = int(self.config.get("request", {}).get("max_response_bytes", 200000))
        content = response.content[:max_bytes]
        return content.decode(response.encoding or "utf-8", errors="replace")

    def fetch_url(self, url: str, method: str = "GET", json_body: Optional[Dict] = None) -> Dict:
        request_cfg = self.config.get("request", {})
        proxy_cfg = self.config.get("proxy", {})

        timeout = int(request_cfg.get("timeout_seconds", 10))
        allowed_methods = set(request_cfg.get("allowed_methods", ["GET", "POST"]))
        method = method.upper()

        if method not in allowed_methods:
            return {
                "ok": False,
                "error": f"Méthode non autorisée: {method}",
                "status_code": 400,
            }

        proxy = self.proxy_manager.get_proxy()
        allow_direct = bool(proxy_cfg.get("allow_direct_fallback", True))

        if not proxy and not allow_direct:
            return {
                "ok": False,
                "error": "Aucun proxy disponible et fallback direct désactivé",
                "status_code": 503,
            }

        started = time.time()

        try:
            response = self.http.request(
                method=method,
                url=url,
                json=json_body if method == "POST" else None,
                proxies=self._proxy_dict(proxy),
                timeout=timeout,
                headers={"User-Agent": "dened/2.0"},
            )

            elapsed = round(time.time() - started, 4)
            success = 200 <= response.status_code < 500

            self.stats.record_request(success=success, proxy=proxy)

            if proxy and success:
                self.proxy_manager.mark_working(proxy)

            REQUESTS_TOTAL.labels(
                result="success" if success else "failed",
                mode="proxy" if proxy else "direct",
            ).inc()

            return {
                "ok": success,
                "status_code": response.status_code,
                "elapsed_seconds": elapsed,
                "proxy_used": proxy,
                "mode": "proxy" if proxy else "direct",
                "headers": dict(response.headers),
                "body_preview": self._safe_response_body(response),
            }

        except requests.RequestException as exc:
            self.stats.record_request(success=False, proxy=proxy, error=str(exc))

            if proxy:
                self.proxy_manager.mark_failed(proxy)

            REQUESTS_TOTAL.labels(
                result="failed",
                mode="proxy" if proxy else "direct",
            ).inc()

            return {
                "ok": False,
                "status_code": 502,
                "elapsed_seconds": round(time.time() - started, 4),
                "proxy_used": proxy,
                "mode": "proxy" if proxy else "direct",
                "error": str(exc),
            }

    def runtime_payload(self) -> Dict:
        proxy_status = self.proxy_manager.status()
        system = self.hardware.get_system_stats()

        PROXIES_AVAILABLE.set(proxy_status["available"])
        SYSTEM_MEMORY_PERCENT.set(system["memory_percent"])
        SYSTEM_CPU_PERCENT.set(system["cpu_percent"])

        return {
            "scheduler": self.scheduler.snapshot(),
            "stats": self.stats.snapshot(),
            "proxies": proxy_status,
            "system": system,
            "config_file": self.config_path,
        }

    def _setup_routes(self) -> None:
        @self.app.get("/")
        def ui():
            return Response(UI_HTML, mimetype="text/html")

        @self.app.get("/api/config")
        def api_config():
            return jsonify(self.config)

        @self.app.get("/api/runtime")
        def api_runtime():
            return jsonify(self.runtime_payload())

        @self.app.post("/api/start")
        def api_start():
            payload = request.get_json(silent=True) or {}
            result = self.scheduler.start(payload)
            return jsonify(result), 200 if result.get("ok") else 400

        @self.app.post("/api/stop")
        def api_stop():
            return jsonify(self.scheduler.stop())

        @self.app.get("/health")
        def health():
            limits = self.config.get("limits", {})

            check = self.hardware.limits_ok(
                max_memory_percent=float(limits.get("max_memory_percent", 85)),
                max_cpu_percent=float(limits.get("max_cpu_percent", 90)),
            )

            status_code = 200 if check["ok"] else 503

            return jsonify({
                "status": "healthy" if check["ok"] else "degraded",
                **check,
            }), status_code

        @self.app.get("/stats")
        def stats():
            return jsonify(self.runtime_payload())

        @self.app.get("/proxies")
        def proxies():
            return jsonify(self.proxy_manager.status())

        @self.app.post("/proxies")
        def add_proxy():
            payload = request.get_json(silent=True) or {}
            proxy = payload.get("proxy")
            added = self.proxy_manager.add_proxy(proxy)

            return jsonify({
                "added": added,
                "proxies": self.proxy_manager.status(),
            }), 201 if added else 400

        @self.app.get("/fetch")
        def fetch_get():
            url = request.args.get("url")

            if not url:
                return jsonify({
                    "ok": False,
                    "error": "Paramètre obligatoire manquant: url",
                }), 400

            result = self.fetch_url(url=url, method="GET")
            return jsonify(result), int(result.get("status_code", 200)) if not result.get("ok") else 200

        @self.app.post("/fetch")
        def fetch_post():
            payload = request.get_json(silent=True) or {}
            url = payload.get("url")

            if not url:
                return jsonify({
                    "ok": False,
                    "error": "Champ obligatoire manquant: url",
                }), 400

            result = self.fetch_url(
                url=url,
                method=payload.get("method", "GET"),
                json_body=payload.get("json"),
            )

            return jsonify(result), int(result.get("status_code", 200)) if not result.get("ok") else 200

        @self.app.get("/metrics")
        def metrics():
            self.runtime_payload()
            return generate_latest(), 200, {"Content-Type": CONTENT_TYPE_LATEST}

    def start_background_logger(self) -> None:
        interval = int(self.config.get("monitoring", {}).get("log_interval_seconds", 30))

        def loop():
            while True:
                LOGGER.info("runtime=%s", self.runtime_payload())
                time.sleep(interval)

        threading.Thread(target=loop, daemon=True).start()

    def run(self) -> None:
        self.start_background_logger()

        server_cfg = self.config.get("server", {})

        self.app.run(
            host=server_cfg.get("host", "0.0.0.0"),
            port=int(os.getenv("PORT", server_cfg.get("port", 8080))),
            threaded=True,
        )


def create_app():
    config_path = os.getenv("CONFIG_FILE", "config.yaml")
    return DenedApp(config_path).app


if __name__ == "__main__":
    config_path = os.getenv("CONFIG_FILE", "config.yaml")
    DenedApp(config_path).run()
