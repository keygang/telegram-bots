import logging
from typing import Optional
import redis
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from prometheus_client.core import CounterMetricFamily, GaugeMetricFamily, HistogramMetricFamily, CollectorRegistry
from platform_core.config import settings

logger = logging.getLogger(__name__)

BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)

# Prometheus In-Memory Metrics Definitions
TELEGRAM_EVENTS_TOTAL = Counter(
    "telegram_events_total",
    "Total count of Telegram events handled by bots",
    ["bot_id", "event_type", "event_name"],
)

TELEGRAM_EVENT_DURATION_SECONDS = Histogram(
    "telegram_event_duration_seconds",
    "Latency of Telegram event handling in seconds",
    ["bot_id", "event_type"],
    buckets=BUCKETS,
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

_redis_client: Optional[redis.Redis] = None


def get_redis_client() -> Optional[redis.Redis]:
    """Returns a cached synchronous Redis client for low-latency metric increments."""
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    if not settings.REDIS_URL:
        return None
    try:
        _redis_client = redis.Redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_timeout=1.0,
            socket_connect_timeout=1.0,
        )
        return _redis_client
    except Exception as e:
        logger.debug(f"Redis client initialization for metrics failed: {e}")
        return None


def record_prometheus_event(bot_id: str, event_type: str, event_name: str, duration_ms: float) -> None:
    """Records event count and latency in Prometheus metrics and syncs to shared Redis."""
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

    try:
        r = get_redis_client()
        if r:
            duration_s = duration_ms / 1000.0
            r.hincrby("metrics:events_total", f"{bot_id}:{event_type}:{event_name}", 1)
            r.hincrbyfloat("metrics:durations_sum", f"{bot_id}:{event_type}", duration_s)
            r.hincrby("metrics:durations_count", f"{bot_id}:{event_type}", 1)
            for b in BUCKETS:
                if duration_s <= b:
                    r.hincrby("metrics:durations_buckets", f"{bot_id}:{event_type}:{b}", 1)
            r.hincrby("metrics:durations_buckets", f"{bot_id}:{event_type}:+Inf", 1)
    except Exception as e:
        logger.debug(f"Failed to sync event metrics to Redis: {e}")


def record_prometheus_generation(bot_id: str, status: str, model_name: str = "default") -> None:
    """Records AI generation status in Prometheus metrics and syncs to shared Redis."""
    try:
        TELEGRAM_GENERATIONS_TOTAL.labels(
            bot_id=bot_id,
            status=status,
            model_name=model_name,
        ).inc()
    except Exception as e:
        logger.warning(f"Failed to record Prometheus generation metrics: {e}")

    try:
        r = get_redis_client()
        if r:
            r.hincrby("metrics:generations_total", f"{bot_id}:{status}:{model_name}", 1)
    except Exception as e:
        logger.debug(f"Failed to sync generation metrics to Redis: {e}")


def record_prometheus_stars(bot_id: str, amount: int = 1) -> None:
    """Records Telegram Stars transaction in Prometheus metrics and syncs to shared Redis."""
    try:
        TELEGRAM_STARS_TOTAL.labels(bot_id=bot_id).inc(amount)
    except Exception as e:
        logger.warning(f"Failed to record Prometheus stars metrics: {e}")

    try:
        r = get_redis_client()
        if r:
            r.hincrby("metrics:stars_total", bot_id, amount)
    except Exception as e:
        logger.debug(f"Failed to sync stars metrics to Redis: {e}")


def update_prometheus_queue(pending_count: int) -> None:
    """Updates pending task queue count gauge and syncs to shared Redis."""
    try:
        TELEGRAM_QUEUE_PENDING_TASKS.set(pending_count)
    except Exception as e:
        logger.warning(f"Failed to update Prometheus queue metrics: {e}")

    try:
        r = get_redis_client()
        if r:
            r.set("metrics:queue_pending", pending_count)
    except Exception as e:
        logger.debug(f"Failed to sync queue metric to Redis: {e}")


def get_prometheus_metrics() -> bytes:
    """
    Generates and returns formatted Prometheus metric text.
    If Redis is available and has recorded data from distributed bots/workers,
    aggregates and exposes cluster-wide metrics. Otherwise falls back to in-memory registry.
    """
    try:
        r = get_redis_client()
        if r:
            events_data = r.hgetall("metrics:events_total")
            gen_data = r.hgetall("metrics:generations_total")
            stars_data = r.hgetall("metrics:stars_total")
            q_val = r.get("metrics:queue_pending")
            durations_sum = r.hgetall("metrics:durations_sum")
            durations_count = r.hgetall("metrics:durations_count")
            durations_buckets = r.hgetall("metrics:durations_buckets")

            if events_data or gen_data or stars_data or q_val is not None:
                registry = CollectorRegistry()

                # Events Total
                events_metric = CounterMetricFamily(
                    "telegram_events_total",
                    "Total count of Telegram events handled by bots",
                    labels=["bot_id", "event_type", "event_name"],
                )
                for k, v in events_data.items():
                    parts = k.split(":", 2)
                    if len(parts) == 3:
                        events_metric.add_metric(parts, float(v))
                registry.register(type("EventsCollector", (), {"collect": lambda self: [events_metric]})())

                # Generations Total
                gen_metric = CounterMetricFamily(
                    "telegram_generations_total",
                    "Total count of AI media generation requests",
                    labels=["bot_id", "status", "model_name"],
                )
                for k, v in gen_data.items():
                    parts = k.split(":", 2)
                    if len(parts) == 3:
                        gen_metric.add_metric(parts, float(v))
                registry.register(type("GenCollector", (), {"collect": lambda self: [gen_metric]})())

                # Stars Total
                stars_metric = CounterMetricFamily(
                    "telegram_stars_total",
                    "Total count of Telegram Stars collected",
                    labels=["bot_id"],
                )
                for k, v in stars_data.items():
                    stars_metric.add_metric([k], float(v))
                registry.register(type("StarsCollector", (), {"collect": lambda self: [stars_metric]})())

                # Queue Pending
                queue_metric = GaugeMetricFamily(
                    "telegram_queue_pending_tasks",
                    "Number of pending tasks waiting in the task broker queue",
                )
                queue_val = float(q_val) if q_val is not None else 0.0
                queue_metric.add_metric([], queue_val)
                registry.register(type("QueueCollector", (), {"collect": lambda self: [queue_metric]})())

                # Latency Histogram
                if durations_count:
                    latency_metric = HistogramMetricFamily(
                        "telegram_event_duration_seconds",
                        "Latency of Telegram event handling in seconds",
                        labels=["bot_id", "event_type"],
                    )
                    for k, total_count in durations_count.items():
                        parts = k.split(":", 1)
                        if len(parts) == 2:
                            b_id, e_type = parts
                            sum_val = float(durations_sum.get(k, 0.0))
                            bucket_list = []
                            for b in BUCKETS:
                                b_count = float(durations_buckets.get(f"{b_id}:{e_type}:{b}", 0))
                                bucket_list.append((str(b), b_count))
                            inf_count = float(durations_buckets.get(f"{b_id}:{e_type}:+Inf", total_count))
                            bucket_list.append(("+Inf", inf_count))
                            latency_metric.add_metric([b_id, e_type], bucket_list, sum_value=sum_val)
                    registry.register(type("LatencyCollector", (), {"collect": lambda self: [latency_metric]})())

                return generate_latest(registry)
    except Exception as e:
        logger.warning(f"Error collecting metrics from Redis, falling back to in-memory metrics: {e}")

    return generate_latest()
