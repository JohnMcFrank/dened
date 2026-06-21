#!/usr/bin/env bash
set +e

OUT="diag-k8s-iprotator-$(date +%Y%m%d-%H%M%S).log"

{
echo "===== DATE ====="
date

echo
echo "===== SYSTEM ====="
hostname
whoami
pwd
lsb_release -a 2>/dev/null || cat /etc/os-release
uname -a
free -h
df -h

echo
echo "===== PROJECT TREE ====="
find . -maxdepth 3 -type f | sort

echo
echo "===== KUBECTL CONFIG ====="
kubectl version --client=true
kubectl config current-context
kubectl config get-contexts
ls -la ~/.kube || true
ls -la ~/.kube/config || true

echo
echo "===== CLUSTER ====="
kubectl cluster-info
kubectl get nodes -o wide
kubectl describe nodes

echo
echo "===== ALL PODS ====="
kubectl get pods -A -o wide

echo
echo "===== ALL SERVICES ====="
kubectl get svc -A -o wide

echo
echo "===== CONFIGMAPS ====="
kubectl get configmaps -A

echo
echo "===== EVENTS SORTED ====="
kubectl get events -A --sort-by=.lastTimestamp

echo
echo "===== CURRENT NAMESPACE RESOURCES ====="
kubectl get all -o wide
kubectl get configmaps -o yaml
kubectl get deployments -o yaml
kubectl get services -o yaml

echo
echo "===== DESCRIBE IP ROTATOR PODS ====="
for p in $(kubectl get pods -o name 2>/dev/null | grep ip-rotator); do
  echo
  echo "--- $p ---"
  kubectl describe "$p"
done

echo
echo "===== IP ROTATOR POD LOGS ====="
for p in $(kubectl get pods -o name 2>/dev/null | grep ip-rotator); do
  echo
  echo "--- logs $p ---"
  kubectl logs "$p" --all-containers=true --tail=200
done

echo
echo "===== KUBE SYSTEM PODS ====="
kubectl get pods -n kube-system -o wide
kubectl get pods -n kube-flannel -o wide 2>/dev/null || true

echo
echo "===== CONTAINERD ====="
systemctl status containerd --no-pager -l
sudo journalctl -u containerd --no-pager -n 100

echo
echo "===== KUBELET ====="
systemctl status kubelet --no-pager -l
sudo journalctl -u kubelet --no-pager -n 150

echo
echo "===== DOCKER ====="
docker version 2>/dev/null || true
docker ps -a 2>/dev/null || true
docker images 2>/dev/null || true

echo
echo "===== CONTAINERD IMAGES ====="
sudo crictl images 2>/dev/null || true
sudo ctr -n k8s.io images list 2>/dev/null || true

echo
echo "===== K8S YAML FILES ====="
for f in k8s/*.yaml k8s/*.yml; do
  [ -f "$f" ] || continue
  echo
  echo "----- FILE: $f -----"
  sed -n '1,240p' "$f"
done

} > "$OUT" 2>&1

echo "Diagnostic créé : $OUT"
echo
echo "Envoie-moi le contenu avec :"
echo "cat $OUT"
