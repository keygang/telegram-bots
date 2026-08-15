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
    stream_message_id: str | None = None  # Redis Stream entry ID for explicit XACK

    def to_json(self) -> str:
        return self.model_dump_json()

    @classmethod
    def from_json(cls, json_str: str) -> "GenerationJob":
        return cls.model_validate_json(json_str)


class TaskQueueBroker:
    """
    Production-grade Redis Streams task queue broker with consumer groups,
    explicit message acknowledgments (XACK), auto-claim for worker crash recovery,
    and transparent in-memory fallback.
    """

    def __init__(
        self,
        redis_url: str | None = None,
        queue_name: str | None = None,
        group_name: str = "telegram_workers_group",
    ):
        self.redis_url = redis_url or settings.REDIS_URL
        self.stream_key = queue_name or settings.QUEUE_NAME or "telegram_tasks:stream"
        self.group_name = group_name
        self._redis_client: Any | None = None
        self._fallback_queue: asyncio.Queue = asyncio.Queue()
        self._use_fallback = False
        self._group_initialized = False

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

        if self._redis_client and not self._group_initialized:
            try:
                # Create consumer group if not already created
                await self._redis_client.xgroup_create(
                    name=self.stream_key,
                    groupname=self.group_name,
                    id="0",
                    mkstream=True,
                )
                self._group_initialized = True
                logger.info(f"Initialized Redis Stream consumer group '{self.group_name}'")
            except Exception as e:
                # Group already exists or other error
                if "BUSYGROUP" in str(e):
                    self._group_initialized = True
                else:
                    logger.debug(f"Redis consumer group status: {e}")
                    self._group_initialized = True

        return self._redis_client

    async def enqueue_job(self, job: GenerationJob) -> bool:
        """Pushes a generation job onto the Redis Stream."""
        client = await self._get_client()
        payload = job.to_json()

        if client:
            try:
                msg_id = await client.xadd(self.stream_key, {"payload": payload})
                job.stream_message_id = msg_id
                logger.info(
                    f"Enqueued job {job.job_id} (stream_id: {msg_id}) to Redis stream '{self.stream_key}'"
                )
                return True
            except Exception as e:
                logger.error(f"Redis stream xadd failed ({e}), using in-memory fallback.")
                self._use_fallback = True

        await self._fallback_queue.put(payload)
        logger.info(f"Enqueued job {job.job_id} to In-Memory queue")
        return True

    async def dequeue_job(
        self, consumer_name: str = "worker_1", timeout: float = 2.0
    ) -> GenerationJob | None:
        """Pops a generation job from Redis Stream using consumer groups and auto-claim."""
        client = await self._get_client()

        if client:
            try:
                # 1. Attempt to claim abandoned/stalled messages from crashed workers (> 60s idle)
                with contextlib.suppress(Exception):
                    claimed = await client.xautoclaim(
                        name=self.stream_key,
                        groupname=self.group_name,
                        consumername=consumer_name,
                        min_idle_time=60000,
                        start_id="0-0",
                        count=1,
                    )
                    if claimed and len(claimed) > 1 and claimed[1]:
                        msg_id, fields = claimed[1][0]
                        if fields and "payload" in fields:
                            job = GenerationJob.from_json(fields["payload"])
                            job.stream_message_id = msg_id
                            logger.info(f"Auto-claimed abandoned job {job.job_id} ({msg_id})")
                            return job

                # 2. Read new unread messages for this consumer group
                block_ms = int(max(1, timeout) * 1000)
                streams_res = await client.xreadgroup(
                    groupname=self.group_name,
                    consumername=consumer_name,
                    streams={self.stream_key: ">"},
                    count=1,
                    block=block_ms,
                )
                if streams_res:
                    for _stream, messages in streams_res:
                        for msg_id, fields in messages:
                            if fields and "payload" in fields:
                                job = GenerationJob.from_json(fields["payload"])
                                job.stream_message_id = msg_id
                                return job
                return None
            except Exception as e:
                logger.error(f"Redis stream dequeue error ({e}), falling back to in-memory queue.")
                self._use_fallback = True

        try:
            payload = await asyncio.wait_for(self._fallback_queue.get(), timeout=timeout)
            return GenerationJob.from_json(payload)
        except TimeoutError:
            return None

    async def ack_job(self, job: GenerationJob) -> bool:
        """Acknowledges and removes processed job from Redis stream."""
        client = await self._get_client()
        if client and job.stream_message_id:
            try:
                await client.xack(self.stream_key, self.group_name, job.stream_message_id)
                await client.xdel(self.stream_key, job.stream_message_id)
                logger.debug(f"Acknowledged job {job.job_id} ({job.stream_message_id})")
                return True
            except Exception as e:
                logger.warning(f"Failed to ack job {job.job_id}: {e}")
                return False
        return True

    async def get_queue_length(self) -> int:
        """Returns current pending queue length."""
        client = await self._get_client()
        if client:
            with contextlib.suppress(Exception):
                return await client.xlen(self.stream_key)
        return self._fallback_queue.qsize()

    async def close(self) -> None:
        """Closes connection pools."""
        if self._redis_client:
            with contextlib.suppress(Exception):
                await self._redis_client.close()
            self._redis_client = None


# Global singleton instance
task_broker = TaskQueueBroker()
