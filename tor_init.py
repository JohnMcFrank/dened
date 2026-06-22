import asyncio
import aiohttp
import random
import subprocess
import time
from typing import Optional

class TORManager:
    def __init__(self):
        self.circuit_id = None
        
    async def restart_tor_circuit(self) -> bool:
        """Redémarre le circuit Tor en utilisant le service de redémarrage"""
        try:
            # Exemple d'appel au service de redémarrage
            result = subprocess.run(['tor', 'restart'], capture_output=True, text=True)
            
            if result.returncode == 0:
                print("Circuit Tor redémarré avec succès")
                return True
            else:
                print(f"Erreur lors du redémarrage : {result.stderr}")
                return False
                
        except Exception as e:
            print(f"Exception lors du redémarrage du circuit : {e}")
            return False

class RequestHandler:
    def __init__(self):
        self.tor_manager = TORManager()
        
    async def send_request_with_tor(self, url: str) -> Optional[str]:
        """Envoie une requête HTTP via Tor avec gestion des réponses négatives"""
        try:
            # Configuration de la session avec proxy Tor
            timeout = aiohttp.ClientTimeout(total=30)
            
            async with aiohttp.ClientSession(timeout=timeout) as session:
                # Envoi de la requête
                async with session.get(url, proxy="socks5://127.0.0.1:9050") as response:
                    content = await response.text()
                    
                    # Vérification de la réponse négative (exemples)
                    if response.status >= 400 or "error" in content.lower():
                        print(f"Réponse négative détectée : {response.status}")
                        
                        # Redémarrage du circuit Tor
                        await self.tor_manager.restart_tor_circuit()
                        
                        # Retenter la requête après redémarrage
                        time.sleep(2)  # Pause avant de retenter
                        
                        async with session.get(url, proxy="socks5://127.0.0.1:9050") as retry_response:
                            return await retry_response.text()
                    
                    return content
                    
        except Exception as e:
            print(f"Erreur lors de la requête : {e}")
            
            # En cas d'erreur réseau, redémarrer le circuit
            await self.tor_manager.restart_tor_circuit()
            time.sleep(2)
            
            try:
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
                    async with session.get(url, proxy="socks5://127.0.0.1:9050") as retry_response:
                        return await retry_response.text()
            except Exception as retry_e:
                print(f"Erreur de reprise : {retry_e}")
                return None

# Exemple d'utilisation
async def main():
    handler = RequestHandler()
    
    # Liste des URLs à tester
    urls = [
        "https://httpbin.org/ip",
        "https://www.google.com"
    ]
    
    for url in urls:
        print(f"Envoi de requête vers {url}")
        content = await handler.send_request_with_tor(url)
        
        if content:
            print("Réponse reçue avec succès")
        else:
            print("Échec de la requête")

# Exécution principale
if __name__ == "__main__":
    asyncio.run(main())
