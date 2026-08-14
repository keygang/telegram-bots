import pytest
from platform_core.db import db, BotEvent, GenerationLog


@pytest.mark.asyncio
async def test_metrics_recording_and_summary():
    bot_id = "test_metrics_bot"
    user_id = 1234567

    await db.record_event(
        BotEvent(
            bot_id=bot_id,
            user_id=user_id,
            event_type="command",
            event_name="/start",
            duration_ms=15,
        )
    )

    await db.record_event(
        BotEvent(
            bot_id=bot_id,
            user_id=user_id,
            event_type="click",
            event_name="preset:odyssey",
            duration_ms=22,
        )
    )

    await db.log_generation(
        GenerationLog(
            bot_id=bot_id,
            user_id=user_id,
            model_name="flux-schnell",
            prompt="Hero Odyssey",
            preset_id="odyssey",
            status="success",
            duration_ms=800,
        )
    )

    summary = await db.get_metrics_summary(bot_id=bot_id)
    assert summary["total_users"] >= 1
    assert summary["total_commands"] >= 1
    assert summary["total_button_clicks"] >= 1
    assert summary["total_generations"] >= 1
    assert summary["successful_generations"] >= 1
