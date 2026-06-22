import threading
import time
from collections import defaultdict
from typing import Dict, Optional


class StatsManager:
    def __init__(self):
        self._lock = threading.Lock()
        self._start = time.time()
        self._stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "direct_requests": 0,
            "proxied_requests": 0,
            "requests_per_second": 0.0,
            "last_error": None,
        }
        self._proxy_usage = defaultdict(int)

    def record_request(self, success: bool, proxy: Optional[str] = None, error: Optional[str] = None) -> None:
        with self._lock:
            self._stats["total_requests"] += 1

            if success:
                self._stats["successful_requests"] += 1
            else:
                self._stats["failed_requests"] += 1
                self._stats["last_error"] = error

            if proxy:
                self._stats["proxied_requests"] += 1
                self._proxy_usage[proxy] += 1
            else:
                self._stats["direct_requests"] += 1

            elapsed = max(time.time() - self._start, 0.001)
            self._stats["requests_per_second"] = self._stats["total_requests"] / elapsed

    def snapshot(self) -> Dict:
        with self._lock:
            return {
                "stats": dict(self._stats),
                "proxy_usage": dict(self._proxy_usage),
                "uptime_seconds": round(time.time() - self._start, 2),
                "timestamp": time.time(),
            }
