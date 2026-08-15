-- ==============================================================================
-- Schema Migration for Self-Hosted Supabase / PostgreSQL Database
-- Telegram AI Bot Platform Database Schema
-- ==============================================================================

-- Enable UUID extension if not already enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Initialize default Supabase roles if not present
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'supabase_admin') THEN
        CREATE ROLE supabase_admin WITH SUPERUSER CREATEDB CREATEROLE LOGIN REPLICATION BYPASSRLS;
    END IF;

    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'authenticator') THEN
        CREATE ROLE authenticator WITH NOINHERIT LOGIN;
    END IF;

    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'anon') THEN
        CREATE ROLE anon WITH NOLOGIN;
    END IF;

    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'authenticated') THEN
        CREATE ROLE authenticated WITH NOLOGIN;
    END IF;

    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'service_role') THEN
        CREATE ROLE service_role WITH NOLOGIN BYPASSRLS;
    END IF;

    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'supabase_auth_admin') THEN
        CREATE ROLE supabase_auth_admin WITH SUPERUSER CREATEDB CREATEROLE LOGIN;
    END IF;

    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'supabase_storage_admin') THEN
        CREATE ROLE supabase_storage_admin WITH SUPERUSER CREATEDB CREATEROLE LOGIN;
    END IF;

    GRANT anon TO authenticator;
    GRANT authenticated TO authenticator;
    GRANT service_role TO authenticator;
END
$$;


-- 1. Users Table
CREATE TABLE IF NOT EXISTS public.users (
    telegram_id BIGINT PRIMARY KEY,
    username TEXT,
    first_name TEXT,
    last_name TEXT,
    language_code TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_active_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 2. User Balances Table
CREATE TABLE IF NOT EXISTS public.user_balances (
    user_id BIGINT PRIMARY KEY REFERENCES public.users(telegram_id) ON DELETE CASCADE,
    credits_remaining INT NOT NULL DEFAULT 3,
    total_stars_spent INT NOT NULL DEFAULT 0,
    free_credits_reset_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 3. Star Transactions Table
CREATE TABLE IF NOT EXISTS public.star_transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id BIGINT NOT NULL REFERENCES public.users(telegram_id) ON DELETE CASCADE,
    bot_id TEXT NOT NULL,
    stars_amount INT NOT NULL,
    credits_added INT NOT NULL,
    telegram_payment_charge_id TEXT NOT NULL,
    provider_payment_charge_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 4. Bot Events Table (Metrics & Telemetry)
CREATE TABLE IF NOT EXISTS public.bot_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    bot_id TEXT NOT NULL,
    user_id BIGINT NOT NULL,
    event_type TEXT NOT NULL,
    event_name TEXT NOT NULL,
    duration_ms INT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 5. Generation Logs Table
CREATE TABLE IF NOT EXISTS public.generation_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    bot_id TEXT NOT NULL,
    user_id BIGINT NOT NULL,
    model_name TEXT NOT NULL,
    prompt TEXT NOT NULL,
    preset_id TEXT,
    media_url TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    duration_ms INT,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for Fast Query Performance
CREATE INDEX IF NOT EXISTS idx_star_transactions_user_id ON public.star_transactions(user_id);
CREATE INDEX IF NOT EXISTS idx_star_transactions_bot_id ON public.star_transactions(bot_id);
CREATE INDEX IF NOT EXISTS idx_bot_events_bot_id ON public.bot_events(bot_id);
CREATE INDEX IF NOT EXISTS idx_bot_events_user_id ON public.bot_events(user_id);
CREATE INDEX IF NOT EXISTS idx_generation_logs_bot_id ON public.generation_logs(bot_id);
CREATE INDEX IF NOT EXISTS idx_generation_logs_user_id ON public.generation_logs(user_id);

-- 6. Preset Prompts Table (NoSQL Document Store using JSONB)
CREATE TABLE IF NOT EXISTS public.preset_prompts (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    icon TEXT DEFAULT '🎨',
    prompt_template TEXT NOT NULL,
    category TEXT DEFAULT 'popular',
    media_type TEXT DEFAULT 'image',
    default_model TEXT DEFAULT 'google/gemini-2.5-flash-image',
    supports_reference_photo BOOLEAN DEFAULT TRUE,
    is_active BOOLEAN DEFAULT TRUE,
    target_bot_id TEXT DEFAULT 'all',
    data JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_preset_prompts_is_active ON public.preset_prompts(is_active);
CREATE INDEX IF NOT EXISTS idx_preset_prompts_target_bot_id ON public.preset_prompts(target_bot_id);
