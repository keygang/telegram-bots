import asyncio
import contextlib
import html
import logging
import os
import time
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import url2pathname

import yaml
from aiogram import Bot

from platform_core.config import settings
from platform_core.db import BotEvent, GenerationLog, db
from platform_core.generators.base import GenerationRequest, GenerationStatus
from platform_core.generators.factory import GeneratorFactory
from platform_core.metrics.prometheus import record_prometheus_generation
from platform_core.queue.broker import GenerationJob, TaskQueueBroker, task_broker
from platform_core.storage.media import MediaStorageManager

logger = logging.getLogger(__name__)


def resolve_bot_token(bot_id: str) -> str | None:
    """
    Resolves the Telegram Bot API token for a given bot_id.
    Checks:
    1. Direct environment variable (e.g. IMAGE_BOT_1_TOKEN, BOT_TOKEN_IMAGE_BOT_1, IMAGE_BOT_TOKEN).
    2. Instance YAML file under `instances/{bot_id}.yaml`.
    3. PlatformSettings attributes or fallbacks.
    """
    clean_id = bot_id.replace("-", "_").upper()
    env_candidates = [
        f"{clean_id}_TOKEN",
        f"BOT_TOKEN_{clean_id}",
        f"TELEGRAM_BOT_TOKEN_{clean_id}",
        clean_id,
    ]
    for env_name in env_candidates:
        val = os.getenv(env_name)
        if val and ":" in val:
            return val

    # Check instance config YAML under instances/
    try:
        yaml_candidates = [
            Path("instances") / f"{bot_id}.yaml",
            Path("instances") / f"{bot_id.replace('-', '_')}.yaml",
        ]
        for ypath in yaml_candidates:
            if ypath.is_file():
                with open(ypath, encoding="utf-8") as f:
                    cfg = yaml.safe_load(f) or {}
                if cfg.get("token") and ":" in str(cfg["token"]):
                    return str(cfg["token"])
                token_env = cfg.get("token_env")
                if token_env:
                    val = os.getenv(token_env)
                    if val and ":" in val:
                        return val
    except Exception as e:
        logger.debug(f"Error checking instance config for bot_id {bot_id}: {e}")

    # Check PlatformSettings attributes
    if "admin" in bot_id.lower() and getattr(settings, "ADMIN_BOT_TOKEN", None):
        return settings.ADMIN_BOT_TOKEN
    specific_token = getattr(settings, f"{clean_id}_TOKEN", None)
    if specific_token and ":" in str(specific_token):
        return specific_token
    if getattr(settings, "IMAGE_BOT_TOKEN", None):
        return settings.IMAGE_BOT_TOKEN

    return None


class BotPool:
    """
    Persistent connection pool for aiogram.Bot instances.
    Reuses Bot instances and underlying aiohttp ClientSessions across jobs
    to eliminate TCP/TLS connection handshake latency.
    """

    def __init__(self):
        self._bots: dict[str, Bot] = {}

    def get_bot(self, token: str) -> Bot:
        if token not in self._bots:
            self._bots[token] = Bot(token=token)
        return self._bots[token]

    async def close_all(self) -> None:
        for _token, bot in list(self._bots.items()):
            with contextlib.suppress(Exception):
                await bot.session.close()
        self._bots.clear()


class AIWorkerPool:
    """
    Decoupled Background Worker process pool for executing AI Media Generations.
    Pops jobs from TaskQueueBroker and pushes results to Telegram Bot API.
    Reuses persistent Bot HTTP client sessions and acknowledges stream jobs.
    """

    def __init__(
        self,
        broker: TaskQueueBroker | None = None,
        concurrency: int = 4,
        force_mock: bool = False,
    ):
        self.broker = broker or task_broker
        self.concurrency = concurrency
        self.force_mock = force_mock
        self.bot_pool = BotPool()
        self._running = False
        self._tasks: list[asyncio.Task[None]] = []

    @property
    def is_running(self) -> bool:
        return self._running

    async def process_job(self, job: GenerationJob) -> None:
        """Processes a single AI generation job."""
        logger.info(
            f"⚙️ Worker processing job [{job.job_id}] for user {job.user_id} (Model: {job.model_name})"
        )
        token = resolve_bot_token(job.bot_id)
        if not token:
            logger.error(
                f"❌ Cannot process job [{job.job_id}]: Telegram bot token for bot_id '{job.bot_id}' not found."
            )
            # Refund user credits and log generation failure
            await db.add_user_credits(
                user_id=job.user_id,
                bot_id=job.bot_id,
                stars_paid=0,
                credits_to_add=job.cost,
                telegram_charge_id="refund",
            )
            record_prometheus_generation(job.bot_id, "failed", job.model_name)
            await db.record_event(
                BotEvent(
                    bot_id=job.bot_id,
                    user_id=job.user_id,
                    event_type="generation_failed",
                    event_name=job.media_type,
                    duration_ms=0,
                )
            )
            await db.log_generation(
                GenerationLog(
                    bot_id=job.bot_id,
                    user_id=job.user_id,
                    model_name=job.model_name,
                    prompt=job.prompt,
                    preset_id=job.preset_id,
                    status="failed",
                    duration_ms=0,
                    error_message=f"Bot token not found for bot_id: {job.bot_id}",
                )
            )
            await self.broker.ack_job(job)
            return

        bot = self.bot_pool.get_bot(token)
        start_time = time.time()

        try:
            # Load reference photo from local path/URI if present
            ref_bytes = None
            if job.photo_path:
                try:
                    parsed = urlparse(job.photo_path)
                    if parsed.scheme == "file":
                        file_path = Path(url2pathname(parsed.path))
                    else:
                        file_path = Path(job.photo_path)

                    if file_path.exists():
                        ref_bytes = file_path.read_bytes()
                    else:
                        logger.warning(
                            f"Reference photo file does not exist at '{file_path}' for job {job.job_id}"
                        )
                except Exception as e:
                    logger.warning(
                        f"Failed to load reference photo from '{job.photo_path}' for job {job.job_id}: {e}"
                    )

            # Instantiate appropriate generator (Replicate, LiteLLM, or Mock)
            generator = GeneratorFactory.get_generator(force_mock=self.force_mock)

            gen_req = GenerationRequest(
                prompt=job.prompt,
                negative_prompt=job.negative_prompt,
                model_name=job.model_name,
                reference_photo_bytes=ref_bytes,
                extra_params=job.extra_params,
            )

            res = await generator.generate(gen_req)
            elapsed_ms = res.duration_ms or int((time.time() - start_time) * 1000)

            if res.status == GenerationStatus.SUCCESS and res.media_urls:
                caption = f"✨ <b>{html.escape(job.prompt)}</b>"
                media_url_logged = res.media_urls[0]
                media_input = MediaStorageManager.get_input_file(media_url_logged)

                # Send media to user
                if job.media_type == "video":
                    await bot.send_video(
                        chat_id=job.chat_id,
                        video=media_input,
                        caption=caption,
                        parse_mode="HTML",
                    )
                else:
                    await bot.send_photo(
                        chat_id=job.chat_id,
                        photo=media_input,
                        caption=caption,
                        parse_mode="HTML",
                    )

                # Delete temporary status message
                with contextlib.suppress(Exception):
                    await bot.delete_message(chat_id=job.chat_id, message_id=job.status_message_id)

                # Record metrics and log transaction
                record_prometheus_generation(job.bot_id, "success", job.model_name)
                await db.record_event(
                    BotEvent(
                        bot_id=job.bot_id,
                        user_id=job.user_id,
                        event_type="generation_success",
                        event_name=job.media_type,
                        duration_ms=elapsed_ms,
                    )
                )
                await db.log_generation(
                    GenerationLog(
                        bot_id=job.bot_id,
                        user_id=job.user_id,
                        model_name=job.model_name,
                        prompt=job.prompt,
                        preset_id=job.preset_id,
                        media_url=media_url_logged,
                        status="success",
                        duration_ms=elapsed_ms,
                    )
                )
                logger.info(f"✅ Job [{job.job_id}] completed successfully in {elapsed_ms}ms")

            else:
                error_msg = res.error_message or "Unknown AI generation error"
                logger.error(f"❌ Job [{job.job_id}] failed: {error_msg}")

                # Edit status message to notify user of failure
                try:
                    await bot.edit_message_text(
                        chat_id=job.chat_id,
                        message_id=job.status_message_id,
                        text=f"❌ <b>Generation Failed</b>\n\n<i>{html.escape(error_msg)}</i>\n\n💰 <i>Your {job.cost} credit(s) have been refunded.</i>",
                        parse_mode="HTML",
                    )
                except Exception as e:
                    logger.warning(f"Could not edit status message: {e}")

                # Refund credits to user balance
                await db.add_user_credits(
                    user_id=job.user_id,
                    bot_id=job.bot_id,
                    stars_paid=0,
                    credits_to_add=job.cost,
                    telegram_charge_id="refund",
                )

                record_prometheus_generation(job.bot_id, "failed", job.model_name)
                await db.record_event(
                    BotEvent(
                        bot_id=job.bot_id,
                        user_id=job.user_id,
                        event_type="generation_failed",
                        event_name=job.media_type,
                        duration_ms=elapsed_ms,
                    )
                )
                await db.log_generation(
                    GenerationLog(
                        bot_id=job.bot_id,
                        user_id=job.user_id,
                        model_name=job.model_name,
                        prompt=job.prompt,
                        preset_id=job.preset_id,
                        status="failed",
                        duration_ms=elapsed_ms,
                        error_message=error_msg,
                    )
                )

        except Exception as e:
            logger.error(f"Fatal error processing job {job.job_id}: {e}", exc_info=True)
            with contextlib.suppress(Exception):
                await bot.edit_message_text(
                    chat_id=job.chat_id,
                    message_id=job.status_message_id,
                    text=f"❌ <b>Unexpected System Error</b>: <i>{html.escape(str(e))}</i>\n\n💰 <i>Credits refunded.</i>",
                    parse_mode="HTML",
                )
            await db.add_user_credits(
                user_id=job.user_id,
                bot_id=job.bot_id,
                stars_paid=0,
                credits_to_add=job.cost,
                telegram_charge_id="refund",
            )
        finally:
            # Acknowledge job completion from Redis Stream
            await self.broker.ack_job(job)

    async def _worker_loop(self, worker_idx: int) -> None:
        logger.info(f"🚀 AI Worker #{worker_idx} started")
        consumer_name = f"worker_{worker_idx}"
        while self._running:
            try:
                job = await self.broker.dequeue_job(consumer_name=consumer_name, timeout=1.5)
                if job:
                    await self.process_job(job)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker #{worker_idx} encountered error in main loop: {e}")
                await asyncio.sleep(1)

        logger.info(f"🛑 AI Worker #{worker_idx} stopped")

    async def start(self) -> None:
        """Starts worker tasks up to configured concurrency."""
        self._running = True
        logger.info(
            f"🔥 Starting AIWorkerPool with concurrency={self.concurrency} (Mock={self.force_mock})"
        )
        self._tasks = [
            asyncio.create_task(self._worker_loop(i + 1)) for i in range(self.concurrency)
        ]
        await asyncio.gather(*self._tasks, return_exceptions=True)

    async def stop(self) -> None:
        """Stops worker tasks and cleans up bot connection pools gracefully."""
        self._running = False
        for t in self._tasks:
            t.cancel()
        await self.bot_pool.close_all()
        await self.broker.close()
        logger.info("AIWorkerPool shut down gracefully.")
