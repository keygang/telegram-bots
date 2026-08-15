import asyncio
import base64
import contextlib
import logging
import time

from aiogram import Bot
from aiogram.types import BufferedInputFile, URLInputFile

from platform_core.db import BotEvent, GenerationLog, db
from platform_core.generators.base import GenerationRequest
from platform_core.generators.factory import GeneratorFactory
from platform_core.metrics.prometheus import record_prometheus_generation
from platform_core.queue.broker import GenerationJob, TaskQueueBroker, task_broker

logger = logging.getLogger(__name__)


class AIWorkerPool:
    """
    Decoupled Background Worker process pool for executing AI Media Generations.
    Pops jobs from TaskQueueBroker and pushes results to Telegram Bot API.
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
        bot = Bot(token=job.bot_token)
        start_time = time.time()

        try:
            # Decode reference photo if present
            ref_bytes = None
            if job.reference_photo_b64:
                try:
                    ref_bytes = base64.b64decode(job.reference_photo_b64)
                except Exception as e:
                    logger.warning(f"Failed to decode reference photo for job {job.job_id}: {e}")

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

            if res.status == "success" and (res.media_urls or res.media_bytes):
                caption = f"✨ *{job.prompt}*"

                if res.media_bytes:
                    media_input = BufferedInputFile(res.media_bytes, filename="generated.png")
                    media_url_logged = "bytes://generated.png"
                else:
                    media_input = URLInputFile(res.media_urls[0])
                    media_url_logged = res.media_urls[0]

                # Send media to user
                if job.media_type == "video":
                    await bot.send_video(
                        chat_id=job.chat_id,
                        video=media_input,
                        caption=caption,
                        parse_mode="Markdown",
                    )
                else:
                    await bot.send_photo(
                        chat_id=job.chat_id,
                        photo=media_input,
                        caption=caption,
                        parse_mode="Markdown",
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
                        text=f"❌ *Generation Failed*\n\n_{error_msg}_\n\n💰 _Your {job.cost} credit(s) have been refunded._",
                        parse_mode="Markdown",
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
                    text=f"❌ *Unexpected System Error*: _{e!s}_\n\n💰 _Credits refunded._",
                    parse_mode="Markdown",
                )
                await db.add_user_credits(
                    user_id=job.user_id,
                    bot_id=job.bot_id,
                    stars_paid=0,
                    credits_to_add=job.cost,
                    telegram_charge_id="refund",
                )
        finally:
            await bot.session.close()

    async def _worker_loop(self, worker_idx: int) -> None:
        logger.info(f"🚀 AI Worker #{worker_idx} started")
        while self._running:
            try:
                job = await self.broker.dequeue_job(timeout=1.5)
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
        """Stops worker tasks gracefully."""
        self._running = False
        for t in self._tasks:
            t.cancel()
        await self.broker.close()
        logger.info("AIWorkerPool shut down gracefully.")
