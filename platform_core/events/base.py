from abc import ABC
from datetime import UTC, datetime
from typing import Any, ClassVar

from pydantic import BaseModel, Field

from platform_core.db.models import AnalyticsEvent


def utc_now() -> datetime:
    return datetime.now(UTC)


class BaseEvent(BaseModel, ABC):
    """
    Abstract Base Class for all Telemetry & Analytics Events.

    Contains standard envelope attributes common to all events. Subclasses
    define event-specific strongly-typed attributes that get automatically
    serialized into the JSON properties payload for PostHog/Postgres analytics.
    """

    event_name: ClassVar[str] = "custom_event"

    distinct_id: int | str
    bot_id: str | None = None
    duration_ms: int | None = None
    status: str = "success"  # "success", "error", "pending"
    timestamp: datetime = Field(default_factory=utc_now)

    def get_event_name(self) -> str:
        """Returns the identifier name for this event type."""
        return self.event_name

    def to_properties(self) -> dict[str, Any]:
        """
        Extract all non-envelope fields as the event's JSONB properties dictionary.
        """
        envelope_keys = {"distinct_id", "bot_id", "duration_ms", "status", "timestamp"}
        data = self.model_dump(mode="json")
        props = {k: v for k, v in data.items() if k not in envelope_keys and v is not None}
        if "event_type" not in props:
            props["event_type"] = self.event_name
        return props

    def to_analytics_event(self, default_bot_id: str = "default") -> AnalyticsEvent:
        """Converts this typed event into a database AnalyticsEvent record."""
        return AnalyticsEvent(
            event=self.get_event_name(),
            distinct_id=str(self.distinct_id),
            bot_id=self.bot_id or default_bot_id,
            status=self.status,
            duration_ms=self.duration_ms,
            properties=self.to_properties(),
            timestamp=self.timestamp,
        )
