# ☸️ Deploying Telegram AI Bot Platform on Kubernetes

This guide walks you through deploying the complete **Telegram AI Bot Platform** stack on Kubernetes (Local: Minikube, K3s, Kind, or Cloud: GKE, EKS, AKS).

---

## 📌 Architecture Components in Kubernetes

The Kubernetes deployment comprises:

1. **Namespace (`telegram-bots`)**: Isolated environment for platform services.
2. **ConfigMap (`telegram-bots-config`)**: Non-sensitive settings (`REDIS_URL`, `FREE_DAILY_CREDITS`, `METRICS_ENABLED`, etc.).
3. **Secret (`telegram-bots-secret`)**: API credentials (`IMAGE_BOT_TOKEN`, `OPENROUTER_API_KEY`, `SUPABASE_KEY`, `POSTGRES_PASSWORD`).
4. **Redis Deployment & Service (`redis`)**: ClusterIP Service on port 6379 for task queueing.
5. **Webhook Server Gateway (`webhook-server`)**: Scalable HTTP gateway running `platform_core.cli server` with `/health` liveness & readiness probes and optional Ingress.
6. **AI Worker Pool (`ai-worker`)**: Background worker processing AI image & media generation requests asynchronously.
7. **Telegram Bot Runner (`telegram-all-bots`)**: Multi-bot polling runner for handling Telegram user interactions.

---

## 🚀 Quick Start (Local Deployment with Minikube / K3s / Kind)

### Step 1: Build Docker Image locally

Build the production Docker image and tag it as `telegram-bots-platform:latest`:

```bash
docker build -t telegram-bots-platform:latest .
```

If using **Minikube**, load the image directly into Minikube's Docker daemon:
```bash
minikube image load telegram-bots-platform:latest
```
Or for **Kind**:
```bash
kind load docker-image telegram-bots-platform:latest
```

---

### Step 2: Configure Secrets

1. Copy the Secret template:
   ```bash
   cp k8s/secret.yaml.template k8s/secret.yaml
   ```

2. Edit `k8s/secret.yaml` with your actual Telegram bot tokens and API keys:
   ```yaml
   stringData:
     IMAGE_BOT_TOKEN: "your_real_telegram_bot_token"
     OPENROUTER_API_KEY: "sk-or-v1-your_real_openrouter_api_key"
     SUPABASE_KEY: "your_supabase_service_role_key"
   ```

---

### Step 3: Deploy to Kubernetes

Deploy all resources in one command using Kustomize:

```bash
kubectl apply -k k8s/
```

Or apply raw manifests directly:
```bash
kubectl apply -f k8s/
```

---

### Step 4: Verify Deployment Status

Check that all pods and services in the `telegram-bots` namespace are running:

```bash
kubectl get all -n telegram-bots
```

Output:
```text
NAME                                  READY   STATUS    RESTARTS   AGE
pod/ai-worker-674488b776-6hx2p        1/1     Running   0          30s
pod/ai-worker-674488b776-k8dls        1/1     Running   0          30s
pod/redis-74b7cbb45b-7zfxm            1/1     Running   0          30s
pod/telegram-all-bots-556bcbb9-9x5lq 1/1     Running   0          30s
pod/webhook-server-6b5c7fdb7b-l8nrt   1/1     Running   0          30s
pod/webhook-server-6b5c7fdb7b-m2p5q   1/1     Running   0          30s

NAME                     TYPE        CLUSTER-IP       EXTERNAL-IP   PORT(S)    AGE
service/redis            ClusterIP   10.96.120.45     <none>        6379/TCP   30s
service/webhook-server   ClusterIP   10.96.189.102    <none>        8000/TCP   30s
```

---

### Step 5: Test Webhook Health Endpoint

Port-forward the Webhook Gateway to test the `/health` endpoint:

```bash
kubectl port-forward svc/webhook-server 8000:8000 -n telegram-bots
```

In a new terminal:
```bash
curl http://localhost:8000/health
```
Response:
```json
{
  "status": "healthy",
  "active_bot_count": 2,
  "bot_ids": ["image_bot_1", "image_bot_2"],
  "pending_queue_length": 0
}
```

---

## ⚙️ Scaling Workers & Gateways

- **Scale AI Workers**:
  ```bash
  kubectl scale deployment ai-worker --replicas=5 -n telegram-bots
  ```

- **Scale Webhook Server Gateways**:
  ```bash
  kubectl scale deployment webhook-server --replicas=4 -n telegram-bots
  ```

---

## 🔍 Inspection & Logging

- **Stream AI Worker Logs**:
  ```bash
  kubectl logs -f deployment/ai-worker -n telegram-bots
  ```

- **Stream Webhook Server Logs**:
  ```bash
  kubectl logs -f deployment/webhook-server -n telegram-bots
  ```

- **Stream Bot Runner Logs**:
  ```bash
  kubectl logs -f deployment/telegram-all-bots -n telegram-bots
  ```

---

## 🛑 Clean Up

To delete all platform resources from your Kubernetes cluster:

```bash
kubectl delete -k k8s/
```
