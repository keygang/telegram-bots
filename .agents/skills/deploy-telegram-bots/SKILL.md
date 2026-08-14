---
name: deploy-telegram-bots
description: >-
  Instructions and procedures for building, testing, and deploying the Telegram AI Bot Platform,
  its microservices, and observability stack (Grafana, Prometheus, Loki, Promtail) via GitHub Actions CI/CD.
---

# Deploy Telegram Bots & Observability Stack

This skill provides step-by-step instructions for validating, building, and deploying the Telegram AI Bot Platform, its bot instances, and the Grafana observability stack via GitHub Actions CI/CD workflows.

---

## Deployment Architectures & Strategies

The platform supports two deployment methods:

1. **GitHub Actions CI/CD Workflow (Recommended)**
   - Triggered on push to `main` or manually via `workflow_dispatch`.
   - Workflows available in [.github/workflows/](file:///.github/workflows/):
     - `ci.yml`: Runs `pytest`, validates YAML instance configs, builds Docker images.
     - `deploy.yml`: Deploys bot instances to production/staging servers via SSH or Docker Compose.
     - `docker-ghcr.yml`: Builds & publishes multi-arch Docker images to GitHub Container Registry (`ghcr.io`).

2. **Docker Compose Stack (Observability & Production)**
   - Services defined in [docker-compose.yml](file:///docker-compose.yml):
     - `webhook_server`: FastAPI Webhook Gateway (Port 8000). Exposes `/metrics` endpoint.
     - `ai_worker`: Background AI generation worker pool.
     - `all_bots` / `image_bot_1` / `image_bot_2` / `admin_bot`: Bot runners.
     - `prometheus`: Scrapes metrics from `webhook_server:8000` (Port 9090).
     - `loki`: Log aggregation server (Port 3100).
     - `promtail`: Tails Docker container JSON logs and ships to Loki.
     - `grafana`: Grafana dashboard UI (Port 3000).

---

## Step-by-Step Deployment Procedure

### 1. Pre-Deployment Code & Config Verification

Before triggering a deployment, always run the unit tests and validate the bot instance configurations:

```bash
# Run full pytest suite including Prometheus metric tests
uv run pytest

# Validate all YAML bot configs in instances/
uv run python -m platform_core.cli list
```

### 2. Committing & Pushing to GitHub

Pushing changes to `main` automatically triggers the CI pipeline (`.github/workflows/ci.yml`):

```bash
git add .
git commit -m "feat: <description of changes>"
git push origin main
```

### 3. Deploying via GitHub Actions (`deploy.yml`)

To deploy to production using GitHub Actions:

1. Navigate to the GitHub repository: `https://github.com/keygang/telegram-bots`
2. Go to **Actions** -> **Deploy Telegram Bot Instances 🚀**
3. Click **Run workflow**:
   - **Environment**: `production` (or `staging` / `dev`)
   - **Bot Instance**: `all` (or specific instance e.g. `image_bot_1`)
   - **Deployment Strategy**: `ssh-remote` (or `docker-compose`)

---

## Grafana & Observability Links

Once deployed, the Grafana observability dashboard and live log stream can be accessed at:

- **Grafana Web UI**: [http://localhost:3000](http://localhost:3000) (or `http://<SERVER_IP>:3000`)
- **Default Credentials**: `admin` / `admin`
- **Dashboard Path**: Dashboards -> **Telegram Bots Platform Dashboard**
- **Prometheus Direct Metrics**: `http://localhost:8000/metrics`
- **Loki Endpoint**: `http://localhost:3100`

---

## Troubleshooting Deployment Failures

1. **GitHub Actions Failures**:
   - Check job logs under **Actions** tab on GitHub.
   - Verify secrets `SERVER_HOST`, `SERVER_USER`, `SSH_PRIVATE_KEY` in repo settings if using `ssh-remote` strategy.

2. **Metrics Not Appearing in Grafana**:
   - Verify `webhook_server` is running and returning HTTP 200 on `/metrics`.
   - Check Prometheus targets at [http://localhost:9090/targets](http://localhost:9090/targets).

3. **Logs Not Appearing in Loki**:
   - Verify `LOG_FORMAT=json` is set in container environment variables.
   - Ensure Promtail container has `/var/run/docker.sock` mounted.
