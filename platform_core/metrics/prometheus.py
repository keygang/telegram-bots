import logging
from typing import Optional
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST

logger = logging.getLogger(__name__)

# Prometheus Metrics Definitions
TELEGRAM_EVENTS_TOTAL = Counter(
    "telegram_events_total",
    "Total count of Telegram events handled by bots",
    ["bot_id", "event_type", "event_name"],
)

TELEGRAM_EVENT_DURATION_SECONDS = Histogram(
    "telegram_event_duration_seconds",
    "Latency of Telegram event handling in seconds",
    ["bot_id", "event_type"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

TELEGRAM_GENERATIONS_TOTAL = Counter(
    "telegram_generations_total",
    "Total count of AI media generation requests",
    ["bot_id", "status", "model_name"],
)

TELEGRAM_STARS_TOTAL = Counter(
    "telegram_stars_total",
    "Total count of Telegram Stars collected",
    ["bot_id"],
)

TELEGRAM_QUEUE_PENDING_TASKS = Gauge(
    "telegram_queue_pending_tasks",
    "Number of pending tasks waiting in the task broker queue",
)


def record_prometheus_event(bot_id: str, event_type: str, event_name: str, duration_ms: float) -> None:
    """Records event count and latency in Prometheus metrics."""
    try:
        TELEGRAM_EVENTS_TOTAL.labels(
            bot_id=bot_id,
            event_type=event_type,
            event_name=event_name,
        ).inc()
        TELEGRAM_EVENT_DURATION_SECONDS.labels(
            bot_id=bot_id,
            event_type=event_type,
        ).observe(duration_ms / 1000.0)
    except Exception as e:
        logger.warning(f"Failed to record Prometheus event metrics: {e}")


def record_prometheus_generation(bot_id: str, status: str, model_name: str = "default") -> None:
    """Records AI generation status in Prometheus metrics."""
    try:
        TELEGRAM_GENERATIONS_TOTAL.labels(
            bot_id=bot_id,
            status=status,
            model_name=model_name,
        ).inc()
    except Exception as e:
        logger.warning(f"Failed to record Prometheus generation metrics: {e}")


def record_prometheus_stars(bot_id: str, amount: int = 1) -> None:
    """Records Telegram Stars transaction in Prometheus metrics."""
    try:
        TELEGRAM_STARS_TOTAL.labels(bot_id=bot_id).inc(amount)
    except Exception as e:
        logger.warning(f"Failed to record Prometheus stars metrics: {e}")


def update_prometheus_queue(pending_count: int) -> None:
    """Updates pending task queue count gauge."""
    try:
        TELEGRAM_QUEUE_PENDING_TASKS.set(pending_count)
    except Exception as e:
        logger.warning(f"Failed to update Prometheus queue metrics: {e}")


def get_prometheus_metrics() -> bytes:
    """Generates and returns formatted Prometheus metric text format."""
    return generate_latest()
