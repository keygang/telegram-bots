---
name: deploy-telegram-bots
description: >-
  Instructions and procedures for building, testing, and deploying the Telegram AI Bot Platform,
  its microservices, observability stack, and database stack via k3s Kubernetes and GitHub Actions CI/CD.
---

# Deploy Telegram Bots Platform (Dokploy & k3s Kubernetes)

This skill provides step-by-step instructions for validating, building, and deploying the Telegram AI Bot Platform, its bot instances, and microservices via **Dokploy PaaS** (`docker-compose.dokploy.yml`) and **k3s lightweight Kubernetes** (`k8s/`).

---

## Dokploy PaaS Deployment (`docker-compose.dokploy.yml`)

1. Install Dokploy on server: `curl -sSL https://dokploy.com/setup.sh | sh`
2. Create Compose stack pointing to `docker-compose.dokploy.yml`.
3. Set environment variables (`IMAGE_BOT_1_TOKEN`, `OPENROUTER_API_KEY`, `DOKPLOY_HOST`, etc.).
4. Traefik automatically issues Let's Encrypt SSL on `DOKPLOY_HOST`.
5. See full guide in [docs/DOKPLOY_DEPLOYMENT.md](file:///Users/stasbokun/prog/telegram-bots/docs/DOKPLOY_DEPLOYMENT.md).

---

## Architecture & Cluster Layout

The platform runs on a single-node **k3s** Kubernetes cluster inside the `telegram-bots` namespace:

1. **Kubernetes Microservices (`k8s/` & `.github/workflows/deploy-bots.yml`)**
   - `redis`: Redis 7 persistent datastore with `local-path` PersistentVolumeClaim (`/data`).
   - `webhook-server`: FastAPI HTTP webhook gateway & Prometheus `/metrics` endpoint exposed on port 8000 via Service `LoadBalancer`.
   - `ai-worker`: Background asynchronous worker processing AI generation queues with OpenRouter.
   - `image-bot-1`: Dedicated microservice deployment running ImageBot instance.
   - `admin-bot`: Dedicated microservice deployment running AdminBot instance.

2. **Triggering Deployments**:
   - Push to `main` when bot/platform/k8s code changes.
   - GitHub Actions `workflow_dispatch` on `deploy-bots.yml` using `k8s-remote` strategy.

---

## Step-by-Step Deployment Procedures

### 1. Pre-Deployment Code & Config Verification

Before pushing to GitHub:

```bash
# Run full pytest suite
uv run pytest

# Validate all YAML bot configs in instances/
uv run python -m platform_core.cli list

# Validate Kubernetes manifests (Kustomize)
kubectl kustomize k8s/
```

### 2. Manual Server Deployment via k3s CLI

To deploy directly on the Hetzner server:

```bash
# Full deployment / setup
sudo /opt/telegram-bots/scripts/setup_k3s.sh

# Or update specific deployment target:
sudo /opt/telegram-bots/scripts/deploy_k8s.sh all
sudo /opt/telegram-bots/scripts/deploy_k8s.sh webhook_server
sudo /opt/telegram-bots/scripts/deploy_k8s.sh image_bot_1
```

### 3. Monitoring & Pod Status

```bash
# Check all pods and services
k3s kubectl get all -n telegram-bots

# Stream logs for a bot instance
k3s kubectl logs -n telegram-bots -l app=image-bot-1 -f

# Check webhook gateway health
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/metrics
```
