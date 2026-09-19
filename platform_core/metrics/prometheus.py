import atexit
from collections import defaultdict
import logging
import threading
from typing import Any

import redis
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from prometheus_client.core import (
    CollectorRegistry,
    CounterMetricFamily,
    GaugeMetricFamily,
    HistogramMetricFamily,
)

from platform_core.config import settings

__all__ = [
    "CONTENT_TYPE_LATEST",
    "flush_metrics_to_redis",
    "get_prometheus_metrics",
    "get_redis_client",
    "record_prometheus_event",
    "record_prometheus_generation",
    "record_prometheus_stars",
    "shutdown_metrics",
    "update_prometheus_queue",
]

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

_redis_client: redis.Redis | None = None

# In-Memory Accumulator for non-blocking telemetry sync
_metrics_lock = threading.Lock()
_pending_events: dict[str, int] = defaultdict(int)
_pending_durations_sum: dict[str, float] = defaultdict(float)
_pending_durations_count: dict[str, int] = defaultdict(int)
_pending_durations_buckets: dict[str, int] = defaultdict(int)
_pending_generations: dict[str, int] = defaultdict(int)
_pending_stars: dict[str, int] = defaultdict(int)
_pending_queue: int | None = None

_flusher_thread: threading.Thread | None = None
_flusher_stop_event = threading.Event()


def get_redis_client() -> redis.Redis | None:
    """Returns a cached synchronous Redis client for background metric synchronization."""
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


def _ensure_flusher_thread_started() -> None:
    """Ensures the background flusher daemon thread is running."""
    global _flusher_thread
    if _flusher_thread is not None and _flusher_thread.is_alive():
        return
    _flusher_stop_event.clear()
    _flusher_thread = threading.Thread(
        target=_flusher_worker,
        name="PrometheusMetricsFlusher",
        daemon=True,
    )
    _flusher_thread.start()


def _flusher_worker() -> None:
    """Background flusher loop running periodically."""
    while not _flusher_stop_event.wait(timeout=1.0):
        try:
            flush_metrics_to_redis()
        except Exception as e:
            logger.debug(f"Metrics flusher worker error: {e}")


def flush_metrics_to_redis() -> None:
    """Flushes in-memory accumulated metrics to Redis via a pipelined batch."""
    global _pending_queue, _pending_events, _pending_durations_sum, _pending_durations_count, _pending_durations_buckets, _pending_generations, _pending_stars

    with _metrics_lock:
        if not (
            _pending_events
            or _pending_durations_sum
            or _pending_durations_count
            or _pending_durations_buckets
            or _pending_generations
            or _pending_stars
            or _pending_queue is not None
        ):
            return

        events = _pending_events
        durations_sum = _pending_durations_sum
        durations_count = _pending_durations_count
        durations_buckets = _pending_durations_buckets
        generations = _pending_generations
        stars = _pending_stars
        queue_val = _pending_queue

        _pending_events = defaultdict(int)
        _pending_durations_sum = defaultdict(float)
        _pending_durations_count = defaultdict(int)
        _pending_durations_buckets = defaultdict(int)
        _pending_generations = defaultdict(int)
        _pending_stars = defaultdict(int)
        _pending_queue = None

    try:
        r = get_redis_client()
        if not r:
            return

        pipe = r.pipeline(transaction=False)
        for k, count in events.items():
            pipe.hincrby("metrics:events_total", k, count)
        for k, val in durations_sum.items():
            pipe.hincrbyfloat("metrics:durations_sum", k, val)
        for k, count in durations_count.items():
            pipe.hincrby("metrics:durations_count", k, count)
        for k, count in durations_buckets.items():
            pipe.hincrby("metrics:durations_buckets", k, count)
        for k, count in generations.items():
            pipe.hincrby("metrics:generations_total", k, count)
        for k, count in stars.items():
            pipe.hincrby("metrics:stars_total", k, count)
        if queue_val is not None:
            pipe.set("metrics:queue_pending", queue_val)

        pipe.execute()
    except Exception as e:
        logger.debug(f"Failed to flush accumulated metrics to Redis: {e}")


def shutdown_metrics() -> None:
    """Gracefully flushes remaining metrics and stops background flusher."""
    _flusher_stop_event.set()
    flush_metrics_to_redis()


atexit.register(shutdown_metrics)


def record_prometheus_event(
    bot_id: str, event_type: str, event_name: str, duration_ms: float
) -> None:
    """
    Records event count and latency in Prometheus metrics and accumulates for
    asynchronous pipelined flush to Redis. Returns immediately without blocking the event loop.
    """
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
        duration_s = duration_ms / 1000.0
        with _metrics_lock:
            _pending_events[f"{bot_id}:{event_type}:{event_name}"] += 1
            _pending_durations_sum[f"{bot_id}:{event_type}"] += duration_s
            _pending_durations_count[f"{bot_id}:{event_type}"] += 1
            for b in BUCKETS:
                if duration_s <= b:
                    _pending_durations_buckets[f"{bot_id}:{event_type}:{b}"] += 1
            _pending_durations_buckets[f"{bot_id}:{event_type}:+Inf"] += 1
        _ensure_flusher_thread_started()
    except Exception as e:
        logger.debug(f"Failed to buffer event metrics for Redis: {e}")


def record_prometheus_generation(
    bot_id: str,
    status: str = "success",
    model_name: str = "default",
    model: str | None = None,
    duration_ms: float | None = None,
    **kwargs: Any,
) -> None:
    """
    Records AI generation status in Prometheus metrics and accumulates for
    asynchronous pipelined flush to Redis. Returns immediately without blocking the event loop.
    """
    effective_model = model or model_name or "default"
    try:
        TELEGRAM_GENERATIONS_TOTAL.labels(
            bot_id=bot_id,
            status=status,
            model_name=effective_model,
        ).inc()
    except Exception as e:
        logger.warning(f"Failed to record Prometheus generation metrics: {e}")

    try:
        with _metrics_lock:
            _pending_generations[f"{bot_id}:{status}:{effective_model}"] += 1
        _ensure_flusher_thread_started()
    except Exception as e:
        logger.debug(f"Failed to buffer generation metrics for Redis: {e}")


def record_prometheus_stars(bot_id: str, amount: int = 1) -> None:
    """
    Records Telegram Stars transaction in Prometheus metrics and accumulates for
    asynchronous pipelined flush to Redis. Returns immediately without blocking the event loop.
    """
    try:
        TELEGRAM_STARS_TOTAL.labels(bot_id=bot_id).inc(amount)
    except Exception as e:
        logger.warning(f"Failed to record Prometheus stars metrics: {e}")

    try:
        with _metrics_lock:
            _pending_stars[bot_id] += amount
        _ensure_flusher_thread_started()
    except Exception as e:
        logger.debug(f"Failed to buffer stars metrics for Redis: {e}")


def update_prometheus_queue(pending_count: int) -> None:
    """
    Updates pending task queue count gauge and accumulates for asynchronous
    pipelined flush to Redis. Returns immediately without blocking the event loop.
    """
    global _pending_queue
    try:
        TELEGRAM_QUEUE_PENDING_TASKS.set(pending_count)
    except Exception as e:
        logger.warning(f"Failed to update Prometheus queue metrics: {e}")

    try:
        with _metrics_lock:
            _pending_queue = pending_count
        _ensure_flusher_thread_started()
    except Exception as e:
        logger.debug(f"Failed to buffer queue metric for Redis: {e}")



def get_prometheus_metrics() -> bytes:
    """
    Generates and returns formatted Prometheus metric text.
    If Redis is available and has recorded data from distributed bots/workers,
    aggregates and exposes cluster-wide metrics. Otherwise falls back to in-memory registry.
    """
    try:
        flush_metrics_to_redis()
    except Exception as e:
        logger.debug(f"Pre-scrape metric flush error: {e}")

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
                registry.register(
                    type("EventsCollector", (), {"collect": lambda self: [events_metric]})()
                )

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
                registry.register(
                    type("GenCollector", (), {"collect": lambda self: [gen_metric]})()
                )

                # Stars Total
                stars_metric = CounterMetricFamily(
                    "telegram_stars_total",
                    "Total count of Telegram Stars collected",
                    labels=["bot_id"],
                )
                for k, v in stars_data.items():
                    stars_metric.add_metric([k], float(v))
                registry.register(
                    type("StarsCollector", (), {"collect": lambda self: [stars_metric]})()
                )

                # Queue Pending
                queue_metric = GaugeMetricFamily(
                    "telegram_queue_pending_tasks",
                    "Number of pending tasks waiting in the task broker queue",
                )
                queue_val = float(q_val) if q_val is not None else 0.0
                queue_metric.add_metric([], queue_val)
                registry.register(
                    type("QueueCollector", (), {"collect": lambda self: [queue_metric]})()
                )

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
                            inf_count = float(
                                durations_buckets.get(f"{b_id}:{e_type}:+Inf", total_count)
                            )
                            bucket_list.append(("+Inf", inf_count))
                            latency_metric.add_metric(
                                [b_id, e_type], bucket_list, sum_value=sum_val
                            )
                    registry.register(
                        type("LatencyCollector", (), {"collect": lambda self: [latency_metric]})()
                    )

                return generate_latest(registry)
    except Exception as e:
        logger.warning(
            f"Error collecting metrics from Redis, falling back to in-memory metrics: {e}"
        )

    return generate_latest()
