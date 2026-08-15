from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(UTC)


class UserProfile(BaseModel):
    """Telegram User Profile Schema"""

    telegram_id: int
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    language_code: str | None = None
    selected_model: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    last_active_at: datetime = Field(default_factory=utc_now)


class UserBalance(BaseModel):
    """User Credits & Monetization Balance Schema"""

    user_id: int
    credits_remaining: int = 3
    total_stars_spent: int = 0
    free_credits_reset_at: datetime = Field(default_factory=utc_now)


class StarTransaction(BaseModel):
    """Telegram Stars Purchase Transaction Record"""

    id: str | None = None
    user_id: int
    bot_id: str
    stars_amount: int
    credits_added: int
    telegram_payment_charge_id: str
    provider_payment_charge_id: str | None = None
    created_at: datetime = Field(default_factory=utc_now)


class AnalyticsEvent(BaseModel):
    """
    PostHog-style Analytics & Telemetry Event Schema.
    Combines common standard envelope fields with flexible JSONB properties.
    """

    id: str | None = None
    event: str  # e.g., 'command', 'click', 'generation_start', 'generation_success', 'payment', 'custom'
    distinct_id: str  # Telegram user ID or distinct identifier (stringified)
    bot_id: str = "default"
    status: str = "success"  # 'success', 'error', 'pending'
    duration_ms: int | None = None
    properties: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=utc_now)

    @classmethod
    def from_bot_event(cls, bot_event: "BotEvent") -> "AnalyticsEvent":
        props = dict(bot_event.metadata)
        if "event_type" not in props:
            props["event_type"] = bot_event.event_type
        if "event_name" not in props:
            props["event_name"] = bot_event.event_name
        return cls(
            id=bot_event.id,
            event=bot_event.event_name or bot_event.event_type,
            distinct_id=str(bot_event.user_id),
            bot_id=bot_event.bot_id,
            duration_ms=bot_event.duration_ms,
            properties=props,
            timestamp=bot_event.created_at,
        )


# Alias Event to AnalyticsEvent
Event = AnalyticsEvent


class BotEvent(BaseModel):
    """Metrics & Telemetry Event Schema (Legacy compatibility)"""

    id: str | None = None
    bot_id: str
    user_id: int
    event_type: str  # 'command', 'click', 'generation_start', 'generation_success', 'generation_fail', 'payment'
    event_name: str  # e.g., '/start', 'preset:odyssey', 'model:flux'
    duration_ms: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)


class GenerationLog(BaseModel):
    """Media Generation Execution Record"""

    id: str | None = None
    bot_id: str
    user_id: int
    model_name: str
    prompt: str
    preset_id: str | None = None
    media_url: str | None = None
    status: str = "pending"  # "pending", "success", "failed"
    duration_ms: int | None = None
    error_message: str | None = None
    created_at: datetime = Field(default_factory=utc_now)


class ButtonClickMetric(BaseModel):
    """Aggregated button click metric schema."""

    name: str
    count: int = 0
    unique_users: int = 0
    avg_duration_ms: int = 0

    def __getitem__(self, item: str) -> Any:
        return getattr(self, item)

    def get(self, item: str, default: Any = None) -> Any:
        return getattr(self, item, default)


class CommandMetric(BaseModel):
    """Aggregated bot command execution metric schema."""

    name: str
    count: int = 0
    unique_users: int = 0
    avg_duration_ms: int = 0

    def __getitem__(self, item: str) -> Any:
        return getattr(self, item)

    def get(self, item: str, default: Any = None) -> Any:
        return getattr(self, item, default)


class BotBreakdownMetric(BaseModel):
    """Per-bot cross-instance activity breakdown metric schema."""

    bot_id: str
    users: int = 0
    clicks: int = 0
    commands: int = 0
    generations: int = 0
    messages_sent: int = 0
    stars: int = 0
    events: int = 0

    def __getitem__(self, item: str) -> Any:
        return getattr(self, item)

    def get(self, item: str, default: Any = None) -> Any:
        return getattr(self, item, default)


class ModelBreakdownMetric(BaseModel):
    """AI Model usage and performance breakdown metric schema."""

    model_name: str
    total: int = 0
    success: int = 0
    failed: int = 0
    avg_duration_ms: int = 0

    def __getitem__(self, item: str) -> Any:
        return getattr(self, item)

    def get(self, item: str, default: Any = None) -> Any:
        return getattr(self, item, default)


class MessageBreakdownMetric(BaseModel):
    """Outgoing message type distribution breakdown metric schema."""

    type: str
    count: int = 0
    unique_users: int = 0
    avg_chars: int = 0

    def __getitem__(self, item: str) -> Any:
        return getattr(self, item)

    def get(self, item: str, default: Any = None) -> Any:
        return getattr(self, item, default)


class ErrorBreakdownMetric(BaseModel):
    """Platform error category and frequency breakdown metric schema."""

    error_type: str
    count: int = 0
    unique_users: int = 0
    last_message: str = ""

    def __getitem__(self, item: str) -> Any:
        return getattr(self, item)

    def get(self, item: str, default: Any = None) -> Any:
        return getattr(self, item, default)


class RecentEventMetric(BaseModel):
    """Recent real-time event feed entry schema."""

    event: str
    bot_id: str
    user_id: int | None = None
    duration_ms: int | None = None
    created_at: str = ""

    def __getitem__(self, item: str) -> Any:
        return getattr(self, item)

    def get(self, item: str, default: Any = None) -> Any:
        return getattr(self, item, default)


class MetricsSummary(BaseModel):
    """Overall platform and bot telemetry summary schema."""

    total_users: int = 0
    total_events: int = 0
    total_commands: int = 0
    total_button_clicks: int = 0
    total_generations: int = 0
    successful_generations: int = 0
    failed_generations: int = 0
    total_messages_sent: int = 0
    total_errors: int = 0
    total_stars_earned: int = 0
    top_presets: list[tuple[str, int]] = Field(default_factory=list)
    top_buttons: list[ButtonClickMetric] = Field(default_factory=list)
    top_commands: list[CommandMetric] = Field(default_factory=list)
    bots_breakdown: list[BotBreakdownMetric] = Field(default_factory=list)
    models_breakdown: list[ModelBreakdownMetric] = Field(default_factory=list)
    messages_breakdown: list[MessageBreakdownMetric] = Field(default_factory=list)
    errors_breakdown: list[ErrorBreakdownMetric] = Field(default_factory=list)
    recent_events: list[RecentEventMetric] = Field(default_factory=list)

    def __getitem__(self, item: str) -> Any:
        return getattr(self, item)

    def get(self, item: str, default: Any = None) -> Any:
        return getattr(self, item, default)
