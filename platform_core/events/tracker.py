import logging
import time
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from typing import Any, TypeVar

from platform_core.db import AnalyticsEvent, GenerationLog, db
from platform_core.events.base import BaseEvent
from platform_core.metrics.prometheus import (
    record_prometheus_event,
    record_prometheus_generation,
    record_prometheus_stars,
)

logger = logging.getLogger(__name__)

TEvent = TypeVar("TEvent", bound=BaseEvent)


class EventTracker:
    """
    Modular Event Tracker that receives typed BaseEvent data classes,
    performs standard serialization, and dispatches them to the PostgreSQL/PostHog
    event store and Prometheus telemetry.
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

    async def track(self, event: BaseEvent) -> AnalyticsEvent:
        """
        Record any typed event dataclass that inherits from BaseEvent.
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

        # 1. Dispatch to Prometheus telemetry
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

        # 2. Persist event to Database / in-memory store
        try:
            await db.track_event(analytics_event)
        except Exception as e:
            logger.error(f"Error persisting event '{event.get_event_name()}': {e}")

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
