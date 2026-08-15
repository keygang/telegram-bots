# 📚 Platform Architecture, Data Storage & Observability Guide

> 💡 **Visual Architecture Diagrams**: For complete Mermaid diagrams covering high-level architecture, module class composition, generation request sequences, Stars monetization, and Docker deployment stacks, see [SYSTEM_ARCHITECTURE_DIAGRAMS.md](file:///Users/stasbokun/prog/telegram-bots/docs/SYSTEM_ARCHITECTURE_DIAGRAMS.md).

This guide explains **why** each core technology (Supabase, Redis, Prometheus, Promtail, Loki, Grafana, LiteLLM) is used in the Telegram AI Bot Platform, **what purpose** it serves, and **how to actually query and extract data** from each system.

---

## 🏗️ 1. Architecture Overview: How the Pieces Connect

```
                                  ┌────────────────────────┐
                                  │      Telegram API      │
                                  └───────────┬────────────┘
                                              │ Webhook / Polling
                                              ▼
                                 ┌──────────────────────────┐
                                 │ Telegram Webhook Server  │
                                 │     & Bot Instances      │
                                 └───────┬──────────┬───────┘
                                         │          │
                     Enqueue Tasks / FSM │          │ Writes Users, Events,
                                         │          │ Transactions, Presets
                                         ▼          ▼
                             ┌───────────────┐  ┌──────────────────────────┐
                             │     Redis     │  │   Supabase / Postgres    │
                             │ (Queue/State) │  │  (Relational + JSONB DB) │
                             └───────┬───────┘  └──────────────────────────┘
                                     │
                     Worker Dequeue  ▼
                             ┌───────────────┐
                             │   AI Worker   │
                             │ (OpenRouter / │
                             │   LiteLLM)    │
                             └───────────────┘

══════════════════════════ OBSERVABILITY LAYER ══════════════════════════

      Docker Container Logs                     Prometheus Scraping (/metrics)
               │                                               │
               ▼                                               ▼
      ┌─────────────────┐                             ┌─────────────────┐
      │    Promtail     │                             │   Prometheus    │
      │ (Log Collector) │                             │(Metrics Engine) │
      └────────┬────────┘                             └────────┬────────┘
               │ Ships Logs                                    │ Time-Series
               ▼                                               ▼
      ┌─────────────────┐                             ┌─────────────────┐
      │      Loki       │ ◀─────────────────────────  │     Grafana     │
      │ (Log Database)  │       Unified UI / Alerts   │  (Visual Dash)  │
      └─────────────────┘                             └─────────────────┘
```

---

## 🧭 2. Component Breakdown: Purpose & Why We Need Them

| Technology | Role | Why We Need It |
| :--- | :--- | :--- |
| **Supabase** (PostgreSQL) | Primary Database & Document Store | Persistent relational data (users, balances, financial star purchases) + JSONB stores for bot prompt presets and PostHog-style event telemetry. |
| **Redis** | In-Memory Broker & Cache | Ultra-low latency task queue for asynchronous AI generations, user FSM (finite state machine) dialog states, and multi-process metrics aggregation. |
| **Prometheus** | Time-Series Metrics Engine | Scrapes numerical counters, gauges, and histograms every few seconds to measure request rates, p95 generation latencies, and queue depths. |
| **Promtail** | Docker Log Collector | Tails stdout/stderr logs from all running Docker containers and forwards structured logs to Loki in real time. |
| **Loki** | Log Aggregation Engine | Stores and indexes log streams by metadata labels (like `service`, `bot_id`, `level`) without indexing full text, keeping it lightweight and fast. |
| **Grafana** | Centralized Visualization UI | A single web interface to view live charts, query logs, build custom dashboards, and trigger alerting rules. |
| **LiteLLM / OpenRouter** | AI Model Gateway | Unified interface connecting to multiple LLM providers (Gemini, FLUX, Recraft, Claude, OpenAI) with automatic retry and fallback. |

---

## 🔍 3. How to Extract and Use Data

### A. 🗄️ Supabase / PostgreSQL (Business & Analytics Data)

#### Access Points
- **Supabase Studio Web Dashboard**: `http://<SERVER_IP>:8082` (or `http://localhost:8082`)
- **PostgREST API**: `http://<SERVER_IP>:8001/rest/v1/`
- **Direct Postgres Connection**: `postgres://postgres:<PASSWORD>@<SERVER_IP>:5432/postgres`

#### Key Tables & Schema
1. `public.users`: Telegram ID, username, language, registration date, last active timestamp.
2. `public.user_balances`: Credits remaining, total stars spent, free credit reset timestamps.
3. `public.star_transactions`: In-app Telegram Star purchase records (`telegram_payment_charge_id`, `stars_amount`, `credits_added`).
4. `public.events`: PostHog-style analytics events with flexible JSONB properties (`command`, `click`, `generation_completed`, `payment`, `error`).
5. `public.generation_logs`: History of generated images, prompts, models used, durations, and output URLs.
6. `public.preset_prompts`: Configurable dynamic prompt templates and style presets.

#### Practical SQL Queries

```sql
-- 1. Daily Active Users (DAU) for the last 7 days
SELECT 
    DATE(last_active_at) AS active_date, 
    COUNT(DISTINCT telegram_id) AS dau
FROM public.users
WHERE last_active_at >= NOW() - INTERVAL '7 days'
GROUP BY active_date
ORDER BY active_date DESC;

-- 2. Total Telegram Stars Revenue by Bot
SELECT 
    bot_id, 
    COUNT(*) AS total_purchases, 
    SUM(stars_amount) AS total_stars_earned
FROM public.star_transactions
GROUP BY bot_id;

-- 3. AI Generation Success Rate & Average Duration (by Model)
SELECT 
    model_name,
    COUNT(*) AS total_requests,
    ROUND(100.0 * COUNT(*) FILTER (WHERE status = 'success') / COUNT(*), 2) AS success_rate_pct,
    AVG(duration_ms) FILTER (WHERE status = 'success') AS avg_duration_ms
FROM public.generation_logs
GROUP BY model_name;

-- 4. PostHog-Style Event Query: Most Clicked Buttons / Presets (from JSONB)
SELECT 
    properties->>'preset_id' AS preset,
    COUNT(*) AS selection_count
FROM public.events
WHERE event = 'preset_selected'
GROUP BY preset
ORDER BY selection_count DESC
LIMIT 10;
```

---

### B. 📈 Prometheus (Real-Time Performance Metrics)

#### Access Points
- **Prometheus Web UI**: `http://<SERVER_IP>:9090`
- **Raw Metrics API**: `http://<SERVER_IP>:8000/metrics`

#### Exposed Platform Metrics
- `telegram_events_total{bot_id, event_type, event_name}`: Counter of all received commands, messages, and button clicks.
- `telegram_generations_total{bot_id, status, model_name}`: Counter of successful or failed AI generations.
- `telegram_stars_total{bot_id}`: Counter of Telegram Stars earned.
- `telegram_queue_pending_tasks`: Gauge showing currently queued AI generation tasks.
- `telegram_event_duration_seconds_bucket`: Histogram measuring response latency.

#### Practical PromQL Queries (Run in Prometheus UI or Grafana Panels)

```promql
# 1. Total request rate per second across all bots (5-minute sliding window)
sum(rate(telegram_events_total[5m])) by (bot_id)

# 2. AI generation error rate percentage
sum(rate(telegram_generations_total{status="error"}[5m])) 
/ 
sum(rate(telegram_generations_total[5m])) * 100

# 3. 95th Percentile (p95) event handling latency in seconds
histogram_quantile(0.95, sum(rate(telegram_event_duration_seconds_bucket[5m])) by (le, bot_id))

# 4. Current backlog in task queue
telegram_queue_pending_tasks
```

---

### C. 🪵 Loki & Promtail (Centralized JSON Log Aggregation)

#### Access Points
- **Grafana Explore (Loki Data Source)**: `http://<SERVER_IP>:3000/explore`

#### Why Promtail + Loki?
Instead of manually SSH-ing into servers and running `docker logs -f <container>`, Promtail continuously streams all Docker logs directly into Loki. All bot logs are output in structured JSON.

#### Practical LogQL Queries (Run in Grafana Explore)

```logql
# 1. View logs for a specific service
{service="ai_worker"}
{service="webhook_server"}
{service="image_bot_1"}

# 2. Filter for errors only across all containers
{level="error"}

# 3. Search for a specific user ID or trace ID in JSON logs
{service="image_bot_1"} | json | user_id="123456789"

# 4. Search for AI model timeouts or API key errors
{service="ai_worker"} |~ "(?i)timeout|rate limit|quota"

# 5. Extract generation durations from log messages
{service="ai_worker"} | json | duration_ms > 5000
```

---

### D. 📊 Grafana (Unified Visual Dashboards)

#### Access Points
- **Grafana Web Dashboard**: `http://<SERVER_IP>:3000`
- **Default Credentials**: `admin` / `admin`

#### How to Use Grafana
1. **Explore Mode (`/explore`)**:
   - Select **Prometheus** to test metric queries, build graphs, and view trend lines.
   - Select **Loki** to inspect logs, view live tail streams, and trace exceptions.
2. **Pre-configured Dashboard**:
   - Navigate to **Dashboards** → **Telegram Bots Overview**.
   - View real-time panels for:
     - Active Bot Instances & Webhook Health
     - Real-Time Queue Backlog & Worker Load
     - Generation Latencies (p50, p95, p99)
     - Telegram Stars Revenue Summary
     - Real-time Log Stream Feed

---

### E. ⚡ Redis (State & Broker Inspection)

#### Access Points
- Via CLI inside container: `docker exec -it telegram_redis redis-cli`

#### Common Redis Commands to Inspect Data
```bash
# 1. Check pending queue length
LLEN "queue:ai_tasks"

# 2. Check cluster metrics aggregated from distributed instances
HGETALL "metrics:events_total"
HGETALL "metrics:generations_total"
HGETALL "metrics:stars_total"
GET "metrics:queue_pending"

# 3. Check active user FSM state
KEYS "fsm:*"
```

---

## 📋 4. Quick Reference Summary Table

| Service | Port | What to Query | Best For |
| :--- | :--- | :--- | :--- |
| **Grafana** | `3000` | Dashboards, LogQL, PromQL | Visual monitoring, executive overview, live log streaming |
| **Supabase Studio** | `8082` | SQL Editor, Table Viewer | User balances, transaction ledger, event analytics, prompt presets |
| **Prometheus** | `9090` | PromQL | Real-time system health, throughput, error rates, p95 latency |
| **Loki** | `3100` | LogQL (via Grafana) | Debugging bugs, stack traces, inspecting structured JSON payload logs |
| **PostgREST** | `8001` | REST HTTP GET/POST | Querying database tables via secure JSON HTTP endpoints |
| **Redis** | `6379` | Redis CLI commands | Checking task queue status, FSM states, cache keys |
