# 🚀 Deploying Telegram AI Bot Platform with Dokploy

This guide outlines how to deploy and manage the **Telegram AI Bot Platform** on your own server using **[Dokploy](https://dokploy.com)** — a self-hosted Platform as a Service (PaaS) with automatic SSL (Let's Encrypt), Traefik reverse proxying, Git auto-deployments, managed databases, and real-time monitoring.

---

## 📑 Table of Contents

1. [Why Dokploy?](#why-dokploy)
2. [Architecture Overview in Dokploy](#architecture-overview-in-dokploy)
3. [Prerequisites & Server Setup](#prerequisites--server-setup)
4. [Deployment Method A: Compose Stack (Recommended)](#deployment-method-a-compose-stack-recommended)
5. [Deployment Method B: Individual Applications + Managed Redis](#deployment-method-b-individual-applications--managed-redis)
6. [Configuring Custom Domain & Let's Encrypt SSL](#configuring-custom-domain--lets-encrypt-ssl)
7. [Setting Up Automated CI/CD (Auto-Deploy on Push)](#setting-up-automated-cicd-auto-deploy-on-push)
8. [Registering Telegram Webhooks](#registering-telegram-webhooks)
9. [Observability, Logs & Alerts](#observability-logs--alerts)
10. [Troubleshooting & Maintenance](#troubleshooting--maintenance)

---

## 💡 Why Dokploy?

Dokploy provides a modern alternative to Heroku, Coolify, and Kubernetes for single-server or multi-server deployments:

- 🔒 **Automated SSL/TLS**: Built-in Traefik reverse proxy automatically issues and renews Let's Encrypt HTTPS certificates for webhook endpoints.
- ⚡ **Git Auto-Deploy**: Automatically builds and deploys on `git push` to `main` via GitHub/GitLab webhooks.
- 🗄️ **Managed Databases**: 1-click provisioned Redis or PostgreSQL with automated S3 backups.
- 📊 **Resource & Log Monitoring**: Real-time log streams, CPU/memory usage charts, and notification hooks (Telegram, Discord, Slack).
- 🧩 **Zero Kubernetes Overhead**: Native Docker & Docker Compose support without the operational complexity of a full k8s control plane.

---

## 🏗️ Architecture Overview in Dokploy

When deployed via Dokploy, the system runs with the following structure:

```
                          Internet / Telegram API
                                     │
                                     ▼ (HTTPS Port 443)
                         ┌───────────────────────┐
                         │    Dokploy Traefik    │  <── Let's Encrypt SSL
                         │     Reverse Proxy     │
                         └───────────┬───────────┘
                                     │
                                     ▼ (Internal HTTP Port 8000)
                         ┌───────────────────────┐
                         │    webhook-server     │  <── FastAPI Gateway + /metrics
                         └───────────┬───────────┘
                                     │
                         ┌───────────┴───────────┐
                         ▼                       ▼
                ┌─────────────────┐     ┌─────────────────┐
                │   image_bot_1   │     │    admin_bot    │
                └────────┬────────┘     └────────┬────────┘
                         │                       │
                         ▼                       ▼
                ┌─────────────────────────────────────────┐
                │             telegram_redis              │  <── Job Queue & Cache
                └────────────────────┬────────────────────┘
                                     │
                                     ▼
                ┌─────────────────────────────────────────┐
                │                ai_worker                │  <── OpenRouter / LiteLLM
                └─────────────────────────────────────────┘
```

---

## 🛠️ Prerequisites & Server Setup

### 1. Server Requirements
- **OS**: Ubuntu 22.04 LTS or Debian 12 (or any modern Linux distribution).
- **Hardware**: Minimum 2 vCPU, 2 GB RAM (4 GB recommended for concurrent image workflows).
- **Ports Open**: `80` (HTTP), `443` (HTTPS), `3000` (Dokploy Dashboard).

### 2. Install Dokploy on Your Server
Run the official Dokploy automated setup script on your VPS:

```bash
curl -sSL https://dokploy.com/setup.sh | sh
```

Once installed, open your browser and navigate to:
```
http://<YOUR_SERVER_IP>:3000
```
Create your administrative account during the initial wizard.

---

## 📦 Deployment Method A: Compose Stack (Recommended)

The easiest and cleanest approach is deploying the platform as a single **Dokploy Compose Stack** using `docker-compose.dokploy.yml`.

### Step 1: Create a Project in Dokploy
1. In the Dokploy Dashboard, click **Create Project** (e.g. `telegram-ai-platform`).
2. Inside the project, click **Create Service** ➔ Select **Compose**.
3. Name your stack: `telegram-bots-stack`.

### Step 2: Configure Git Repository
1. In the **General** tab of the Compose service:
   - **Source Type**: `Git` (or `GitHub`).
   - **Repository URL**: `https://github.com/your-username/telegram-bots` (or connect your GitHub account).
   - **Branch**: `main`.
   - **Compose Path**: `docker-compose.dokploy.yml`.

### Step 3: Configure Environment Variables
Navigate to the **Environment** tab and paste your `.env` configuration:

```env
# Telegram Bot Tokens
IMAGE_BOT_1_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz_image
ADMIN_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz_admin
ADMIN_USER_IDS_RAW=123456789

# AI Generation Engine
OPENROUTER_API_KEY=sk-or-v1-your_openrouter_api_key_here

# Domain configuration for Traefik routing (Let's Encrypt)
DOKPLOY_HOST=bots.yourdomain.com

# Platform Settings
BOT_STRATEGY=webhook
METRICS_ENABLED=true
USE_MOCK_GENERATOR=false
LOG_FORMAT=json

# Database Credentials (Cloud Supabase or Self-Hosted)
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-service-role-or-anon-key
```

### Step 4: Deploy Stack
Click **Deploy**. Dokploy will:
1. Clone the repository and build the container images via `Dockerfile`.
2. Spin up `redis`, `webhook_server`, `ai_worker`, `image_bot_1`, and `admin_bot`.
3. Register the Traefik routing rule for `DOKPLOY_HOST` and obtain a Let's Encrypt certificate.

---

## 🧩 Deployment Method B: Individual Applications + Managed Redis

If you prefer isolating each bot and service as standalone Dokploy entities:

1. **Create Managed Redis**:
   - In Dokploy, click **Create Service** ➔ **Database** ➔ **Redis**.
   - Note the internal connection string: `redis://:password@redis:6379/0`.

2. **Deploy Webhook Server (Application)**:
   - Click **Create Service** ➔ **Application**.
   - Point to your Git repo, set Dockerfile path to `Dockerfile`.
   - Set start command to `python -m platform_core.cli server --host 0.0.0.0 --port 8000`.
   - In **Domains**, add `bots.yourdomain.com` routing to container port `8000` with HTTPS enabled.

3. **Deploy AI Worker (Application)**:
   - Click **Create Service** ➔ **Application**.
   - Build via `Dockerfile`.
   - Set start command to `python -m platform_core.cli worker --concurrency 4`.

4. **Deploy Bot Instances (Applications)**:
   - Image Bot: `python -m platform_core.cli start image_bot_1`
   - Admin Bot: `python -m platform_core.cli start admin_bot`

---

## 🌐 Configuring Custom Domain & Let's Encrypt SSL

1. Add a **DNS A Record** in your DNS provider (Cloudflare, Namecheap, Route53, Hetzner DNS):
   ```
   bots.yourdomain.com  IN  A  <YOUR_SERVER_IP>
   ```
2. In Dokploy, ensure `DOKPLOY_HOST` in your Compose environment matches `bots.yourdomain.com`.
3. Traefik automatically verifies the HTTP-01 challenge and provisions a free SSL certificate.

Test your webhook endpoint:
```bash
curl https://bots.yourdomain.com/health
# Response: {"status":"healthy"}

curl https://bots.yourdomain.com/metrics
# Response: Prometheus metrics output
```

---

## 🔄 Setting Up Automated CI/CD (Auto-Deploy on Push)

1. In your Dokploy Compose stack or Application, open the **Deployments** tab.
2. Under **Webhook**, copy the unique Dokploy Deployment Webhook URL:
   ```
   https://dokploy.yourserver.com/api/deploy/...
   ```
3. In GitHub, navigate to your repository:
   - **Settings** ➔ **Webhooks** ➔ **Add webhook**.
   - **Payload URL**: Paste the Dokploy Webhook URL.
   - **Content type**: `application/json`.
   - **Events**: Select *Just the push event*.
4. Now, whenever you push code changes to `main`, Dokploy will automatically rebuild and deploy without downtime!

---

## 🤖 Registering Telegram Webhooks

Once your Dokploy domain is live with HTTPS, register the webhook with Telegram's API:

```bash
# Register Image Bot Webhook
curl -F "url=https://bots.yourdomain.com/webhook/image_bot_1" \
     https://api.telegram.org/bot<IMAGE_BOT_1_TOKEN>/setWebhook

# Register Admin Bot Webhook
curl -F "url=https://bots.yourdomain.com/webhook/admin_bot" \
     https://api.telegram.org/bot<ADMIN_BOT_TOKEN>/setWebhook
```

To verify webhook status:
```bash
curl https://api.telegram.org/bot<IMAGE_BOT_1_TOKEN>/getWebhookInfo
```

---

## 📊 Observability, Logs & Alerts

### 1. Viewing Live Logs in Dokploy
- Click any service in your Dokploy project and navigate to the **Logs** tab.
- Filter logs in real time across bot workers, webhook traffic, and generation queues.

### 2. Notifications & Alerts
- Navigate to **Server Settings** ➔ **Notifications** in Dokploy.
- Configure instant alerts to your **Telegram Bot** or **Discord Channel** on:
  - Deployment success / failure
  - Container crashes / restarts
  - High CPU or Memory consumption thresholds

---

## 🔧 Troubleshooting & Maintenance

| Issue | Cause | Solution |
| :--- | :--- | :--- |
| **502 Bad Gateway** | `webhook_server` is starting or failed healthcheck | Check `webhook_server` logs in Dokploy. Ensure Redis is healthy. |
| **SSL Certificate Pending** | DNS record hasn't propagated or port 80 blocked | Ensure ports `80` and `443` are open in your VPS firewall (UFW/Security Group). |
| **Bot not responding to messages** | Bot token invalid or webhook URL not set | Verify `IMAGE_BOT_1_TOKEN` in Dokploy environment variables and run `getWebhookInfo`. |
| **Worker queue backlog** | High generation demand | Increase worker concurrency (`--concurrency 8`) or scale up worker replicas in Compose. |

---

### 🎉 You are all set!
Your Telegram AI platform is now deployed with zero-hassle operations via **Dokploy**.
