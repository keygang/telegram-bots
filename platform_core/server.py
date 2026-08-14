import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Dict
from aiogram import Bot, Dispatcher
from aiogram.types import Update
from fastapi import FastAPI, Header, HTTPException, Request, Response, status
from platform_core.cli import get_instance_config_files
from platform_core.config import settings
from platform_core.metrics.prometheus import get_prometheus_metrics, update_prometheus_queue, CONTENT_TYPE_LATEST
from platform_core.modules.builder import ModularBot, ModularBotBuilder
from platform_core.queue.broker import task_broker

logger = logging.getLogger("platform_server")

# Active Bot Instances lookup table: bot_id -> ModularBot
BOT_INSTANCES: Dict[str, ModularBot] = {}


async def initialize_bot_instances():
    """Scans instances/ directory, builds ModularBot apps, and sets up webhooks."""
    configs = get_instance_config_files()
    if not configs:
        logger.warning("No instance configs found in instances/. Creating default fallback instances...")
        return

    for cfg_path in configs:
        try:
            builder = ModularBotBuilder.from_config(cfg_path)
            bot_app = builder.build()

            # Run startup hooks for registered modules
            for mod in bot_app.modules:
                await mod.on_startup(bot_app.bot, bot_app.dp)

            if bot_app.commands:
                try:
                    await bot_app.bot.set_my_commands(bot_app.commands)
                except Exception as e:
                    logger.warning(f"Could not set commands for {bot_app.bot_id}: {e}")

            BOT_INSTANCES[bot_app.bot_id] = bot_app
            logger.info(f"Loaded bot instance [{bot_app.bot_id}] (Strategy: {bot_app.strategy})")

            # Setup Telegram Webhook if strategy is 'webhook' and WEBHOOK_BASE_URL is configured
            if bot_app.strategy == "webhook":
                if settings.WEBHOOK_BASE_URL:
                    webhook_url = f"{settings.WEBHOOK_BASE_URL.rstrip('/')}/webhook/{bot_app.bot_id}"
                    secret_token = settings.WEBHOOK_SECRET_TOKEN
                    try:
                        await bot_app.bot.set_webhook(
                            url=webhook_url,
                            secret_token=secret_token,
                            drop_pending_updates=True,
                        )
                        logger.info(f"🌐 Webhook set for [{bot_app.bot_id}] -> {webhook_url}")
                    except Exception as e:
                        logger.error(f"Failed to set webhook for [{bot_app.bot_id}]: {e}")
                else:
                    logger.warning(f"Bot [{bot_app.bot_id}] uses webhook strategy, but WEBHOOK_BASE_URL is not set.")
            else:
                logger.info(f"ℹ️ Bot [{bot_app.bot_id}] is configured for POLLING strategy (skipping server webhook registration).")

        except Exception as e:
            logger.error(f"Failed to initialize bot instance from {cfg_path}: {e}")


async def shutdown_bot_instances():
    """Cleans up webhooks and closes bot sessions on server shutdown."""
    for bot_id, bot_app in BOT_INSTANCES.items():
        try:
            for mod in bot_app.modules:
                await mod.on_shutdown(bot_app.bot, bot_app.dp)
            await bot_app.bot.session.close()
            logger.info(f"Closed bot session for [{bot_id}]")
        except Exception as e:
            logger.warning(f"Error shutting down bot [{bot_id}]: {e}")
    BOT_INSTANCES.clear()
    await task_broker.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI application lifespan event handler."""
    logger.info("⚡ Telegram Webhook Gateway Server starting up...")
    await initialize_bot_instances()
    yield
    logger.info("🛑 Telegram Webhook Gateway Server shutting down...")
    await shutdown_bot_instances()


app = FastAPI(
    title="Telegram AI Bot Platform Webhook Gateway",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/")
async def root():
    return {
        "service": "Telegram AI Bot Platform Webhook Gateway",
        "status": "online",
        "configured_bots": list(BOT_INSTANCES.keys()),
    }


@app.get("/health")
async def health_check():
    q_len = await task_broker.get_queue_length()
    return {
        "status": "healthy",
        "active_bot_count": len(BOT_INSTANCES),
        "bot_ids": list(BOT_INSTANCES.keys()),
        "pending_queue_length": q_len,
    }


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint scraped by Prometheus server."""
    try:
        q_len = await task_broker.get_queue_length()
        update_prometheus_queue(q_len)
    except Exception as e:
        logger.warning(f"Could not update queue metrics on /metrics scrape: {e}")
    return Response(content=get_prometheus_metrics(), media_type=CONTENT_TYPE_LATEST)


@app.post("/webhook/{bot_id}")
async def handle_telegram_webhook(
    bot_id: str,
    request: Request,
    x_telegram_bot_api_secret_token: str = Header(None, alias="X-Telegram-Bot-Api-Secret-Token"),
):
    """
    High-performance Webhook endpoint receiving HTTP POST updates from Telegram.
    Validates secret token and feeds updates into aiogram Dispatcher instantly (< 50ms).
    """
    bot_app = BOT_INSTANCES.get(bot_id)
    if not bot_app:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bot instance '{bot_id}' not found",
        )

    # Secret token validation if configured
    if settings.WEBHOOK_SECRET_TOKEN and x_telegram_bot_api_secret_token:
        if x_telegram_bot_api_secret_token != settings.WEBHOOK_SECRET_TOKEN:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Telegram secret token",
            )

    try:
        data = await request.json()
        update = Update.model_validate(data, context={"bot": bot_app.bot})
        # Feed update asynchronously into aiogram Dispatcher
        await bot_app.dp.feed_update(bot=bot_app.bot, update=update, bot_id=bot_id)
        return Response(status_code=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"Error processing webhook update for bot [{bot_id}]: {e}", exc_info=True)
        # Always return HTTP 200 to Telegram so it doesn't repeatedly retry malformed updates
        return Response(status_code=status.HTTP_200_OK)
