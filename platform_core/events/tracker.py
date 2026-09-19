import asyncio
import logging
import time
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from typing import Any, TypeVar

from platform_core.db import AnalyticsEvent, GenerationLog, db, register_flush_callback
from platform_core.events.base import BaseEvent
from platform_core.metrics.prometheus import (
    record_prometheus_event,
    record_prometheus_generation,
    record_prometheus_stars,
)

logger = logging.getLogger(__name__)

TEvent = TypeVar("TEvent", bound=BaseEvent)

BATCH_SIZE = 50
FLUSH_INTERVAL = 2.0

_event_queue: asyncio.Queue[AnalyticsEvent] | None = None
_flush_task: asyncio.Task[None] | None = None
_current_loop: asyncio.AbstractEventLoop | None = None


def get_event_queue() -> asyncio.Queue[AnalyticsEvent]:
    """Returns or initializes the asyncio.Queue for analytics events on the running event loop."""
    global _event_queue, _current_loop
    try:
        current_loop = asyncio.get_running_loop()
    except RuntimeError:
        current_loop = None

    if _event_queue is None or (_current_loop is not None and _current_loop != current_loop):
        _event_queue = asyncio.Queue()
        _current_loop = current_loop
    return _event_queue


def _ensure_flush_task() -> None:
    """Ensures the background flush loop task is active."""
    global _flush_task
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return

    if _flush_task is None or _flush_task.done() or _flush_task.get_loop() != loop:
        _flush_task = loop.create_task(_flush_loop(), name="analytics_event_flush_loop")


async def _flush_batch(batch: list[AnalyticsEvent]) -> None:
    """Flushes a batch of events to the database."""
    if not batch:
        return
    try:
        await db.track_events_batch(batch)
    except Exception as e:
        logger.error(f"Failed to persist batch of {len(batch)} events: {e}")


async def _flush_loop() -> None:
    """
    Background worker loop that flushes events in batches using db.track_events_batch()
    every 2 seconds or when the batch reaches 50 events.
    """
    queue = get_event_queue()
    batch: list[AnalyticsEvent] = []

    while True:
        try:
            # 1. Wait for the first item to arrive (0% CPU when idle)
            first_event = await queue.get()
            batch.append(first_event)
            queue.task_done()

            # 2. Drain any already-pending events up to BATCH_SIZE without delay
            while len(batch) < BATCH_SIZE and not queue.empty():
                try:
                    batch.append(queue.get_nowait())
                    queue.task_done()
                except (asyncio.QueueEmpty, ValueError):
                    break

            # 3. If batch is still less than BATCH_SIZE, wait up to FLUSH_INTERVAL
            deadline = time.monotonic() + FLUSH_INTERVAL
            while len(batch) < BATCH_SIZE:
                timeout = deadline - time.monotonic()
                if timeout <= 0:
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=timeout)
                    batch.append(event)
                    queue.task_done()
                except asyncio.TimeoutError:
                    break

            # 4. Flush the batch
            if batch:
                await _flush_batch(batch)
                batch = []

        except asyncio.CancelledError:
            # On shutdown / cancellation, drain remaining queue and flush
            while not queue.empty():
                try:
                    batch.append(queue.get_nowait())
                    queue.task_done()
                except (asyncio.QueueEmpty, ValueError):
                    break
            if batch:
                await _flush_batch(batch)
            raise
        except Exception as e:
            logger.error(f"Error in event tracker flush loop: {e}")
            if batch:
                await _flush_batch(batch)
                batch = []
            await asyncio.sleep(0.5)


async def flush_events() -> None:
    """Flushes all currently buffered events immediately."""
    queue = get_event_queue()
    batch: list[AnalyticsEvent] = []
    while not queue.empty():
        try:
            batch.append(queue.get_nowait())
            queue.task_done()
        except (asyncio.QueueEmpty, ValueError):
            break
    if batch:
        await _flush_batch(batch)


async def shutdown_event_tracker() -> None:
    """Gracefully flushes remaining events and cancels the background flush task."""
    global _flush_task
    await flush_events()
    if _flush_task and not _flush_task.done():
        _flush_task.cancel()
        try:
            await _flush_task
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.warning(f"Error during event tracker shutdown: {e}")
        _flush_task = None


# Register flush callback with db pre-query hook
register_flush_callback(flush_events)


class EventTracker:
    """
    Modular Event Tracker that receives typed BaseEvent data classes,
    performs standard serialization, and dispatches them to an asynchronous
    batch buffer and Prometheus telemetry.
    """

    def __init__(
        self,
        bot_id: str = "default",
        enabled: bool = True,
        default_properties: dict[str, Any] | None = None,
    ):
        self.bot_id = bot_id
        self.enabled = enabled
        self.default_properties = default_properties or {}

    def with_properties(self, **properties: Any) -> "EventTracker":
        """Returns a child tracker with merged default properties."""
        merged = {**self.default_properties, **properties}
        return EventTracker(
            bot_id=self.bot_id,
            enabled=self.enabled,
            default_properties=merged,
        )

    async def flush(self) -> None:
        """Immediately flushes any buffered events to the database."""
        await flush_events()

    async def aclose(self) -> None:
        """Flushes events and cleans up."""
        await flush_events()

    async def track(self, event: BaseEvent) -> AnalyticsEvent:
        """
        Record any typed event dataclass that inherits from BaseEvent.
        Places event into an in-memory queue for batched non-blocking database persistence.
        """
        if not event.bot_id:
            event.bot_id = self.bot_id

        # If tracking is disabled for this tracker instance, no-op cleanly
        if not self.enabled:
            return event.to_analytics_event(default_bot_id=self.bot_id)

        # Convert to DB AnalyticsEvent representation
        analytics_event = event.to_analytics_event(default_bot_id=self.bot_id)

        # Merge tracker-level default properties if any
        if self.default_properties:
            analytics_event.properties = {**self.default_properties, **analytics_event.properties}

        # 1. Dispatch to Prometheus telemetry (non-blocking in-memory accumulator)
        try:
            from platform_core.events.generation import GenerationEvent
            from platform_core.events.payment import PaymentEvent

            if isinstance(event, GenerationEvent):
                record_prometheus_generation(
                    bot_id=event.bot_id or self.bot_id,
                    model=event.model_name,
                    status=event.status,
                    duration_ms=event.duration_ms or 0,
                )
                # Also log to generation_logs table for user history
                user_id_int = int(event.distinct_id) if str(event.distinct_id).isdigit() else 0
                await db.log_generation(
                    GenerationLog(
                        bot_id=event.bot_id or self.bot_id,
                        user_id=user_id_int,
                        model_name=event.model_name,
                        prompt=event.prompt,
                        preset_id=event.preset_id,
                        media_url=event.media_url,
                        status=event.status,
                        duration_ms=event.duration_ms,
                        error_message=event.error_message,
                    )
                )
            elif isinstance(event, PaymentEvent):
                record_prometheus_stars(event.bot_id or self.bot_id, event.stars_amount)
            else:
                record_prometheus_event(
                    bot_id=event.bot_id or self.bot_id,
                    event_type=event.event_name,
                    event_name=event.get_event_name(),
                    duration_ms=event.duration_ms or 0,
                )
        except Exception as e:
            logger.debug(f"Prometheus metric error: {e}")

        # 2. Persist event to Database via non-blocking asynchronous batch buffer
        try:
            queue = get_event_queue()
            _ensure_flush_task()
            queue.put_nowait(analytics_event)
        except Exception as e:
            logger.error(f"Error queueing event '{event.get_event_name()}': {e}")

        return analytics_event

    async def track_batch(self, events: Sequence[BaseEvent]) -> None:
        """Record multiple typed events in batch."""
        for e in events:
            await self.track(e)

    @asynccontextmanager
    async def timed(
        self, event_cls: type[TEvent], distinct_id: int | str, **initial_fields: Any
    ) -> AsyncIterator[dict[str, Any]]:
        """
        Async context manager that measures duration for an event dataclass,
        catches exceptions to record errors, and automatically tracks the event upon exit.
        """
        start_time = time.perf_counter()
        fields: dict[str, Any] = dict(initial_fields)
        status = "success"

        try:
            yield fields
        except Exception as exc:
            status = "error"
            if "error_message" in event_cls.model_fields:
                fields["error_message"] = str(exc)
            if "error_type" in event_cls.model_fields:
                fields["error_type"] = exc.__class__.__name__
            raise
        finally:
            elapsed_ms = max(0, int((time.perf_counter() - start_time) * 1000))
            fields["distinct_id"] = distinct_id
            fields["bot_id"] = fields.get("bot_id") or self.bot_id
            fields["duration_ms"] = elapsed_ms
            fields["status"] = status
            event_instance = event_cls(**fields)
            await self.track(event_instance)


# Global tracker registry
_trackers: dict[str, EventTracker] = {}


def get_tracker(
    bot_id: str = "default", enabled: bool = True, **default_properties: Any
) -> EventTracker:
    """Get or create an EventTracker instance scoped to a bot_id."""
    if bot_id not in _trackers or default_properties or not enabled:
        _trackers[bot_id] = EventTracker(
            bot_id=bot_id,
            enabled=enabled,
            default_properties=default_properties,
        )
    return _trackers[bot_id]
