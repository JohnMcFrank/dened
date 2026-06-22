import logging
import os
import socket
import threading
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Optional

import requests
import yaml
from flask import Flask, Response, jsonify, request
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, generate_latest

from monitoring.stats import StatsManager
from tor_init import TORManager
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
      --bg:#060914; --panel:rgba(255,255,255,.075); --panel2:rgba(255,255,255,.11);
      --border:rgba(255,255,255,.14); --text:#f8fafc; --muted:#94a3b8;
      --accent:#8b5cf6; --accent2:#06b6d4; --good:#22c55e; --bad:#ef4444; --warn:#f59e0b;
    }
    * { box-sizing:border-box; }
    body {
      margin:0; color:var(--text); font-family:Inter,system-ui,Segoe UI,sans-serif;
      background:
        radial-gradient(circle at 15% 10%, rgba(139,92,246,.35), transparent 35%),
        radial-gradient(circle at 90% 15%, rgba(6,182,212,.25), transparent 30%),
        radial-gradient(circle at 50% 100%, rgba(34,197,94,.14), transparent 35%),
        var(--bg);
      min-height:100vh;
    }
    .wrap { max-width:1380px; margin:auto; padding:28px; }
    .top { display:flex; justify-content:space-between; align-items:center; gap:18px; margin-bottom:20px; }
    h1 { margin:0; font-size:34px; letter-spacing:-.04em; }
    .sub { color:var(--muted); margin-top:8px; }
    .pill { border:1px solid var(--border); background:var(--panel); padding:10px 14px; border-radius:999px; color:var(--muted); }
    .grid { display:grid; gap:16px; }
    .cards { grid-template-columns:repeat(5,1fr); margin-bottom:16px; }
    .main { grid-template-columns: 1.05fr .95fr; }
    .panel,.card {
      background:var(--panel); border:1px solid var(--border); border-radius:24px;
      backdrop-filter:blur(18px); box-shadow:0 20px 70px rgba(0,0,0,.28);
    }
    .panel { padding:20px; }
    .card { padding:16px; }
    .label { color:var(--muted); font-size:12px; text-transform:uppercase; letter-spacing:.09em; }
    .value { font-size:26px; font-weight:900; margin-top:7px; white-space:nowrap; }
    h2 { margin:0 0 14px; font-size:18px; }
    input,select {
      width:100%; border:1px solid var(--border); background:rgba(0,0,0,.28); color:var(--text);
      border-radius:14px; padding:12px 13px; outline:none;
    }
    option { color:#111; }
    .formgrid { display:grid; grid-template-columns:1.2fr .8fr; gap:12px; margin-bottom:12px; }
    .three { display:grid; grid-template-columns:repeat(3,1fr); gap:12px; margin-bottom:12px; }
    button {
      border:0; background:linear-gradient(135deg,var(--accent),var(--accent2)); color:white;
      padding:12px 16px; border-radius:14px; font-weight:800; cursor:pointer;
    }
    button.stop { background:var(--bad); }
    button.dark { background:var(--panel2); border:1px solid var(--border); }
    .actions { display:flex; flex-wrap:wrap; gap:10px; margin-top:10px; }
    table { width:100%; border-collapse:collapse; overflow:hidden; }
    th,td { text-align:left; padding:11px 9px; border-bottom:1px solid rgba(255,255,255,.09); font-size:13px; vertical-align:top; }
    th { color:var(--muted); font-size:11px; text-transform:uppercase; letter-spacing:.08em; }
    .ok { color:var(--good); font-weight:800; }
    .ko { color:var(--bad); font-weight:800; }
    .warn { color:var(--warn); }
    .scroll { max-height:330px; overflow:auto; border-radius:16px; border:1px solid rgba(255,255,255,.08); }
    pre {
      background:rgba(0,0,0,.34); border:1px solid var(--border); border-radius:16px;
      padding:14px; overflow:auto; max-height:250px; color:#dbeafe;
    }
    .mini { color:var(--muted); font-size:12px; line-height:1.45; }
    @media(max-width:1000px){ .cards,.main,.formgrid,.three{grid-template-columns:1fr;} }
  </style>
</head>
<body>
<div class="wrap">
  <div class="top">
    <div>
      <h1>DENED Control Center</h1>
      <div class="sub">Pilotage des modes, Tor, pods, IP de sortie et journal des requêtes.</div>
    </div>
    <div class="pill" id="statusPill">Chargement...</div>
  </div>

  <div class="grid cards">
    <div class="card"><div class="label">Scheduler</div><div class="value" id="running">-</div></div>
    <div class="card"><div class="label">Total</div><div class="value" id="total">-</div></div>
    <div class="card"><div class="label">Succès</div><div class="value" id="success">-</div></div>
    <div class="card"><div class="label">RPS</div><div class="value" id="rps">-</div></div>
    <div class="card"><div class="label">IP Tor</div><div class="value" id="torIp" style="font-size:18px;">-</div></div>
  </div>

  <div class="grid main">
    <div class="panel">
      <h2>Destination & modes</h2>

      <div class="formgrid">
        <div>
          <div class="label">Destination autorisée</div>
          <input id="targetUrl" placeholder="https://check.torproject.org/api/ip">
        </div>
        <div>
          <div class="label">Mode</div>
          <select id="mode">
            <option value="basic">Basique — 1 requête toutes les X secondes</option>
            <option value="fast">Rapide — RPS contrôlé pendant X secondes</option>
            <option value="extreme">Extrême contrôlé — jusqu’à arrêt manuel</option>
          </select>
        </div>
      </div>

      <div class="three">
        <div><div class="label">Intervalle basique</div><input id="interval" type="number" min="1" value="5"></div>
        <div><div class="label">Durée rapide</div><input id="duration" type="number" min="1" value="60"></div>
        <div><div class="label">Méthode</div><select id="method"><option>GET</option><option>POST</option></select></div>
      </div>

      <div class="three">
        <div><div class="label">RPS max</div><input id="maxRps" type="number" min="1" max="50" value="10"></div>
        <div><div class="label">Workers</div><input id="workers" type="number" min="1" max="16" value="4"></div>
        <div><div class="label">Pods souhaités</div><input id="replicas" type="number" min="1" value="1"></div>
      </div>

      <div class="actions">
        <button onclick="startRun()">Démarrer</button>
        <button class="stop" onclick="stopRun()">Arrêter</button>
        <button class="dark" onclick="newTorIdentity()">Nouvelle identité Tor</button>
        <button class="dark" onclick="refresh()">Rafraîchir</button>
      </div>

      <p class="mini">
        Utilisation prévue uniquement sur vos propres environnements ou destinations explicitement autorisées.
        Le scaling pods s’effectue via commande Kubernetes pour éviter de donner des droits d’écriture au pod.
      </p>
    </div>

    <div class="panel">
      <h2>Runtime</h2>
      <pre id="runtime">{}</pre>
    </div>
  </div>

  <div class="grid main" style="margin-top:16px;">
    <div class="panel">
      <h2>Pods Kubernetes</h2>
      <div class="scroll">
        <table>
          <thead><tr><th>Pod</th><th>Pod IP</th><th>Node</th><th>Phase</th><th>Ready</th></tr></thead>
          <tbody id="podsBody"></tbody>
        </table>
      </div>
    </div>

    <div class="panel">
      <h2>Proxys / Tor</h2>
      <div class="scroll">
        <table>
          <thead><tr><th>Proxy</th><th>Type</th><th>Statut</th></tr></thead>
          <tbody id="proxyBody"></tbody>
        </table>
      </div>
    </div>
  </div>

  <div class="panel" style="margin-top:16px;">
    <h2>Journal des requêtes envoyées</h2>
    <div class="scroll">
      <table>
        <thead><tr><th>Heure</th><th>Pod</th><th>Destination</th><th>Mode</th><th>Proxy</th><th>Status</th><th>Temps</th></tr></thead>
        <tbody id="requestsBody"></tbody>
      </table>
    </div>
  </div>

  <div class="panel" style="margin-top:16px;">
    <h2>Commandes scaling utiles</h2>
    <pre id="scaleCmd">kubectl scale deployment dened --replicas=1</pre>
  </div>
</div>

<script>
async function api(path, options={}) {
  const r = await fetch(path, options);
  return await r.json();
}

function fmtTime(ts) {
  if (!ts) return "-";
  return new Date(ts * 1000).toLocaleTimeString();
}

async function refresh() {
  const data = await api('/api/runtime');

  const stats = data.stats?.stats || {};
  const sch = data.scheduler || {};

  document.getElementById('runtime').textContent = JSON.stringify(data, null, 2);
  document.getElementById('running').textContent = sch.running ? 'ON' : 'OFF';
  document.getElementById('total').textContent = stats.total_requests ?? 0;
  document.getElementById('success').textContent = stats.successful_requests ?? 0;
  document.getElementById('rps').textContent = Number(stats.requests_per_second ?? 0).toFixed(2);
  document.getElementById('torIp').textContent = data.tor?.data?.IP || "-";

  const pill = document.getElementById('statusPill');
  pill.textContent = sch.running ? `Actif — ${sch.mode}` : 'Arrêté';
  pill.style.color = sch.running ? '#22c55e' : '#94a3b8';

  const proxies = data.proxies?.proxies || [];
  document.getElementById('proxyBody').innerHTML = proxies.map(p =>
    `<tr><td>${p.proxy}</td><td>${p.type}</td><td class="${p.status === 'available' ? 'ok':'ko'}">${p.status}</td></tr>`
  ).join('');

  const reqs = data.recent_requests || [];
  document.getElementById('requestsBody').innerHTML = reqs.slice().reverse().map(r =>
    `<tr>
      <td>${fmtTime(r.timestamp)}</td><td>${r.pod_name || '-'}</td><td>${r.url || '-'}</td>
      <td>${r.mode || '-'}</td><td>${r.proxy_used || 'direct'}</td>
      <td class="${r.ok ? 'ok':'ko'}">${r.status_code}</td><td>${r.elapsed_seconds}s</td>
    </tr>`
  ).join('');

  const pods = await api('/api/pods');
  document.getElementById('podsBody').innerHTML = (pods.pods || []).map(p =>
    `<tr>
      <td>${p.name}</td><td>${p.pod_ip || '-'}</td><td>${p.node || '-'}</td>
      <td class="${p.phase === 'Running' ? 'ok':'warn'}">${p.phase}</td><td>${p.ready}</td>
    </tr>`
  ).join('');

  const replicas = document.getElementById('replicas').value || 1;
  document.getElementById('scaleCmd').textContent =
`kubectl scale deployment dened --replicas=${replicas}

# Voir les pods
kubectl get pods -l app=dened -o wide

# Voir les logs app
kubectl logs deployment/dened -c dened --tail=100

# Voir les logs Tor
kubectl logs deployment/dened -c tor --tail=100`;
}

async function loadDefaults() {
  const cfg = await api('/api/config');
  document.getElementById('targetUrl').value = cfg.target?.url || 'https://check.torproject.org/api/ip';
}

async function startRun() {
  const mode = document.getElementById('mode').value;
  const payload = {
    target_url: document.getElementById('targetUrl').value,
    mode,
    method: document.getElementById('method').value,
    request_interval_seconds: Number(document.getElementById('interval').value),
    duration_seconds: mode === 'extreme' ? null : Number(document.getElementById('duration').value),
    max_rps: Number(document.getElementById('maxRps').value),
    max_workers: Number(document.getElementById('workers').value)
  };
  const res = await api('/api/start', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)});
  document.getElementById('runtime').textContent = JSON.stringify(res, null, 2);
  refresh();
}

async function stopRun() {
  await api('/api/stop', {method:'POST'});
  refresh();
}

async function newTorIdentity() {
  const res = await api('/tor/new-identity', {method:'POST'});
  document.getElementById('runtime').textContent = JSON.stringify(res, null, 2);
  setTimeout(refresh, 12000);
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

            request_interval = payload.get("request_interval_seconds", mode_cfg.get("request_interval_seconds", 5))
            duration = payload.get("duration_seconds", mode_cfg.get("duration_seconds"))
            max_rps = min(int(payload.get("max_rps", mode_cfg.get("max_rps", 1))), 50)
            max_workers = min(int(payload.get("max_workers", mode_cfg.get("max_workers", 1))), 16)
            method = payload.get("method", "GET")

            if mode == "basic":
                max_rps = 1
                max_workers = 1
                request_interval = max(1, float(request_interval or 1))

            if mode == "fast" and (not duration or int(duration) <= 0):
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
                        time.sleep(max(0, 1.0 - (time.time() - loop_started)))
        finally:
            with self._lock:
                self.runtime["running"] = False
                self.runtime["stopped_at"] = time.time()
                self.runtime["last_message"] = "Scheduler terminé"
            SCHEDULER_RUNNING.set(0)


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
        self.tor_manager = TORManager()
        self.app = Flask(__name__)
        self.scheduler = LoadScheduler(self)
        self.recent_requests = deque(maxlen=200)

        self.pod_name = os.getenv("POD_NAME", socket.gethostname())
        self.pod_ip = os.getenv("POD_IP", "")

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
        return response.content[:max_bytes].decode(response.encoding or "utf-8", errors="replace")

    def _record_recent(self, item: Dict) -> None:
        self.recent_requests.append(item)

    def fetch_url(self, url: str, method: str = "GET", json_body: Optional[Dict] = None) -> Dict:
        request_cfg = self.config.get("request", {})
        proxy_cfg = self.config.get("proxy", {})

        timeout = int(request_cfg.get("timeout_seconds", 10))
        allowed_methods = set(request_cfg.get("allowed_methods", ["GET", "POST"]))
        method = method.upper()

        if method not in allowed_methods:
            return {"ok": False, "error": f"Méthode non autorisée: {method}", "status_code": 400}

        proxy = self.proxy_manager.get_proxy()
        allow_direct = bool(proxy_cfg.get("allow_direct_fallback", True))

        if not proxy and not allow_direct:
            return {"ok": False, "error": "Aucun proxy disponible et fallback direct désactivé", "status_code": 503}

        started = time.time()

        try:
            response = self.http.request(
                method=method,
                url=url,
                json=json_body if method == "POST" else None,
                proxies=self._proxy_dict(proxy),
                timeout=timeout,
                headers={"User-Agent": "dened/3.0"},
            )

            elapsed = round(time.time() - started, 4)
            success = 200 <= response.status_code < 500
            self.stats.record_request(success=success, proxy=proxy)

            if proxy and success:
                self.proxy_manager.mark_working(proxy)

            REQUESTS_TOTAL.labels(result="success" if success else "failed", mode="proxy" if proxy else "direct").inc()

            result = {
                "ok": success,
                "status_code": response.status_code,
                "elapsed_seconds": elapsed,
                "proxy_used": proxy,
                "mode": "proxy" if proxy else "direct",
                "headers": dict(response.headers),
                "body_preview": self._safe_response_body(response),
            }

            self._record_recent({
                "timestamp": time.time(),
                "pod_name": self.pod_name,
                "pod_ip": self.pod_ip,
                "url": url,
                "ok": success,
                "status_code": response.status_code,
                "elapsed_seconds": elapsed,
                "proxy_used": proxy,
                "mode": "proxy" if proxy else "direct",
            })

            return result

        except requests.RequestException as exc:
            elapsed = round(time.time() - started, 4)
            self.stats.record_request(success=False, proxy=proxy, error=str(exc))

            if proxy:
                self.proxy_manager.mark_failed(proxy)
                if proxy.startswith(("socks5://", "socks5h://")):
                    self.tor_manager.request_new_identity()

            REQUESTS_TOTAL.labels(result="failed", mode="proxy" if proxy else "direct").inc()

            self._record_recent({
                "timestamp": time.time(),
                "pod_name": self.pod_name,
                "pod_ip": self.pod_ip,
                "url": url,
                "ok": False,
                "status_code": 502,
                "elapsed_seconds": elapsed,
                "proxy_used": proxy,
                "mode": "proxy" if proxy else "direct",
                "error": str(exc),
            })

            return {
                "ok": False,
                "status_code": 502,
                "elapsed_seconds": elapsed,
                "proxy_used": proxy,
                "mode": "proxy" if proxy else "direct",
                "error": str(exc),
            }

    def get_kubernetes_pods(self) -> Dict:
        token_path = "/var/run/secrets/kubernetes.io/serviceaccount/token"
        ns_path = "/var/run/secrets/kubernetes.io/serviceaccount/namespace"
        ca_path = "/var/run/secrets/kubernetes.io/serviceaccount/ca.crt"

        if not os.path.exists(token_path):
            return {
                "ok": True,
                "source": "local",
                "pods": [{
                    "name": self.pod_name,
                    "pod_ip": self.pod_ip,
                    "node": "-",
                    "phase": "local",
                    "ready": "unknown",
                }],
            }

        try:
            token = open(token_path, "r", encoding="utf-8").read().strip()
            namespace = open(ns_path, "r", encoding="utf-8").read().strip()
            url = f"https://kubernetes.default.svc/api/v1/namespaces/{namespace}/pods?labelSelector=app%3Ddened"

            response = requests.get(
                url,
                headers={"Authorization": f"Bearer {token}"},
                verify=ca_path,
                timeout=5,
            )
            response.raise_for_status()

            pods = []
            for item in response.json().get("items", []):
                statuses = item.get("status", {}).get("containerStatuses", [])
                ready = f"{sum(1 for c in statuses if c.get('ready'))}/{len(statuses)}"
                pods.append({
                    "name": item.get("metadata", {}).get("name"),
                    "pod_ip": item.get("status", {}).get("podIP"),
                    "node": item.get("spec", {}).get("nodeName"),
                    "phase": item.get("status", {}).get("phase"),
                    "ready": ready,
                })

            return {"ok": True, "source": "kubernetes", "pods": pods}

        except Exception as exc:
            return {"ok": False, "error": str(exc), "pods": []}

    def runtime_payload(self) -> Dict:
        proxy_status = self.proxy_manager.status()
        system = self.hardware.get_system_stats()
        tor = self.tor_manager.check_tor_ip(timeout=8)

        PROXIES_AVAILABLE.set(proxy_status["available"])
        SYSTEM_MEMORY_PERCENT.set(system["memory_percent"])
        SYSTEM_CPU_PERCENT.set(system["cpu_percent"])

        return {
            "scheduler": self.scheduler.snapshot(),
            "stats": self.stats.snapshot(),
            "proxies": proxy_status,
            "system": system,
            "tor": tor,
            "pod": {"name": self.pod_name, "ip": self.pod_ip},
            "recent_requests": list(self.recent_requests),
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

        @self.app.get("/api/pods")
        def api_pods():
            return jsonify(self.get_kubernetes_pods())

        @self.app.post("/api/start")
        def api_start():
            result = self.scheduler.start(request.get_json(silent=True) or {})
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
            return jsonify({"status": "healthy" if check["ok"] else "degraded", **check}), 200 if check["ok"] else 503

        @self.app.get("/stats")
        def stats():
            return jsonify(self.runtime_payload())

        @self.app.get("/proxies")
        def proxies():
            return jsonify(self.proxy_manager.status())

        @self.app.get("/tor/status")
        def tor_status():
            return jsonify(self.tor_manager.check_tor_ip())

        @self.app.post("/tor/new-identity")
        def tor_new_identity():
            return jsonify(self.tor_manager.request_new_identity())

        @self.app.get("/fetch")
        def fetch_get():
            url = request.args.get("url")
            if not url:
                return jsonify({"ok": False, "error": "Paramètre obligatoire manquant: url"}), 400
            result = self.fetch_url(url=url, method="GET")
            return jsonify(result), int(result.get("status_code", 200)) if not result.get("ok") else 200

        @self.app.get("/metrics")
        def metrics():
            self.runtime_payload()
            return generate_latest(), 200, {"Content-Type": CONTENT_TYPE_LATEST}

    def run(self) -> None:
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
    DenedApp(os.getenv("CONFIG_FILE", "config.yaml")).run()
