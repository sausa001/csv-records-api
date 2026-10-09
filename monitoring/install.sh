#!/usr/bin/env bash
# Installs Prometheus + Grafana (kube-prometheus-stack) and the PeoplePulse dashboard
# into namespace "monitoring" of the cluster kubectl currently points at.
# Run after: terraform apply (envs/dev) and aws eks update-kubeconfig.
set -euo pipefail
cd "$(dirname "$0")"
NS=monitoring
RELEASE=kps

CTX=$(kubectl config current-context)
if [[ "$CTX" != *peoplepulse-dev* && "${SKIP_CONTEXT_CHECK:-}" != "1" ]]; then
  echo "kubectl points at '$CTX', not the EKS cluster peoplepulse-dev."
  echo "Run: aws eks update-kubeconfig --name peoplepulse-dev --region us-west-1"
  exit 1
fi

helm repo add prometheus-community https://prometheus-community.github.io/helm-charts >/dev/null 2>&1 || true
helm repo update prometheus-community

kubectl create namespace "$NS" --dry-run=client -o yaml | kubectl apply -f -

# Grafana admin password: generated once per cluster, stored only in a Kubernetes Secret
if ! kubectl -n "$NS" get secret grafana-admin >/dev/null 2>&1; then
  PASS=$(LC_ALL=C tr -dc 'A-Za-z0-9' </dev/urandom | head -c 20)
  kubectl -n "$NS" create secret generic grafana-admin \
    --from-literal=admin-user=admin --from-literal=admin-password="$PASS"
fi

# Dashboard as a ConfigMap; Grafana's sidecar loads every ConfigMap labelled grafana_dashboard=1
kubectl -n "$NS" create configmap peoplepulse-dashboard \
  --from-file=peoplepulse.json=dashboards/peoplepulse.json --dry-run=client -o yaml \
  | kubectl label --local -f - grafana_dashboard=1 -o yaml \
  | kubectl apply -f -

helm upgrade --install "$RELEASE" prometheus-community/kube-prometheus-stack \
  --namespace "$NS" -f kube-prometheus-stack-values.yaml --wait --timeout 10m

kubectl -n "$NS" get pods
cat <<MSG

Prometheus and Grafana are running.
  Grafana:     kubectl -n $NS port-forward svc/$RELEASE-grafana 3001:80      -> http://localhost:3001
  Prometheus:  kubectl -n $NS port-forward svc/$RELEASE-prometheus 9090:9090 -> http://localhost:9090
  Login:       user admin, password:
               kubectl -n $NS get secret grafana-admin -o jsonpath='{.data.admin-password}' | base64 -d; echo
  Dashboard:   Dashboards -> PeoplePulse
MSG
