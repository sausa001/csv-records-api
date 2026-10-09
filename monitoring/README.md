# Monitoring: Prometheus + Grafana on EKS

`install.sh` installs kube-prometheus-stack into namespace `monitoring` and loads the
PeoplePulse dashboard. Run it once after each `terraform apply` of `envs/dev`:

```bash
aws eks update-kubeconfig --name peoplepulse-dev --region us-west-1
./monitoring/install.sh
kubectl -n monitoring port-forward svc/kps-grafana 3001:80     # http://localhost:3001
```

What is scraped
- Nodes, pods and Kubernetes objects (node-exporter, kubelet/cAdvisor, kube-state-metrics)
- PeoplePulse API `/metrics` (requests, latency, errors, record count, events published)
- PeoplePulse worker `:9101/metrics` (events processed from SQS)

Pods opt in with annotations `prometheus.io/scrape: "true"`, `prometheus.io/port`,
`prometheus.io/path` (set by the Helm chart when `metrics.enabled=true`).
Data is not persisted: it disappears with the cluster at `terraform destroy`.
