#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-basic}"
DEPLOYMENT="${DEPLOYMENT:-dened}"
POD_MEMORY_MI="${POD_MEMORY_MI:-512}"

case "$MODE" in
  basic)
    TARGET_PERCENT=25
    ;;
  fast)
    TARGET_PERCENT=50
    ;;
  extreme)
    TARGET_PERCENT=80
    ;;
  *)
    echo "Mode invalide: $MODE"
    echo "Modes disponibles: basic, fast, extreme"
    exit 1
    ;;
esac

TOTAL_MEMORY_KB="$(grep MemTotal /proc/meminfo | awk '{print $2}')"
TOTAL_MEMORY_MI="$((TOTAL_MEMORY_KB / 1024))"
TARGET_MEMORY_MI="$((TOTAL_MEMORY_MI * TARGET_PERCENT / 100))"
REPLICAS="$((TARGET_MEMORY_MI / POD_MEMORY_MI))"

if [ "$REPLICAS" -lt 1 ]; then
  REPLICAS=1
fi

echo "Mode: $MODE"
echo "Mémoire totale détectée: ${TOTAL_MEMORY_MI}Mi"
echo "Cible mémoire: ${TARGET_PERCENT}% = ${TARGET_MEMORY_MI}Mi"
echo "Limite mémoire par pod: ${POD_MEMORY_MI}Mi"
echo "Nombre de pods calculé: ${REPLICAS}"

kubectl scale deployment "$DEPLOYMENT" --replicas="$REPLICAS"
kubectl rollout status deployment/"$DEPLOYMENT"
kubectl get pods -l app=dened
