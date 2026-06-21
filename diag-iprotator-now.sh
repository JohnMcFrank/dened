#!/usr/bin/env bash
set +e

OUT="diag-iprotator-now-$(date +%Y%m%d-%H%M%S).log"

{
echo "===== DATE ====="
date

echo
echo "===== NODES ====="
kubectl get nodes -o wide

echo
echo "===== DEPLOYMENT SUMMARY ====="
kubectl get deployment ip-rotator-tool -o wide
kubectl describe deployment ip-rotator-tool

echo
echo "===== CONTAINERS / IMAGES ====="
kubectl get deployment ip-rotator-tool -o jsonpath='{range .spec.template.spec.containers[*]}{.name}{" -> "}{.image}{" / "}{.imagePullPolicy}{" / command="}{.command}{" / args="}{.args}{"\n"}{end}'
echo

echo
echo "===== REPLICASETS ====="
kubectl get rs -o wide
kubectl describe rs -l app=ip-rotator-tool

echo
echo "===== PODS ====="
kubectl get pods -o wide
kubectl get pods -l app=ip-rotator-tool -o jsonpath='{range .items[*]}{"POD: "}{.metadata.name}{"\n"}{range .spec.containers[*]}{"  "}{.name}{" -> "}{.image}{" / "}{.imagePullPolicy}{"\n"}{end}{"\n"}{end}'

echo
echo "===== DESCRIBE PODS ====="
for p in $(kubectl get pods -l app=ip-rotator-tool -o name); do
  echo
  echo "----- $p -----"
  kubectl describe "$p"
done

echo
echo "===== LOGS CURRENT ====="
for p in $(kubectl get pods -l app=ip-rotator-tool -o name); do
  echo
  echo "----- $p / all containers -----"
  kubectl logs "$p" --all-containers=true --tail=120
done

echo
echo "===== LOGS PREVIOUS ====="
for p in $(kubectl get pods -l app=ip-rotator-tool -o name); do
  echo
  echo "----- $p / previous all containers -----"
  kubectl logs "$p" --all-containers=true --previous --tail=120
done

echo
echo "===== SERVICE ====="
kubectl get svc ip-rotator-service -o wide
kubectl describe svc ip-rotator-service

echo
echo "===== ENDPOINTS ====="
kubectl get endpoints ip-rotator-service -o wide
kubectl get endpointslices -o wide

echo
echo "===== RECENT EVENTS ====="
kubectl get events --sort-by=.lastTimestamp | tail -80

echo
echo "===== LOCAL IMAGES ====="
sudo ctr -n k8s.io images list | grep -E 'ip-rotator|python' || true
docker images | grep -E 'ip-rotator|python' || true

echo
echo "===== YAML DEPLOYMENT FILE ====="
sed -n '1,260p' k8s/deployment.yaml

} > "$OUT" 2>&1

echo "Diagnostic créé : $OUT"
echo "Envoie-moi :"
echo "cat $OUT"
