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
     - `supabase-kong` (Self-Hosted): PostgREST & Auth Gateway (Port 8001).
     - `supabase-studio` (Self-Hosted): Database Management UI (Port 8082).

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

Pushing changes to `main` automatically triggers the CI pipeline (`.github/workflows/ci.yml`) and Deployment workflow (`.github/workflows/deploy.yml`):

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
   - **Deployment Strategy**: `ssh-remote`, `docker-compose`, or `dry-run-test`

---

## Grafana & Observability Links

Once deployed, the Grafana observability dashboard and live log stream can be accessed at:

- **Grafana Web UI**: [http://localhost:3000](http://localhost:3000) (or `http://<SERVER_IP>:3000`)
- **Default Credentials**: `admin` / `admin`
- **Dashboard Path**: Dashboards -> **Telegram Bots Platform Dashboard**
- **Prometheus Direct Metrics**: `http://localhost:8000/metrics`
- **Loki Endpoint**: `http://localhost:3100`
- **Supabase Studio UI**: `http://localhost:8082` (Self-Hosted)

---

## Hetzner Cloud API Integration & Token Acquisition

To manage Hetzner Cloud servers and deploy remote infrastructure using the Hetzner API:

### 1. Generating a Hetzner Cloud API Token
1. Log in to the [Hetzner Cloud Console](https://console.hetzner.cloud/).
2. Select your Project (or create a new project named `telegram-bots`).
3. In the left navigation menu, go to **Security** -> **API Tokens**.
4. Click **Generate API Token**.
5. Give the token a name (e.g. `github-actions-deploy`) and set permissions to **Read & Write**.
6. Copy the generated API token (`HCLOUD_TOKEN`).

### 2. Managing Servers via Hetzner REST API / CLI (`hcloud`)
You can use `curl` or the official Hetzner CLI (`hcloud`) with your token:

```bash
# List all Hetzner cloud servers
curl -H "Authorization: Bearer $HCLOUD_TOKEN" "https://api.hetzner.cloud/v1/servers"

# Get details for a specific server by ID
curl -H "Authorization: Bearer $HCLOUD_TOKEN" "https://api.hetzner.cloud/v1/servers/<SERVER_ID>"

# Create a new server (e.g. CPX21 with Ubuntu 24.04)
curl -X POST "https://api.hetzner.cloud/v1/servers" \
  -H "Authorization: Bearer $HCLOUD_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "telegram-bots-prod",
    "server_type": "cpx21",
    "image": "ubuntu-24.04",
    "location": "nbg1",
    "ssh_keys": ["my-ssh-key"]
  }'
```

### 3. Configuring Hetzner & SSH Secrets in GitHub Actions
To enable automated deployments via GitHub Actions to Hetzner:
1. Go to your GitHub Repository -> **Settings** -> **Secrets and variables** -> **Actions**.
2. Add the following repository secrets:
   - `HCLOUD_TOKEN`: Your Hetzner API Token.
   - `SERVER_HOST`: The public IPv4 address of your Hetzner server.
   - `SERVER_USER`: `root` or your deployment user.
   - `SSH_PRIVATE_KEY`: Private SSH key matching the public key added to your Hetzner server.

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
