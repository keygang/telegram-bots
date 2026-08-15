import asyncio
import contextlib
import logging
import time
from typing import Any

from pydantic import BaseModel, Field

try:
    import redis.asyncio as aioredis
except ImportError:
    aioredis = None

from platform_core.config import settings

logger = logging.getLogger(__name__)


class GenerationJob(BaseModel):
    """
    Serializable payload representing an offloaded AI media generation request.
    Strictly typed Pydantic data structure for fast and safe JSON serialization.
    """

    job_id: str
    bot_id: str
    bot_token: str
    user_id: int
    chat_id: int
    status_message_id: int
    prompt: str
    model_name: str
    media_type: str = "image"  # "image" or "video"
    negative_prompt: str | None = None
    cost: int = 1
    reference_photo_b64: str | None = None
    extra_params: dict[str, Any] = Field(default_factory=dict)
    created_at: float = Field(default_factory=time.time)

    def to_json(self) -> str:
        return self.model_dump_json()

    @classmethod
    def from_json(cls, json_str: str) -> "GenerationJob":
        return cls.model_validate_json(json_str)


class TaskQueueBroker:
    """
    Redis-backed task queue broker with automatic in-memory fallback
    when Redis is unavailable or offline mode is requested.
    """

    def __init__(self, redis_url: str | None = None, queue_name: str | None = None):
        self.redis_url = redis_url or settings.REDIS_URL
        self.queue_name = queue_name or settings.QUEUE_NAME
        self._redis_client: Any | None = None
        self._fallback_queue: asyncio.Queue = asyncio.Queue()
        self._use_fallback = False

    async def _get_client(self):
        if self._use_fallback or aioredis is None:
            return None

        if self._redis_client is None and self.redis_url:
            try:
                client = aioredis.from_url(self.redis_url, decode_responses=True)
                await client.ping()
                self._redis_client = client
                logger.info(f"Connected to Redis Task Broker at {self.redis_url}")
            except Exception as e:
                logger.warning(
                    f"Could not connect to Redis ({e}). Falling back to In-Memory Queue."
                )
                self._use_fallback = True
                self._redis_client = None

        return self._redis_client

    async def enqueue_job(self, job: GenerationJob) -> bool:
        """Pushes a generation job onto the task queue."""
        client = await self._get_client()
        payload = job.to_json()

        if client:
            try:
                await client.rpush(self.queue_name, payload)
                logger.info(f"Enqueued job {job.job_id} to Redis queue '{self.queue_name}'")
                return True
            except Exception as e:
                logger.error(f"Redis enqueue failed ({e}), using in-memory fallback.")
                self._use_fallback = True

        await self._fallback_queue.put(payload)
        logger.info(f"Enqueued job {job.job_id} to In-Memory queue")
        return True

    async def dequeue_job(self, timeout: float = 2.0) -> GenerationJob | None:
        """Pops a generation job from the task queue."""
        client = await self._get_client()

        if client:
            try:
                # blpop returns tuple (queue_name, item) or None on timeout
                res = await client.blpop(self.queue_name, timeout=int(max(1, timeout)))
                if res:
                    _, payload = res
                    return GenerationJob.from_json(payload)
                return None
            except Exception as e:
                logger.error(f"Redis dequeue error ({e}), falling back to in-memory queue.")
                self._use_fallback = True

        try:
            payload = await asyncio.wait_for(self._fallback_queue.get(), timeout=timeout)
            return GenerationJob.from_json(payload)
        except TimeoutError:
            return None

    async def get_queue_length(self) -> int:
        """Returns current pending queue length."""
        client = await self._get_client()
        if client:
            with contextlib.suppress(Exception):
                return await client.llen(self.queue_name)
        return self._fallback_queue.qsize()

    async def close(self) -> None:
        """Closes connection pools."""
        if self._redis_client:
            with contextlib.suppress(Exception):
                await self._redis_client.close()
            self._redis_client = None


# Global singleton instance
task_broker = TaskQueueBroker()
