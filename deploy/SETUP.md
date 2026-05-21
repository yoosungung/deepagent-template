# deploy/SETUP.md (Kubernetes Deployment Setup)

This document provides a runbook for deploying the SI Agent Scaffolding application stack to a Kubernetes (k8s) cluster.

---

## Architecture Overview

```txt
   Ingress
      │
      ▼
   Services
   ├── client-service (React SPA)
   └── server-service (FastAPI + DeepAgents Backend)
         │
         ▼
      Database (PostgreSQL State Store & VFS Storage)
```

---

## Deployment Steps

### 1. Configure Secrets
Create a Kubernetes secret containing your API keys and database credentials:
```bash
kubectl create secret generic agent-secrets \
  --from-literal=openai-api-key="your-key-here" \
  --from-literal=database-url="postgresql://postgres:postgres@postgres-service:5432/postgres"
```

### 2. Apply Manifests
Use Kustomize to apply the base configuration manifests:
```bash
cd deploy/k8s/base
kubectl apply -k .
```

### 3. Verify Deployment
Ensure pods are running successfully:
```bash
kubectl get pods -w
```
Confirm connectivity by checking server service logs:
```bash
kubectl logs -l app=agent-server
```
