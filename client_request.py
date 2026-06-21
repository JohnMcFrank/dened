import requests
import time
import threading
from typing import Dict, List

class RequestSender:
    def __init__(self, service_url: str = "http://ip-rotator-service:8080"):
        self.service_url = service_url
        
    def get_proxy(self) -> str:
        """Obtenir un proxy via l'API"""
        try:
            response = requests.get(f"{self.service_url}/proxy")
            if response.status_code == 200:
                return response.json().get('proxy')
            return None
        except Exception as e:
            print(f"Erreur lors de la récupération du proxy: {e}")
            return None
            
    def send_request(self, target_url: str, proxy: str = None) -> Dict:
        """Envoyer une requête HTTP"""
        try:
            headers = {}
            if proxy:
                proxies = {
                    "http": f"http://{proxy}",
                    "https": f"http://{proxy}"
                }
            else:
                proxies = None
                
            response = requests.get(
                target_url,
                proxies=proxies,
                timeout=10
            )
            
            return {
                "status": "success",
                "url": target_url,
                "proxy_used": proxy,
                "status_code": response.status_code,
                "response_time": response.elapsed.total_seconds(),
                "content_length": len(response.content)
            }
            
        except Exception as e:
            return {
                "status": "failed",
                "url": target_url,
                "proxy_used": proxy,
                "error": str(e)
            }
            
    def send_multiple_requests(self, target_url: str, count: int = 10):
        """Envoyer plusieurs requêtes"""
        results = []
        
        for i in range(count):
            # Obtenir un proxy
            proxy = self.get_proxy()
            
            if not proxy:
                print("Aucun proxy disponible")
                break
                
            # Envoyer la requête
            result = self.send_request(target_url, proxy)
            results.append(result)
            
            print(f"Requête {i+1}: {result['status']} - Code: {result.get('status_code', 'N/A')}")
            
            # Pause entre les requêtes
            time.sleep(0.5)
            
        return results

# Utilisation
if __name__ == "__main__":
    sender = RequestSender()
    
    # Envoyer des requêtes vers votre cible
    target_url = "https://httpbin.org/get"  # Remplacez par votre cible
    
    print("Envoi de requêtes...")
    results = sender.send_multiple_requests(target_url, 5)
    
    # Afficher les résultats
    success_count = sum(1 for r in results if r['status'] == 'success')
    print(f"\nRésultats: {success_count}/{len(results)} réussies")
