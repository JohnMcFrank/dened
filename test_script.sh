#!/bin/bash

echo "=== Test de l'outil IP Rotator ==="

# Obtenir un proxy
PROXY=$(curl -s http://ip-rotator-service:8080/proxy | jq -r '.proxy')
echo "Proxy obtenu: $PROXY"

if [ ! -z "$PROXY" ]; then
    echo "Envoi d'une requête de test..."
    
    # Envoyer une requête vers la cible
    RESPONSE=$(curl -s -w "%{http_code}" \
        --proxy http://$PROXY \
        https://httpbin.org/get \
        -o /tmp/response.json)
        
    echo "Code HTTP: $RESPONSE"
    
    # Afficher le contenu de la réponse
    cat /tmp/response.json | head -20
    
else
    echo "Erreur: Aucun proxy disponible"
fi

echo "=== Test terminé ==="
