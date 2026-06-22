import json
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
:root{
  --bg:#050712;--panel:rgba(255,255,255,.075);--panel2:rgba(255,255,255,.115);
  --border:rgba(255,255,255,.14);--text:#f8fafc;--muted:#94a3b8;
  --accent:#8b5cf6;--cyan:#06b6d4;--good:#22c55e;--bad:#ef4444;--warn:#f59e0b;
}
*{box-sizing:border-box}
body{
  margin:0;color:var(--text);font-family:Inter,system-ui,Segoe UI,sans-serif;
  background:
    radial-gradient(circle at 10% 10%,rgba(139,92,246,.38),transparent 35%),
    radial-gradient(circle at 90% 10%,rgba(6,182,212,.24),transparent 32%),
    radial-gradient(circle at 50% 100%,rgba(34,197,94,.12),transparent 35%),
    var(--bg);
  min-height:100vh;
}
.wrap{max-width:1520px;margin:auto;padding:26px}
.top{display:flex;justify-content:space-between;gap:18px;align-items:center;margin-bottom:18px}
h1{margin:0;font-size:34px;letter-spacing:-.045em}
.sub{color:var(--muted);margin-top:7px}
.pill{border:1px solid var(--border);background:var(--panel);padding:10px 14px;border-radius:999px;color:var(--muted)}
.grid{display:grid;gap:16px}
.cards{grid-template-columns:repeat(8,1fr);margin-bottom:16px}
.main{grid-template-columns:1fr 1fr}
.panel,.card,.pod{
  background:var(--panel);border:1px solid var(--border);border-radius:24px;
  backdrop-filter:blur(18px);box-shadow:0 20px 70px rgba(0,0,0,.28);
}
.panel{padding:20px}.card{padding:15px}
.label{color:var(--muted);font-size:12px;text-transform:uppercase;letter-spacing:.09em}
.value{font-size:23px;font-weight:900;margin-top:7px;white-space:nowrap}
h2{margin:0 0 13px;font-size:18px}
input,select{
  width:100%;border:1px solid var(--border);background:rgba(0,0,0,.28);color:var(--text);
  border-radius:14px;padding:12px 13px;outline:none;
}
option{color:#111}
.formgrid{display:grid;grid-template-columns:1.4fr .8fr;gap:12px;margin-bottom:12px}
.three{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:12px}
button{
  border:0;background:linear-gradient(135deg,var(--accent),var(--cyan));color:white;
  padding:12px 16px;border-radius:14px;font-weight:800;cursor:pointer
}
button.stop{background:var(--bad)}
button.dark{background:var(--panel2);border:1px solid var(--border)}
button.good{background:var(--good)}
button:disabled{opacity:.45;cursor:not-allowed}
.actions{display:flex;flex-wrap:wrap;gap:10px;margin-top:10px}
.ok{color:var(--good);font-weight:900}.ko{color:var(--bad);font-weight:900}.warn{color:var(--warn);font-weight:900}
.mini{color:var(--muted);font-size:12px;line-height:1.45}
.pods{display:grid;grid-template-columns:repeat(auto-fit,minmax(350px,1fr));gap:16px}
.pod{padding:16px;position:relative;overflow:hidden}
.pod:before{content:"";position:absolute;inset:0;border-top:3px solid var(--cyan);opacity:.9}
.pod.removed{opacity:.48;filter:grayscale(.7)}
.pod.removed:before{border-top-color:var(--bad)}
.podHead{display:flex;justify-content:space-between;gap:10px;align-items:flex-start;margin-bottom:12px}
.podName{font-weight:900;word-break:break-all}
.dot{width:10px;height:10px;border-radius:50%;background:var(--good);display:inline-block;margin-right:7px}
.removed .dot{background:var(--bad)}
.kv{display:grid;grid-template-columns:135px 1fr;gap:7px;font-size:13px;margin:9px 0}
.k{color:var(--muted)}
.torIp{font-size:20px;font-weight:950}
.rotateFlash{animation:flash 1.2s ease-in-out}
@keyframes flash{0%{box-shadow:0 0 0 rgba(34,197,94,0)}40%{box-shadow:0 0 35px rgba(34,197,94,.65)}100%{box-shadow:0 0 0 rgba(34,197,94,0)}}
table{width:100%;border-collapse:collapse}
th,td{text-align:left;padding:10px 8px;border-bottom:1px solid rgba(255,255,255,.09);font-size:13px;vertical-align:top}
th{color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.08em}
.scroll{max-height:340px;overflow:auto;border:1px solid rgba(255,255,255,.08);border-radius:16px}
pre{background:rgba(0,0,0,.34);border:1px solid var(--border);border-radius:16px;padding:14px;overflow:auto;max-height:240px;color:#dbeafe}
.help{border-left:3px solid var(--cyan);padding-left:12px}
.statusBox{margin-top:10px;padding:12px;border-radius:14px;background:rgba(0,0,0,.24);border:1px solid var(--border)}
@media(max-width:1100px){.cards{grid-template-columns:repeat(2,1fr)}.main,.formgrid,.three{grid-template-columns:1fr}}
</style>
</head>
<body>
<div class="wrap">
  <div class="top">
    <div>
      <h1>DENED Control Center</h1>
      <div class="sub">Orchestration cluster, pods, IP Tor, rotation, bande passante et journal réseau.</div>
    </div>
    <div class="pill" id="statusPill">Chargement...</div>
  </div>

  <div class="grid cards">
    <div class="card"><div class="label">Pods</div><div class="value" id="podsCount">-</div></div>
    <div class="card"><div class="label">Ready</div><div class="value" id="readyCount">-</div></div>
    <div class="card"><div class="label">Retirés</div><div class="value" id="removedCount">-</div></div>
    <div class="card"><div class="label">Mémoire libre</div><div class="value" id="memFree">-</div></div>
    <div class="card"><div class="label">Mémoire utilisée</div><div class="value" id="memUsed">-</div></div>
    <div class="card"><div class="label">CPU</div><div class="value" id="cpuUsed">-</div></div>
    <div class="card"><div class="label">Download</div><div class="value" id="bwDown">-</div></div>
    <div class="card"><div class="label">Upload</div><div class="value" id="bwUp">-</div></div>
  </div>

  <div class="grid main">
    <div class="panel">
      <h2>1. Destination & comportement</h2>

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
        <div><div class="label">Pods souhaités</div><input id="replicas" type="number" min="1" max="50" value="1"></div>
      </div>

      <div class="three">
        <div><div class="label">RPS max / pod</div><input id="maxRps" type="number" min="1" max="20" value="5"></div>
        <div><div class="label">Workers / pod</div><input id="workers" type="number" min="1" max="8" value="2"></div>
        <div><div class="label">Méthode</div><select id="method"><option>GET</option><option>POST</option></select></div>
      </div>

      <div class="actions">
        <button class="good" onclick="scaleCluster()">Appliquer pods</button>
        <button onclick="startCluster()">Démarrer tous</button>
        <button class="stop" onclick="stopCluster()">Arrêter tous</button>
        <button class="dark" onclick="rotateAll()">Rotation Tor globale</button>
        <button class="dark" onclick="refresh()">Actualiser</button>
      </div>

      <div class="statusBox" id="actionStatus">Aucune action en cours.</div>
    </div>

    <div class="panel">
      <h2>2. Guide dynamique</h2>
      <div class="mini help" id="dynamicHelp"></div>
      <pre id="lastAction">Aucune action.</pre>
    </div>
  </div>

  <div class="panel" style="margin-top:16px;">
    <h2>3. Fenêtres pods</h2>
    <div class="pods" id="podCards"></div>
  </div>

  <div class="grid main" style="margin-top:16px;">
    <div class="panel">
      <h2>Journal agrégé des requêtes</h2>
      <div class="scroll">
        <table>
          <thead><tr><th>Heure</th><th>Pod</th><th>Pod IP</th><th>Destination</th><th>Proxy</th><th>Status</th><th>Temps</th></tr></thead>
          <tbody id="requestsBody"></tbody>
        </table>
      </div>
    </div>

    <div class="panel">
      <h2>Commandes de secours</h2>
      <pre id="commands"></pre>
    </div>
  </div>
</div>

<script>
let previousTorIps = {};
let knownPods = {};
let removedPods = {};
let busy = false;

async function api(path, options={}) {
  const r = await fetch(path, options);
  const txt = await r.text();
  try { return JSON.parse(txt); } catch(e) { return {ok:false, raw:txt}; }
}

function time(ts){ return ts ? new Date(ts*1000).toLocaleTimeString() : "-"; }
function safe(v){ return (v===undefined || v===null || v==="") ? "-" : v; }
function setStatus(msg, cls=''){ const el=document.getElementById('actionStatus'); el.className='statusBox '+cls; el.textContent=msg; }
function showAction(obj){ document.getElementById('lastAction').textContent = JSON.stringify(obj,null,2); }

function payload(){
  const mode = document.getElementById('mode').value;
  return {
    target_url: document.getElementById('targetUrl').value,
    mode,
    method: document.getElementById('method').value,
    request_interval_seconds: Number(document.getElementById('interval').value),
    duration_seconds: mode === 'extreme' ? null : Number(document.getElementById('duration').value),
    max_rps: Number(document.getElementById('maxRps').value),
    max_workers: Number(document.getElementById('workers').value)
  };
}

async function refresh(){
  const cluster = await api('/api/cluster');
  const currentPods = cluster.pods || [];
  const currentNames = new Set(currentPods.map(p => p.name));

  for(const p of currentPods){
    knownPods[p.name] = {...p, lastSeen: Date.now(), removed:false};
    delete removedPods[p.name];
  }

  for(const name of Object.keys(knownPods)){
    if(!currentNames.has(name) && !removedPods[name]){
      removedPods[name] = {...knownPods[name], removed:true, removedAt:Date.now()};
    }
  }

  for(const name of Object.keys(removedPods)){
    if(Date.now() - removedPods[name].removedAt > 60000){
      delete removedPods[name];
      delete knownPods[name];
    }
  }

  const displayedPods = [...currentPods, ...Object.values(removedPods)];

  const local = cluster.local || {};
  const sys = local.system || {};
  const bw = local.bandwidth || {};

  document.getElementById('podsCount').textContent = currentPods.length;
  document.getElementById('readyCount').textContent = currentPods.filter(p => p.ready === '2/2').length + '/' + currentPods.length;
  document.getElementById('removedCount').textContent = Object.keys(removedPods).length;
  document.getElementById('memFree').textContent = sys.memory_available_mb ? Math.round(sys.memory_available_mb) + ' MB' : '-';
  document.getElementById('memUsed').textContent = sys.memory_percent !== undefined ? sys.memory_percent + '%' : '-';
  document.getElementById('cpuUsed').textContent = sys.cpu_percent !== undefined ? sys.cpu_percent + '%' : '-';
  document.getElementById('bwDown').textContent = bw.recv_kbps !== undefined ? bw.recv_kbps + ' kb/s' : '-';
  document.getElementById('bwUp').textContent = bw.sent_kbps !== undefined ? bw.sent_kbps + ' kb/s' : '-';

  document.getElementById('statusPill').textContent = cluster.ok ? 'Cluster connecté' : 'Cluster partiel';
  document.getElementById('statusPill').style.color = cluster.ok ? '#22c55e' : '#f59e0b';

  renderPods(displayedPods);
  renderRequests(currentPods);
  renderHelp(currentPods);
  renderCommands();
}

function renderPods(pods){
  const box = document.getElementById('podCards');

  box.innerHTML = pods.map(p => {
    const rt = p.runtime || {};
    const tor = rt.tor || {};
    const torIp = p.removed ? 'pod retiré' : (tor.data?.IP || '-');
    const isTor = tor.data?.IsTor === true;
    const stats = rt.stats?.stats || {};
    const sys = rt.system || {};
    const bw = rt.bandwidth || {};
    const sch = rt.scheduler || {};
    const changed = previousTorIps[p.name] && previousTorIps[p.name] !== torIp && !p.removed;
    previousTorIps[p.name] = torIp;

    const disabled = p.removed || p.phase !== 'Running' ? 'disabled' : '';

    return `
      <div class="pod ${changed ? 'rotateFlash' : ''} ${p.removed ? 'removed' : ''}">
        <div class="podHead">
          <div>
            <div class="podName"><span class="dot"></span>${p.name}</div>
            <div class="mini">${p.removed ? 'Retiré du cluster' : (p.node || '-')}</div>
          </div>
          <div class="${p.removed ? 'ko' : (p.ready === '2/2' ? 'ok':'warn')}">${p.removed ? 'REMOVED' : (p.ready || '-')}</div>
        </div>

        <div class="kv"><div class="k">IP Kubernetes</div><div>${safe(p.pod_ip)}</div></div>
        <div class="kv"><div class="k">IP Tor visible</div><div class="torIp">${torIp}</div></div>
        <div class="kv"><div class="k">Tor</div><div class="${isTor ? 'ok':'ko'}">${p.removed ? 'arrêté' : (isTor ? 'IsTor=true' : 'non confirmé')}</div></div>
        <div class="kv"><div class="k">Mode</div><div>${sch.running ? '<span class="ok">ON</span> ' + sch.mode : '<span class="warn">OFF</span>'}</div></div>
        <div class="kv"><div class="k">Requêtes</div><div>${stats.total_requests || 0} total / ${stats.successful_requests || 0} succès / ${stats.failed_requests || 0} échecs</div></div>
        <div class="kv"><div class="k">CPU</div><div>${safe(sys.cpu_percent)}%</div></div>
        <div class="kv"><div class="k">Mémoire</div><div>${safe(sys.memory_percent)}%</div></div>
        <div class="kv"><div class="k">Download</div><div>${safe(bw.recv_kbps)} kb/s</div></div>
        <div class="kv"><div class="k">Upload</div><div>${safe(bw.sent_kbps)} kb/s</div></div>

        <div class="actions">
          <button class="dark" ${disabled} onclick="rotatePod('${encodeURIComponent(p.name)}')">Rotate ce pod</button>
          <button class="dark" ${disabled} onclick="startPod('${encodeURIComponent(p.name)}')">Start ce pod</button>
          <button class="stop" ${disabled} onclick="stopPod('${encodeURIComponent(p.name)}')">Stop ce pod</button>
        </div>
      </div>`;
  }).join('');
}

function renderRequests(pods){
  let rows = [];
  for(const p of pods){
    const reqs = p.runtime?.recent_requests || [];
    for(const r of reqs){ rows.push({...r, pod_fallback:p.name}); }
  }

  rows.sort((a,b)=>(b.timestamp||0)-(a.timestamp||0));
  rows = rows.slice(0,80);

  document.getElementById('requestsBody').innerHTML = rows.map(r => `
    <tr>
      <td>${time(r.timestamp)}</td>
      <td>${r.pod_name || r.pod_fallback || '-'}</td>
      <td>${r.pod_ip || '-'}</td>
      <td>${r.url || '-'}</td>
      <td>${r.proxy_used || '-'}</td>
      <td class="${r.ok ? 'ok':'ko'}">${r.status_code}</td>
      <td>${r.elapsed_seconds}s</td>
    </tr>
  `).join('');
}

function renderHelp(pods){
  const ready = pods.filter(p => p.ready === '2/2').length;
  const running = pods.filter(p => p.runtime?.scheduler?.running).length;
  const torOk = pods.filter(p => p.runtime?.tor?.data?.IsTor === true).length;

  document.getElementById('dynamicHelp').innerHTML = `
    <p><b>État :</b> ${ready}/${pods.length} pods prêts, ${torOk}/${pods.length} sorties Tor confirmées, ${running}/${pods.length} schedulers actifs.</p>
    <p><b>Pods retirés :</b> lorsqu’un pod disparaît après réduction du nombre de replicas, sa carte reste visible 60 secondes en gris.</p>
    <p><b>Boutons par pod :</b> Start, Stop et Rotate agissent uniquement sur le pod concerné.</p>
    <p><b>Bande passante :</b> Upload/Download sont calculés à partir des compteurs réseau du pod.</p>
  `;
}

function renderCommands(){
  const n = document.getElementById('replicas').value || 1;
  document.getElementById('commands').textContent =
`kubectl scale deployment dened --replicas=${n}
kubectl get pods -l app=dened -o wide
kubectl logs deployment/dened -c dened --tail=100
kubectl logs deployment/dened -c tor --tail=100
curl http://127.0.0.1:8080/api/cluster`;
}

async function withAction(label, fn){
  if(busy) return;
  busy = true;
  setStatus(label + '...', 'warn');
  try{
    const res = await fn();
    showAction(res);
    setStatus(res.ok === false ? 'Action terminée avec erreur.' : 'Action exécutée.', res.ok === false ? 'ko' : 'ok');
    await refresh();
  }catch(e){
    const err = {ok:false,error:String(e)};
    showAction(err);
    setStatus('Erreur action : ' + e, 'ko');
  }finally{
    busy = false;
  }
}

async function scaleCluster(){
  await withAction('Scaling des pods', async () => {
    return await api('/api/scale', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body:JSON.stringify({replicas:Number(document.getElementById('replicas').value)})
    });
  });
  setTimeout(refresh, 3000);
}

async function startCluster(){
  await withAction('Démarrage cluster', async () => {
    return await api('/api/cluster/start', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body:JSON.stringify(payload())
    });
  });
}

async function stopCluster(){
  await withAction('Arrêt cluster', async () => {
    return await api('/api/cluster/stop', {method:'POST'});
  });
}

async function rotateAll(){
  await withAction('Rotation Tor globale', async () => {
    return await api('/api/cluster/tor/new-identity', {method:'POST'});
  });
  setTimeout(refresh, 12000);
}

async function rotatePod(name){
  await withAction('Rotation Tor du pod', async () => {
    return await api(`/api/pod/${name}/tor/new-identity`, {method:'POST'});
  });
  setTimeout(refresh, 12000);
}

async function startPod(name){
  await withAction('Démarrage du pod', async () => {
    return await api(`/api/pod/${name}/start`, {
      method:'POST', headers:{'Content-Type':'application/json'},
      body:JSON.stringify(payload())
    });
  });
}

async function stopPod(name){
  await withAction('Arrêt du pod', async () => {
    return await api(`/api/pod/${name}/stop`, {method:'POST'});
  });
}

refresh();
setInterval(refresh, 3000);
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
            max_rps = min(max(1, int(payload.get("max_rps", mode_cfg.get("max_rps", 1)))), 20)
            max_workers = min(max(1, int(payload.get("max_workers", mode_cfg.get("max_workers", 1)))), 8)
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

        self._last_net_sample = None

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
                headers={"User-Agent": "dened/4.0"},
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

    def k8s_context(self) -> Optional[Dict]:
        token_path = "/var/run/secrets/kubernetes.io/serviceaccount/token"
        ns_path = "/var/run/secrets/kubernetes.io/serviceaccount/namespace"
        ca_path = "/var/run/secrets/kubernetes.io/serviceaccount/ca.crt"
        if not os.path.exists(token_path):
            return None
        return {
            "token": open(token_path, "r", encoding="utf-8").read().strip(),
            "namespace": open(ns_path, "r", encoding="utf-8").read().strip(),
            "ca": ca_path,
            "base": "https://kubernetes.default.svc",
        }

    def k8s_headers(self, ctx: Dict) -> Dict:
        return {"Authorization": f"Bearer {ctx['token']}"}

    def get_kubernetes_pods(self) -> Dict:
        ctx = self.k8s_context()
        if not ctx:
            return {"ok": True, "source": "local", "pods": [{
                "name": self.pod_name, "pod_ip": self.pod_ip, "node": "-", "phase": "local", "ready": "unknown"
            }]}

        try:
            url = f"{ctx['base']}/api/v1/namespaces/{ctx['namespace']}/pods?labelSelector=app%3Ddened"
            response = requests.get(url, headers=self.k8s_headers(ctx), verify=ctx["ca"], timeout=5)
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

    def call_pod(self, pod_name: str, path: str, method: str = "GET", payload: Optional[Dict] = None) -> Dict:
        pods = self.get_kubernetes_pods().get("pods", [])
        target = next((p for p in pods if p.get("name") == pod_name), None)
        if not target or not target.get("pod_ip"):
            return {"ok": False, "error": f"Pod introuvable ou sans IP: {pod_name}"}

        url = f"http://{target['pod_ip']}:8080{path}"
        try:
            if method == "POST":
                r = requests.post(url, json=payload or {}, timeout=12)
            else:
                r = requests.get(url, timeout=12)

            try:
                body = r.json()
            except Exception:
                body = {"raw": r.text[:500]}

            return {
                "ok": r.ok,
                "status_code": r.status_code,
                "pod": pod_name,
                "pod_ip": target.get("pod_ip"),
                "path": path,
                "response": body,
            }

        except Exception as exc:
            return {
                "ok": False,
                "pod": pod_name,
                "pod_ip": target.get("pod_ip"),
                "path": path,
                "error": str(exc),
            }

    def bandwidth_snapshot(self, system: Dict) -> Dict:
        now = time.time()
        current = {
            "timestamp": now,
            "bytes_sent": system.get("bytes_sent", 0),
            "bytes_recv": system.get("bytes_recv", 0),
        }

        if not self._last_net_sample:
            self._last_net_sample = current
            return {
                "sent_kbps": 0,
                "recv_kbps": 0,
                "sent_mbps": 0,
                "recv_mbps": 0,
                "bytes_sent": current["bytes_sent"],
                "bytes_recv": current["bytes_recv"],
            }

        elapsed = max(now - self._last_net_sample["timestamp"], 0.001)
        sent_delta = max(current["bytes_sent"] - self._last_net_sample["bytes_sent"], 0)
        recv_delta = max(current["bytes_recv"] - self._last_net_sample["bytes_recv"], 0)

        self._last_net_sample = current

        sent_kbps = (sent_delta * 8 / 1000) / elapsed
        recv_kbps = (recv_delta * 8 / 1000) / elapsed

        return {
            "sent_kbps": round(sent_kbps, 2),
            "recv_kbps": round(recv_kbps, 2),
            "sent_mbps": round(sent_kbps / 1000, 4),
            "recv_mbps": round(recv_kbps / 1000, 4),
            "bytes_sent": current["bytes_sent"],
            "bytes_recv": current["bytes_recv"],
        }

    def runtime_payload(self, include_tor: bool = True) -> Dict:
        proxy_status = self.proxy_manager.status()
        system = self.hardware.get_system_stats()
        bandwidth = self.bandwidth_snapshot(system)
        tor = self.tor_manager.check_tor_ip(timeout=8) if include_tor else {"ok": None, "skipped": True}

        PROXIES_AVAILABLE.set(proxy_status["available"])
        SYSTEM_MEMORY_PERCENT.set(system["memory_percent"])
        SYSTEM_CPU_PERCENT.set(system["cpu_percent"])

        return {
            "scheduler": self.scheduler.snapshot(),
            "stats": self.stats.snapshot(),
            "proxies": proxy_status,
            "system": system,
            "bandwidth": bandwidth,
            "tor": tor,
            "pod": {"name": self.pod_name, "ip": self.pod_ip},
            "recent_requests": list(self.recent_requests),
            "config_file": self.config_path,
        }

    def cluster_payload(self) -> Dict:
        pods_info = self.get_kubernetes_pods()
        pods = pods_info.get("pods", [])
        enriched = []

        for p in pods:
            if p.get("phase") != "Running" or not p.get("pod_ip"):
                enriched.append({**p, "runtime": None, "runtime_ok": False})
                continue

            try:
                r = requests.get(f"http://{p['pod_ip']}:8080/api/node-runtime", timeout=10)
                runtime = r.json()
                enriched.append({**p, "runtime": runtime, "runtime_ok": r.ok})
            except Exception as exc:
                enriched.append({**p, "runtime": {"error": str(exc)}, "runtime_ok": False})

        return {
            "ok": pods_info.get("ok", False),
            "source": pods_info.get("source"),
            "pods": enriched,
            "local": self.runtime_payload(include_tor=False),
        }

    def scale_deployment(self, replicas: int) -> Dict:
        replicas = max(1, min(int(replicas), 50))
        ctx = self.k8s_context()
        if not ctx:
            return {"ok": False, "error": "API Kubernetes indisponible hors cluster"}

        try:
            url = f"{ctx['base']}/apis/apps/v1/namespaces/{ctx['namespace']}/deployments/dened/scale"
            payload = {"spec": {"replicas": replicas}}
            r = requests.patch(
                url,
                headers={**self.k8s_headers(ctx), "Content-Type": "application/merge-patch+json"},
                verify=ctx["ca"],
                data=json.dumps(payload),
                timeout=8,
            )
            return {"ok": r.ok, "status_code": r.status_code, "replicas": replicas, "response": r.json()}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def broadcast(self, path: str, method: str = "POST", payload: Optional[Dict] = None) -> Dict:
        pods = self.get_kubernetes_pods().get("pods", [])
        results = []
        for p in pods:
            if p.get("phase") == "Running" and p.get("pod_ip"):
                results.append(self.call_pod(p["name"], path, method=method, payload=payload))
        return {"ok": True, "count": len(results), "results": results}

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

        @self.app.get("/api/node-runtime")
        def api_node_runtime():
            return jsonify(self.runtime_payload())

        @self.app.get("/api/cluster")
        def api_cluster():
            return jsonify(self.cluster_payload())

        @self.app.get("/api/pods")
        def api_pods():
            return jsonify(self.get_kubernetes_pods())

        @self.app.post("/api/scale")
        def api_scale():
            payload = request.get_json(silent=True) or {}
            return jsonify(self.scale_deployment(payload.get("replicas", 1)))

        @self.app.post("/api/start")
        def api_start():
            result = self.scheduler.start(request.get_json(silent=True) or {})
            return jsonify(result), 200 if result.get("ok") else 400

        @self.app.post("/api/stop")
        def api_stop():
            return jsonify(self.scheduler.stop())

        @self.app.post("/api/cluster/start")
        def api_cluster_start():
            return jsonify(self.broadcast("/api/start", method="POST", payload=request.get_json(silent=True) or {}))

        @self.app.post("/api/cluster/stop")
        def api_cluster_stop():
            return jsonify(self.broadcast("/api/stop", method="POST"))

        @self.app.post("/api/cluster/tor/new-identity")
        def api_cluster_tor_new():
            return jsonify(self.broadcast("/tor/new-identity", method="POST"))

        @self.app.post("/api/pod/<pod_name>/tor/new-identity")
        def api_pod_tor_new(pod_name):
            return jsonify(self.call_pod(pod_name, "/tor/new-identity", method="POST"))

        @self.app.post("/api/pod/<pod_name>/start")
        def api_pod_start(pod_name):
            return jsonify(self.call_pod(pod_name, "/api/start", method="POST", payload=request.get_json(silent=True) or {}))

        @self.app.post("/api/pod/<pod_name>/stop")
        def api_pod_stop(pod_name):
            return jsonify(self.call_pod(pod_name, "/api/stop", method="POST"))

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
            self.runtime_payload(include_tor=False)
            return generate_latest(), 200, {"Content-Type": CONTENT_TYPE_LATEST}

    def run(self) -> None:
        server_cfg = self.config.get("server", {})
        self.app.run(
            host=server_cfg.get("host", "0.0.0.0"),
            port=int(os.getenv("PORT", server_cfg.get("port", 8080))),
            threaded=True,
        )


def create_app():
    return DenedApp(os.getenv("CONFIG_FILE", "config.yaml")).app


if __name__ == "__main__":
    DenedApp(os.getenv("CONFIG_FILE", "config.yaml")).run()
