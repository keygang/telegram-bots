import pytest
from fastapi.testclient import TestClient

from platform_core.metrics.prometheus import (
    record_prometheus_event,
    record_prometheus_generation,
    record_prometheus_stars,
    update_prometheus_queue,
    get_prometheus_metrics,
)
from platform_core.server import app


def test_prometheus_metrics_record_and_generate():
    bot_id = "test_prometheus_bot"
    
    record_prometheus_event(bot_id, "command", "/start", duration_ms=45.0)
    record_prometheus_event(bot_id, "click", "preset:cyberpunk", duration_ms=12.0)
    record_prometheus_generation(bot_id, "success", "google/gemini-2.5-flash-image")
    record_prometheus_stars(bot_id, amount=15)
    update_prometheus_queue(7)

    raw_metrics = get_prometheus_metrics().decode("utf-8")

    assert "telegram_events_total" in raw_metrics
    assert 'bot_id="test_prometheus_bot"' in raw_metrics
    assert 'event_name="/start"' in raw_metrics
    assert 'event_name="preset:cyberpunk"' in raw_metrics
    assert "telegram_generations_total" in raw_metrics
    assert 'status="success"' in raw_metrics
    assert "telegram_stars_total" in raw_metrics
    assert "telegram_queue_pending_tasks" in raw_metrics


def test_server_metrics_endpoint():
    client = TestClient(app)
    response = client.get("/metrics")

    assert response.status_code == 200
    assert "text/plain" in response.headers.get("content-type", "")
    assert "telegram_events_total" in response.text
