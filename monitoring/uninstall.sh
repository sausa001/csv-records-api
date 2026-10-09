#!/usr/bin/env bash
# Removes Prometheus + Grafana. Not required before terraform destroy (nothing in AWS
# depends on it), but frees the nodes if you only want to switch monitoring off.
set -euo pipefail
helm -n monitoring uninstall kps || true
kubectl delete namespace monitoring --ignore-not-found
