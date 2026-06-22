import random
import threading
from pathlib import Path
from typing import Dict, List, Optional


class ProxyManager:
    def __init__(self, proxies: Optional[List[str]] = None, rotation_mode: str = "round_robin"):
        self._proxies: List[str] = []
        self._failed: set[str] = set()
        self._index = 0
        self._lock = threading.Lock()
        self.rotation_mode = rotation_mode if rotation_mode in {"round_robin", "random"} else "round_robin"

        for proxy in proxies or []:
            self.add_proxy(proxy)

    @staticmethod
    def normalize(proxy: str) -> Optional[str]:
        proxy = (proxy or "").strip()
        if not proxy or proxy.startswith("#"):
            return None
        if proxy.startswith("http://") or proxy.startswith("https://"):
            return proxy
        return f"http://{proxy}"

    def load_from_file(self, path: str) -> int:
        file_path = Path(path)
        if not file_path.exists():
            return 0

        count = 0
        for line in file_path.read_text(encoding="utf-8").splitlines():
            before = len(self._proxies)
            self.add_proxy(line)
            if len(self._proxies) > before:
                count += 1
        return count

    def add_proxy(self, proxy: str) -> bool:
        normalized = self.normalize(proxy)
        if not normalized:
            return False

        with self._lock:
            if normalized not in self._proxies:
                self._proxies.append(normalized)
                return True
        return False

    def get_proxy(self) -> Optional[str]:
        with self._lock:
            available = [p for p in self._proxies if p not in self._failed]
            if not available:
                return None

            if self.rotation_mode == "random":
                return random.choice(available)

            proxy = available[self._index % len(available)]
            self._index = (self._index + 1) % len(available)
            return proxy

    def mark_failed(self, proxy: Optional[str]) -> None:
        if proxy:
            with self._lock:
                self._failed.add(proxy)

    def mark_working(self, proxy: Optional[str]) -> None:
        if proxy:
            with self._lock:
                self._failed.discard(proxy)

    def status(self) -> Dict:
        with self._lock:
            return {
                "total": len(self._proxies),
                "available": len([p for p in self._proxies if p not in self._failed]),
                "failed": len(self._failed),
                "rotation_mode": self.rotation_mode,
                "proxies": [
                    {
                        "proxy": p,
                        "status": "failed" if p in self._failed else "available"
                    }
                    for p in self._proxies
                ],
            }
