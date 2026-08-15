# Telegram AI Bot Platform 🚀

A modular, production-ready platform for deploying Telegram AI bots with **OpenRouter / LiteLLM**, **Telegram Stars (XTR)** monetization, and a full **Grafana Observability Stack** (Prometheus, Loki, Promtail).

---

## 📊 Grafana Observability & Monitoring

The platform includes a pre-configured, production-grade observability stack built with **Grafana**, **Loki**, **Promtail**, and **Prometheus**.

### Accessing Observability & Platform Ports

| Dashboard / Service | Access Link | Description & Usage |
| :--- | :--- | :--- |
| **Grafana Web UI** | `http://<SERVER_IP>:3000` | Platform metrics dashboard & log viewer. <br>**Default Credentials:** `admin` / `admin` |
| **Live Logs (Loki)** | `http://<SERVER_IP>:3000/explore` | Query container JSON logs in real time. <br>**Loki Query:** `{job="docker"}` or `{container_name=~"telegram.*"}` |
| **Prometheus UI** | `http://<SERVER_IP>:9090` | Raw metric targets, time-series data, and active scrapers. |
| **Webhook Metrics API** | `http://<SERVER_IP>:8000/metrics` | Prometheus-formatted metrics exposed by the gateway server (Port 8000). |
| **Supabase Gateway (Self-Hosted)** | `http://<SERVER_IP>:8001` | PostgREST & Auth API Gateway *(Port 8001 to prevent conflict with Webhook Server)*. |
| **Supabase Studio UI (Self-Hosted)** | `http://<SERVER_IP>:8082` | Database Web Dashboard *(Port 8082 to prevent conflict with Grafana)*. |

### Key Metrics Monitored

- **AI Latency & Throughput**: Real-time generation durations, request queues, and model status.
- **User Activity & Analytics**: Daily Active Users (DAU), credit usage, and Telegram Star purchases.
- **Log Aggregation**: Centralized log streaming from all bot instances, AI workers, and webhook servers.
- **System Health**: Error rates, container restarts, and memory/CPU resource consumption.

---

## 🤖 Core Platform Features

- **Multi-Instance Support**: Define and launch separate bot instances (e.g. Image Generators, Admin Bot) using simple YAML files in `instances/`.
- **Unified AI Generation Engine**: Powered by OpenRouter / LiteLLM with automatic fallback from `aimage_generation` to `acompletion` for multimodal vision/image models (e.g., Gemini 2.5 Flash, Gemini 3.1 Flash, FLUX, Recraft, Imagen 3).
- **Binary & URL Media Handling**: Native support for both remote image URLs (`media_urls`) and raw base64 byte streams (`media_bytes` / `BufferedInputFile`).
- **Telegram Stars Monetization**: Automatic daily free credit distribution, balance management, and `/buy` in-app star packages.
- **Preset Engine**: Custom prompt styles (Odyssey, Anime, Cyberpunk, Renaissance, Fine Art) configurable via YAML or database.
- **Database Options**: Support for self-hosted PostgreSQL or Cloud Supabase with user profiles, transaction history, and graceful in-memory fallback when unconfigured.

---

## ⚙️ Managing Bot Instances (`instances/*.yaml`)

Every bot instance is defined by a simple configuration file:

```yaml
bot_id: "image_bot_1"
token_env: "IMAGE_BOT_TOKEN"
constants:
  daily_free_credits: 3
  default_generation_cost: 1
  bot_title: "AI Media Generator"

presets:
  - id: "cinematic"
    title: "Cinematic Movie"
    prompt_template: "Cinematic movie shot, 8k resolution, dramatic lighting, {user_prompt}"
```

### CLI Commands

- **List active instances**:
  ```bash
  uv run bot-cli list
  ```

- **Run all instances (Offline Mock Mode)**:
  ```bash
  uv run bot-cli start all --mock
  ```

- **Run specific instance**:
  ```bash
  uv run bot-cli start image_bot_1
  ```

---

## 🚀 Deployment & Operations

The platform uses a decoupled deployment architecture so bots, telemetry, and databases can be deployed independently:

### 1. Docker Compose Stacks (Hetzner / Linux Server)
```bash
# Ensure shared Docker bridge network exists
docker network create telegram_net 2>/dev/null || true

# 1. Deploy Bots & App Services (Redis, Webhook Gateway, Workers, Bot instances)
docker compose up -d --build

# 2. Deploy Observability Stack (Grafana, Prometheus, Loki, Promtail)
docker compose -f docker-compose.monitoring.yml up -d

# 3. Deploy Self-Hosted Supabase / PostgreSQL Stack
docker compose -f docker-compose.supabase.yml up -d
```

### 2. GitHub Actions CI/CD Workflows
- **`ci.yml`**: Automated Python 3.12 testing & bot instance YAML validation on PRs and pushes.
- **`deploy-bots.yml`**: Dedicated deployment for bot services and webhook gateway.
- **`deploy-monitoring.yml`**: Dedicated deployment for Prometheus & Grafana stack.
- **`deploy-database.yml`**: Dedicated schema migrations & database provisioning.
- **`docker-ghcr.yml`**: Multi-arch container image publisher to GHCR.

### 3. Kubernetes (`k8s/`)
Production Kustomize manifests for Kubernetes clusters (`kubectl apply -k k8s/`).

---

## ⚡ Quick Start (Local Setup)

1. **Install dependencies with `uv`**:
   ```bash
   uv venv
   source .venv/bin/activate
   uv pip install -e ".[dev]"
   ```

2. **Configure environment variables**:
   ```bash
   cp .env.example .env
   ```

3. **Run local pytest test suite**:
   ```bash
   uv run pytest
   ```
