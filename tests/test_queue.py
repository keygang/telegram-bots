import asyncio

import pytest

from platform_core.queue.broker import GenerationJob, TaskQueueBroker
from platform_core.queue.worker import AIWorkerPool


@pytest.mark.asyncio
async def test_generation_job_serialization():
    job = GenerationJob(
        job_id="test_job_123",
        bot_id="image_bot_1",
        user_id=999,
        chat_id=888,
        status_message_id=777,
        prompt="A cute cyberneticcat",
        preset_id="cat_preset",
        photo_path="/tmp/test.jpg",
        model_name="google/gemini-2.5-flash-image",
        cost=1,
    )

    json_str = job.to_json()
    reconstructed = GenerationJob.from_json(json_str)

    assert reconstructed.job_id == "test_job_123"
    assert reconstructed.bot_id == "image_bot_1"
    assert reconstructed.preset_id == "cat_preset"
    assert reconstructed.photo_path == "/tmp/test.jpg"
    assert reconstructed.user_id == 999
    assert reconstructed.prompt == "A cute cyberneticcat"


@pytest.mark.asyncio
async def test_task_queue_broker_fallback():
    broker = TaskQueueBroker(redis_url=None)
    job = GenerationJob(
        job_id="job_fallback",
        bot_id="image_bot_1",
        user_id=1,
        chat_id=1,
        status_message_id=1,
        prompt="Test prompt",
        model_name="mock-model",
    )

    enqueued = await broker.enqueue_job(job)
    assert enqueued is True

    q_len = await broker.get_queue_length()
    assert q_len == 1

    dequeued_job = await broker.dequeue_job(timeout=1.0)
    assert dequeued_job is not None
    assert dequeued_job.job_id == "job_fallback"


@pytest.mark.asyncio
async def test_ai_worker_pool_processing(monkeypatch):
    broker = TaskQueueBroker(redis_url=None)
    worker_pool = AIWorkerPool(broker=broker, concurrency=1, force_mock=True)

    job = GenerationJob(
        job_id="worker_test_job",
        bot_id="image_bot_1",
        user_id=100,
        chat_id=100,
        status_message_id=200,
        prompt="Worker test prompt",
        model_name="mock-model",
    )

    await broker.enqueue_job(job)

    processed_jobs = []

    async def mock_process(job_item):
        processed_jobs.append(job_item)

    monkeypatch.setattr(worker_pool, "process_job", mock_process)

    # Run worker loop for a brief moment
    worker_task = asyncio.create_task(worker_pool.start())
    await asyncio.sleep(0.5)
    await worker_pool.stop()
    worker_task.cancel()

    assert len(processed_jobs) == 1
    assert processed_jobs[0].job_id == "worker_test_job"


@pytest.mark.asyncio
async def test_worker_process_job_caption_without_model():
    broker = TaskQueueBroker(redis_url=None)
    worker_pool = AIWorkerPool(broker=broker, concurrency=1, force_mock=True)

    job = GenerationJob(
        job_id="caption_test_job",
        bot_id="image_bot_1",
        user_id=100,
        chat_id=100,
        status_message_id=200,
        prompt="Cyberpunk neon_city *with special* chars & symbols",
        model_name="google/gemini-2.5-flash-image",
        preset_id="cyber_preset",
    )

    from unittest.mock import AsyncMock, patch

    mock_bot = AsyncMock()
    mock_bot.send_photo = AsyncMock()
    mock_bot.delete_message = AsyncMock()

    with (
        patch("platform_core.queue.worker.Bot", return_value=mock_bot),
        patch("platform_core.db.db.record_event", new_callable=AsyncMock),
        patch("platform_core.db.db.log_generation", new_callable=AsyncMock) as mock_log,
    ):
        await worker_pool.process_job(job)

        assert mock_bot.send_photo.called
        call_kwargs = mock_bot.send_photo.call_args.kwargs
        caption = call_kwargs["caption"]
        assert "Model:" not in caption
        assert "gemini-2.5-flash-image" not in caption
        # Verify HTML escaping: & -> &amp; and no crash with _ or *
        assert "Cyberpunk neon_city *with special* chars &amp; symbols" in caption
        assert call_kwargs["parse_mode"] == "HTML"
        assert mock_log.called
        log_entry = mock_log.call_args[0][0]
        assert log_entry.preset_id == "cyber_preset"


@pytest.mark.asyncio
async def test_bot_pool_caching():
    from unittest.mock import AsyncMock, patch

    from platform_core.queue.worker import BotPool

    pool = BotPool()
    mock_bot_1 = AsyncMock()
    mock_bot_1.session = AsyncMock()
    mock_bot_1.session.close = AsyncMock()

    with patch("platform_core.queue.worker.Bot", return_value=mock_bot_1):
        b1 = pool.get_bot("TOKEN_A")
        b2 = pool.get_bot("TOKEN_A")
        assert b1 is b2
        assert len(pool._bots) == 1

    await pool.close_all()
    mock_bot_1.session.close.assert_awaited_once()
    assert len(pool._bots) == 0


@pytest.mark.asyncio
async def test_task_queue_broker_redis_streams(monkeypatch):
    from unittest.mock import AsyncMock

    mock_redis = AsyncMock()
    mock_redis.ping = AsyncMock()
    mock_redis.xgroup_create = AsyncMock()
    mock_redis.xadd = AsyncMock(return_value="1700000000000-0")
    mock_redis.xautoclaim = AsyncMock(return_value=("0-0", [], []))
    mock_redis.xlen = AsyncMock(return_value=5)
    mock_redis.xack = AsyncMock()
    mock_redis.xdel = AsyncMock()

    job = GenerationJob(
        job_id="stream_job_1",
        bot_id="image_bot_1",
        user_id=1,
        chat_id=1,
        status_message_id=1,
        prompt="Streams prompt",
        model_name="mock-model",
    )

    mock_redis.xreadgroup = AsyncMock(
        return_value=[
            (
                "telegram_tasks:stream",
                [("1700000000000-0", {"payload": job.to_json()})],
            )
        ]
    )

    broker = TaskQueueBroker(redis_url="redis://localhost:6379/0")
    broker._redis_client = mock_redis
    broker._group_initialized = True

    # Test enqueue
    enqueued = await broker.enqueue_job(job)
    assert enqueued is True
    mock_redis.xadd.assert_awaited_once()

    # Test length
    length = await broker.get_queue_length()
    assert length == 5

    # Test dequeue
    dequeued = await broker.dequeue_job(consumer_name="worker_test", timeout=1.0)
    assert dequeued is not None
    assert dequeued.job_id == "stream_job_1"
    assert dequeued.stream_message_id == "1700000000000-0"

    # Test ack
    acked = await broker.ack_job(dequeued)
    assert acked is True
    mock_redis.xack.assert_awaited_once()
    mock_redis.xdel.assert_awaited_once()


@pytest.mark.asyncio
async def test_dlq_routing_on_max_retries():
    from unittest.mock import AsyncMock

    mock_redis = AsyncMock()
    mock_redis.ping = AsyncMock()
    mock_redis.xgroup_create = AsyncMock()
    mock_redis.xadd = AsyncMock(return_value="dlq-1-0")
    mock_redis.xack = AsyncMock()
    mock_redis.xdel = AsyncMock()

    poison_job = GenerationJob(
        job_id="poison_job_1",
        bot_id="image_bot_1",
        user_id=1,
        chat_id=1,
        status_message_id=1,
        prompt="Poison prompt",
        model_name="mock-model",
        retry_count=2,
    )

    # Simulate xautoclaim returning a message attempted >= 3 times
    mock_redis.xautoclaim = AsyncMock(
        return_value=(
            "0-0",
            [("1700000000000-1", {"payload": poison_job.to_json()})],
            [],
        )
    )
    # xpending_range indicates delivery count 3
    mock_redis.xpending_range = AsyncMock(
        return_value=[{"message_id": "1700000000000-1", "delivery_count": 3}]
    )
    # xreadgroup returns None so dequeue finishes
    mock_redis.xreadgroup = AsyncMock(return_value=None)

    broker = TaskQueueBroker(redis_url="redis://localhost:6379/0", dlq_name="telegram_tasks:dlq")
    broker._redis_client = mock_redis
    broker._group_initialized = True

    dequeued = await broker.dequeue_job(consumer_name="worker_test", timeout=0.1)
    # Should not return poison job to worker
    assert dequeued is None

    # Should have added to DLQ stream
    mock_redis.xadd.assert_awaited_once()
    assert mock_redis.xadd.call_args[0][0] == "telegram_tasks:dlq"
    # Should have acked and deleted from main stream
    mock_redis.xack.assert_awaited_once()
    mock_redis.xdel.assert_awaited_once()


def test_resolve_bot_token(monkeypatch):
    from platform_core.queue.worker import resolve_bot_token

    # 1. Environment variable resolution
    monkeypatch.setenv("CUSTOM_BOT_TOKEN", "123:custom_token")
    assert resolve_bot_token("custom_bot") == "123:custom_token"

    # 2. Fallback to settings
    assert resolve_bot_token("image_bot_1") is not None


@pytest.mark.asyncio
async def test_worker_fails_job_when_token_missing(monkeypatch):
    from unittest.mock import AsyncMock, patch

    broker = TaskQueueBroker(redis_url=None)
    worker_pool = AIWorkerPool(broker=broker, concurrency=1, force_mock=True)

    job = GenerationJob(
        job_id="no_token_job",
        bot_id="unknown_bot_without_any_token",
        user_id=456,
        chat_id=456,
        status_message_id=999,
        prompt="A nice landscape",
        model_name="mock-model",
        cost=2,
    )

    # Ensure token resolves to None
    monkeypatch.setattr("platform_core.queue.worker.resolve_bot_token", lambda _bid: None)

    with (
        patch("platform_core.db.db.add_user_credits", new_callable=AsyncMock) as mock_refund,
        patch("platform_core.db.db.record_event", new_callable=AsyncMock) as mock_event,
        patch("platform_core.db.db.log_generation", new_callable=AsyncMock) as mock_log,
    ):
        await worker_pool.process_job(job)

        # Verified refund issued
        mock_refund.assert_awaited_once_with(
            user_id=456,
            bot_id="unknown_bot_without_any_token",
            stars_paid=0,
            credits_to_add=2,
            telegram_charge_id="refund",
        )
        # Failure logged
        assert mock_event.called
        assert mock_log.called
        log_arg = mock_log.call_args[0][0]
        assert log_arg.status == "failed"
        assert "Bot token not found" in log_arg.error_message


@pytest.mark.asyncio
async def test_worker_loads_reference_photo_from_path(tmp_path):
    from unittest.mock import AsyncMock, patch

    # Create dummy photo on disk
    photo_file = tmp_path / "reference.jpg"
    test_bytes = b"fake_jpeg_binary_data_12345"
    photo_file.write_bytes(test_bytes)

    broker = TaskQueueBroker(redis_url=None)
    worker_pool = AIWorkerPool(broker=broker, concurrency=1, force_mock=True)

    job = GenerationJob(
        job_id="photo_path_job",
        bot_id="image_bot_1",
        user_id=789,
        chat_id=789,
        status_message_id=123,
        prompt="Photo transfer test",
        model_name="mock-model",
        photo_path=photo_file.as_uri(),
    )

    mock_bot = AsyncMock()
    mock_bot.send_photo = AsyncMock()
    mock_bot.delete_message = AsyncMock()

    captured_requests = []

    async def mock_generate(req):
        captured_requests.append(req)
        from platform_core.generators.base import GenerationResponse, GenerationStatus

        return GenerationResponse(
            status=GenerationStatus.SUCCESS,
            media_urls=["https://example.com/out.png"],
            duration_ms=100,
        )

    with (
        patch("platform_core.queue.worker.Bot", return_value=mock_bot),
        patch("platform_core.queue.worker.GeneratorFactory.get_generator") as mock_factory,
        patch("platform_core.db.db.record_event", new_callable=AsyncMock),
        patch("platform_core.db.db.log_generation", new_callable=AsyncMock),
    ):
        mock_gen_instance = AsyncMock()
        mock_gen_instance.generate = mock_generate
        mock_factory.return_value = mock_gen_instance

        await worker_pool.process_job(job)

        assert len(captured_requests) == 1
        assert captured_requests[0].reference_photo_bytes == test_bytes

