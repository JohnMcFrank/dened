import time
from typing import Dict

import psutil


class HardwareMonitor:
    def get_system_stats(self) -> Dict:
        memory = psutil.virtual_memory()
        cpu = psutil.cpu_percent(interval=None)
        net = psutil.net_io_counters()

        return {
            "cpu_percent": cpu,
            "cpu_count": psutil.cpu_count(),
            "memory_percent": memory.percent,
            "memory_available_mb": round(memory.available / 1024 / 1024, 2),
            "memory_total_mb": round(memory.total / 1024 / 1024, 2),
            "bytes_sent": net.bytes_sent,
            "bytes_recv": net.bytes_recv,
            "timestamp": time.time(),
        }

    def limits_ok(self, max_memory_percent: float, max_cpu_percent: float) -> Dict:
        stats = self.get_system_stats()

        return {
            "ok": stats["memory_percent"] <= max_memory_percent and stats["cpu_percent"] <= max_cpu_percent,
            "memory_ok": stats["memory_percent"] <= max_memory_percent,
            "cpu_ok": stats["cpu_percent"] <= max_cpu_percent,
            "stats": stats,
        }
