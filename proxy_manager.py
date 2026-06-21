import random

class ProxyManager:
    def __init__(self):
        self.proxies = []

    def get_proxy(self):
        ip = f"10.{random.randint(0, 255)}.{random.randint(0, 255)}.{random.randint(0, 255)}"
        return f"http://{ip}:8080"

# Exemple d'utilisation
pm = ProxyManager()
print(pm.get_proxy())
