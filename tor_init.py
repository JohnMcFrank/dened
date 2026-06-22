import socket
import time
from typing import Dict, Optional

import requests


class TORManager:
    def __init__(
        self,
        socks_host: str = "127.0.0.1",
        socks_port: int = 9050,
        control_host: str = "127.0.0.1",
        control_port: int = 9051,
        cooldown_seconds: int = 10,
    ):
        self.socks_host = socks_host
        self.socks_port = socks_port
        self.control_host = control_host
        self.control_port = control_port
        self.cooldown_seconds = cooldown_seconds
        self.last_newnym_at = 0.0

    @property
    def proxy_url(self) -> str:
        return f"socks5h://{self.socks_host}:{self.socks_port}"

    def proxies(self) -> Dict[str, str]:
        return {
            "http": self.proxy_url,
            "https": self.proxy_url,
        }

    def _send_control_command(self, command: str) -> str:
        with socket.create_connection((self.control_host, self.control_port), timeout=5) as sock:
            file = sock.makefile("rwb", buffering=0)

            file.write(b'AUTHENTICATE\r\n')
            auth_response = file.readline().decode("utf-8", errors="replace").strip()

            if not auth_response.startswith("250"):
                raise RuntimeError(f"Tor ControlPort auth failed: {auth_response}")

            file.write(command.encode("utf-8") + b"\r\n")
            command_response = file.readline().decode("utf-8", errors="replace").strip()

            if not command_response.startswith("250"):
                raise RuntimeError(f"Tor ControlPort command failed: {command_response}")

            return command_response

    def request_new_identity(self) -> Dict:
        now = time.time()
        remaining = self.cooldown_seconds - (now - self.last_newnym_at)

        if remaining > 0:
            return {
                "ok": False,
                "skipped": True,
                "reason": "cooldown",
                "retry_after_seconds": round(remaining, 2),
            }

        try:
            response = self._send_control_command("SIGNAL NEWNYM")
            self.last_newnym_at = time.time()

            return {
                "ok": True,
                "message": "Tor NEWNYM signal sent",
                "control_response": response,
            }

        except Exception as exc:
            return {
                "ok": False,
                "error": str(exc),
            }

    def check_tor_ip(self, timeout: int = 15) -> Dict:
        try:
            response = requests.get(
                "https://check.torproject.org/api/ip",
                proxies=self.proxies(),
                timeout=timeout,
            )

            return {
                "ok": response.ok,
                "status_code": response.status_code,
                "data": response.json(),
            }

        except Exception as exc:
            return {
                "ok": False,
                "error": str(exc),
            }


class RequestHandler:
    def __init__(self):
        self.tor_manager = TORManager()

    def send_request_with_tor(self, url: str, timeout: int = 30) -> Optional[str]:
        try:
            response = requests.get(
                url,
                proxies=self.tor_manager.proxies(),
                timeout=timeout,
            )

            if response.status_code >= 500:
                self.tor_manager.request_new_identity()

            return response.text

        except Exception:
            self.tor_manager.request_new_identity()
            return None


if __name__ == "__main__":
    tor = TORManager()
    print(tor.check_tor_ip())
    print(tor.request_new_identity())
