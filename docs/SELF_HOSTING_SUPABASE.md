# Self-Hosting Supabase Guide 🛠️

This document provides step-by-step instructions on how to self-host Supabase using Docker & Docker Compose and configure this Telegram Bot platform to use your self-hosted database.

---

## 📋 Prerequisites

Before proceeding, ensure you have the following installed on your machine or server:
- **Docker** (v20.10 or higher)
- **Docker Compose** (v2.0 or higher)
- **Git**

---

## 🚀 Step 1: Clone Official Supabase Docker Repository

Supabase provides an official Docker Compose setup for self-hosting all core services (PostgreSQL, PostgREST, GoTrue Auth, Kong Gateway, Studio UI, Storage, Realtime).

Run the following commands in your preferred directory (outside or alongside this repo):

```bash
# Clone Supabase Docker setup (shallow clone for quick setup)
git clone --depth 1 https://github.com/supabase/supabase.git

# Navigate to the docker directory
cd supabase/docker
```

---

## 🔑 Step 2: Configure Environment Variables & Generate Secrets

1. Copy the example environment configuration file:
   ```bash
   cp .env.example .env
   ```

2. **Generate Secure API Keys and JWT Secrets:**
   *Do NOT use default credentials in production.* Supabase provides utility scripts to auto-generate secret keys:

   ```bash
   # Generate POSTGRES_PASSWORD, JWT_SECRET, ANON_KEY, and SERVICE_ROLE_KEY
   sh utils/generate-keys.sh
   ```

   Alternatively, manually set the following variables in `.env`:
   - `POSTGRES_PASSWORD`: Strong database password.
   - `JWT_SECRET`: A secret string (min 32 characters) for signing API tokens.
   - `ANON_KEY`: Public API JWT key (generated from `JWT_SECRET`).
   - `SERVICE_ROLE_KEY`: Service role API JWT key with full database privileges.
   - `DASHBOARD_USERNAME` & `DASHBOARD_PASSWORD`: Login credentials for Supabase Studio UI.
   - `SITE_URL`: Your application URL (e.g. `http://localhost:3000` or your server domain).

---

## 🐳 Step 3: Start Self-Hosted Supabase Containers

Pull and launch the Docker stack in background mode:

```bash
# Pull latest service images
docker compose pull

# Start all Supabase services
docker compose up -d
```

### Verification
Check if all containers are running:
```bash
docker compose ps
```

You should see containers for:
- `supabase-db` (PostgreSQL Database on port `5432`)
- `supabase-kong` (API Gateway on port `8001` - changed from `8000` to avoid conflict with Webhook Server)
- `supabase-studio` (Dashboard UI on port `8082` - changed from `3000` to avoid conflict with Grafana)
- `supabase-rest` (PostgREST API)
- `supabase-auth` (GoTrue Auth)

Access Supabase Studio by opening `http://localhost:8082` (or `http://<YOUR_SERVER_IP>:8082`) in your web browser.

---

## 🗄️ Step 4: Initialize Database Schema

You need to execute the SQL schema script to create the necessary tables (`users`, `user_balances`, `star_transactions`, `bot_events`, `generation_logs`).

### Option A: Via Supabase Studio UI (Recommended)
1. Open Supabase Studio in your browser (`http://localhost:8082`).
2. Go to **SQL Editor** -> **New Query**.
3. Copy and paste the contents of [`supabase/schema.sql`](../supabase/schema.sql).
4. Click **Run**.

### Option B: Via `psql` directly
Run the schema script against your PostgreSQL container:

```bash
docker exec -i supabase-db psql -U postgres -d postgres < /path/to/telegram-bots/supabase/schema.sql
```

---

## ⚙️ Step 5: Update Telegram Bot Platform `.env` File

Update your `.env` file in the root directory of this repository:

```env
# Self-Hosted Supabase API Gateway URL (Kong) - Port 8001
SUPABASE_URL=http://localhost:8001

# Service Role Key or Anon Key generated in Step 2 (from supabase/docker/.env)
SUPABASE_KEY=your_generated_service_role_key_here

# Optional: Direct PostgreSQL Connection details if connecting directly to database container
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_secure_postgres_password
POSTGRES_DB=postgres
DATABASE_URL=postgresql://postgres:your_secure_postgres_password@localhost:5432/postgres
```

If your bot runs inside Docker via `docker-compose.yml` on the same host, you can use `http://host.docker.internal:8001` or join the shared Docker network.

---

## 🧪 Step 6: Verify Connection

Run the platform test suite to verify that database synchronization and fallbacks operate cleanly:

```bash
uv run pytest tests/test_db.py
```

Or launch a bot instance:
```bash
uv run python -m platform_core.cli start image_bot_1 --mock
```

---

## 📦 Maintenance & Backups

### Database Backup
To take a full dump of your PostgreSQL database:
```bash
docker exec -t supabase-db pg_dump -U postgres postgres > backup_$(date +%Y%m%m_%H%M%S).sql
```

### Restoring Database Backup
```bash
cat backup_file.sql | docker exec -i supabase-db psql -U postgres -d postgres
```
