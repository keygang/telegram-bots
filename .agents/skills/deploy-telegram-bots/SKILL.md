---
name: deploy-telegram-bots
description: >-
  Instructions and procedures for building, testing, and deploying the Telegram AI Bot Platform,
  its microservices, observability stack (Grafana, Prometheus, Loki, Promtail), and database stack via split GitHub Actions CI/CD.
---

# Deploy Telegram Bots, Observability & Database Stacks

This skill provides step-by-step instructions for validating, building, and deploying the Telegram AI Bot Platform, its bot instances, the Grafana observability stack, and Supabase database migrations via modular, decoupled GitHub Actions CI/CD workflows.

---

## Modular Deployment Architecture

The platform separates deployments into three independent, decoupled domains:

1. **Bots & Platform Stack** (`docker-compose.yml` & `.github/workflows/deploy-bots.yml`)
   - **Services**: `redis`, `webhook_server` (FastAPI /metrics), `ai_worker`, `all_bots`, `image_bot_1`, `admin_bot`.
   - **Trigger**: Push to `main` when bot/platform code changes (`bots/**`, `platform_core/**`, `instances/**`, `docker-compose.yml`), or via `workflow_dispatch`.
   - **Network**: Connects to `telegram_net` Docker bridge network.

2. **Observability Stack** (`docker-compose.monitoring.yml` & `.github/workflows/deploy-monitoring.yml`)
   - **Services**: `prometheus` (Port 9090), `loki` (Port 3100), `promtail`, `grafana` (Port 3000).
   - **Trigger**: Push to `main` when monitoring files change (`monitoring/**`, `docker-compose.monitoring.yml`), or via `workflow_dispatch`.
   - **Network**: Connects to shared `telegram_net` network to scrape `webhook_server:8000`.

3. **Database & Migrations Stack** (`docker-compose.supabase.yml` & `.github/workflows/deploy-database.yml`)
   - **Services**: `supabase_db` (PostgreSQL Port 5432), `supabase_rest` (PostgREST Port 8001), SQL migrations (`supabase/schema.sql`).
   - **Trigger**: Push to `main` when database schema changes (`supabase/**`, `docker-compose.supabase.yml`), or via `workflow_dispatch`.

---

## Step-by-Step Deployment Procedures

### 1. Pre-Deployment Code & Config Verification

Before committing and triggering a deployment, always run tests and validate configurations:

```bash
# Run full pytest suite including Prometheus metric tests
uv run pytest

# Validate all YAML bot configs in instances/
uv run python -m platform_core.cli list

# Validate Docker Compose configurations
docker compose config
docker network create telegram_net 2>/dev/null || true
docker compose -f docker-compose.monitoring.yml config
docker compose -f docker-compose.supabase.yml config
```

### 2. Committing & Pushing to GitHub

Pushing changes to `main` automatically triggers the corresponding CI/CD pipeline based on modified file paths:

```bash
git add .
git commit -m "feat: <description of changes>"
git push origin main
```

- If you change bot code: `.github/workflows/deploy-bots.yml` triggers.
- If you change monitoring: `.github/workflows/deploy-monitoring.yml` triggers.
- If you change database/schema: `.github/workflows/deploy-database.yml` triggers.

---

### 3. Deploying via GitHub Actions Workflows

#### A. Deploying Bots (`deploy-bots.yml`)
1. Navigate to GitHub -> **Actions** -> **Deploy Telegram Bots 🤖**
2. Click **Run workflow**:
   - **Environment**: `production` (or `staging` / `dev`)
   - **Target Service/Bot**: `all` (or specific service e.g. `image_bot_1`, `admin_bot`, `webhook_server`, `ai_worker`)
   - **Deployment Strategy**: `ssh-remote`, `docker-compose`, or `dry-run-test`

#### B. Deploying Observability (`deploy-monitoring.yml`)
1. Navigate to GitHub -> **Actions** -> **Deploy Observability Stack 📊**
2. Click **Run workflow**:
   - **Environment**: `production`
   - **Service**: `all`, `grafana`, `prometheus`, `loki`, or `promtail`
   - **Deployment Strategy**: `ssh-remote`, `validate-config`, or `dry-run-test`

#### C. Deploying Database & Migrations (`deploy-database.yml`)
1. Navigate to GitHub -> **Actions** -> **Deploy Database & Migrations 🗄️**
2. Click **Run workflow**:
   - **Environment**: `production`
   - **Action**: `apply-migrations`, `deploy-self-hosted-stack`, or `verify-schema`
   - **Deployment Strategy**: `ssh-remote` or `dry-run-test`

---

## Local & Server Docker Compose Commands

```bash
# Ensure the shared network exists
docker network create telegram_net 2>/dev/null || true

# 1. Start Bots & Core Platform
docker compose up -d

# 2. Start Observability Stack (Grafana, Prometheus, Loki)
docker compose -f docker-compose.monitoring.yml up -d

# 3. Start Self-Hosted Supabase / PostgreSQL Stack (if self-hosting)
docker compose -f docker-compose.supabase.yml up -d

# Or run all stacks together:
docker compose -f docker-compose.yml -f docker-compose.monitoring.yml -f docker-compose.supabase.yml up -d
```

---

## Grafana & Observability Links

Once deployed, the Grafana observability dashboard and live log stream can be accessed at:

- **Grafana Web UI**: [http://localhost:3000](http://localhost:3000) (or `http://<SERVER_IP>:3000`)
- **Default Credentials**: `admin` / `admin`
- **Dashboard Path**: Dashboards -> **Telegram Bots Platform Dashboard**
- **Prometheus Direct Metrics**: `http://localhost:8000/metrics`
- **Loki Endpoint**: `http://localhost:3100`
- **Supabase Studio / REST**: `http://localhost:8001` (Self-Hosted)

---

## Troubleshooting Deployment Failures

1. **GitHub Actions Failures**:
   - Check job logs under **Actions** tab on GitHub.
   - Verify secrets `SERVER_HOST`, `SERVER_USER`, `SSH_PRIVATE_KEY` in repo settings.

2. **Metrics Not Appearing in Grafana**:
   - Ensure `telegram_net` Docker network is created and both stacks are connected.
   - Verify `webhook_server` is running and returning HTTP 200 on `/metrics`.
   - Check Prometheus targets at [http://localhost:9090/targets](http://localhost:9090/targets).

3. **Logs Not Appearing in Loki**:
   - Verify `LOG_FORMAT=json` is set in container environment variables.
   - Ensure Promtail container has `/var/run/docker.sock` mounted.
