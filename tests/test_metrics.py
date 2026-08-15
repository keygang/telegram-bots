from datetime import datetime
from unittest.mock import AsyncMock

import pytest
from aiogram.types import Chat, Message, Update
from aiogram.types import User as TelegramUser

from bots.admin_bot.bot import (
    format_bots_breakdown_table,
    format_button_clicks_table,
    format_commands_table,
    format_models_table,
)
from platform_core.db import BotEvent, GenerationLog, db
from platform_core.metrics.middleware import MetricsMiddleware


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
            model_name="google/gemini-2.5-flash-image",
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
    assert len(summary["top_buttons"]) >= 1
    assert summary["top_buttons"][0]["name"] == "preset:odyssey"
    assert len(summary["top_commands"]) >= 1
    assert summary["top_commands"][0]["name"] == "/start"


@pytest.mark.asyncio
async def test_metrics_middleware_injects_context():
    mw = MetricsMiddleware(bot_id="image_bot_test")
    handler = AsyncMock(return_value="ok")

    user = TelegramUser(id=98765, is_bot=False, first_name="Alice")
    chat = Chat(id=98765, type="private")
    msg = Message(
        message_id=1, date=datetime.now(), chat=chat, from_user=user, text="/start@my_bot"
    )
    update = Update(update_id=1001, message=msg)

    data = {"event_from_user": user}
    res = await mw(handler, update, data)
    assert res == "ok"
    handler.assert_called_once()
    assert data["bot_id"] == "image_bot_test"
    assert data["tracker"].bot_id == "image_bot_test"


@pytest.mark.asyncio
async def test_explicit_handler_event_tracking():
    from platform_core.events import ButtonClickEvent, CommandEvent, get_tracker

    tracker = get_tracker("image_bot_test_cb")
    user_id = 98765

    await tracker.track(
        CommandEvent(
            distinct_id=user_id,
            bot_id="image_bot_test_cb",
            command="/start",
            duration_ms=10,
        )
    )

    await tracker.track(
        ButtonClickEvent(
            distinct_id=user_id,
            bot_id="image_bot_test_cb",
            button_id="preset:cyberpunk",
            duration_ms=15,
        )
    )

    buttons = await db.get_button_click_metrics(bot_id="image_bot_test_cb")
    assert len(buttons) >= 1
    assert buttons[0]["name"] == "preset:cyberpunk"
    assert buttons[0]["count"] >= 1

    summary = await db.get_metrics_summary(bot_id="image_bot_test_cb")
    assert any(cmd["name"] == "/start" for cmd in summary["top_commands"])


def test_table_formatters():
    buttons = [
        {"name": "preset:odyssey", "count": 15, "unique_users": 8},
        {"name": "model:flux", "count": 10, "unique_users": 5},
    ]
    formatted_btn = format_button_clicks_table(buttons)
    assert "preset:odyssey" in formatted_btn
    assert "15" in formatted_btn
    assert "<pre>" in formatted_btn

    commands = [
        {"name": "/start", "count": 25, "unique_users": 12},
    ]
    formatted_cmd = format_commands_table(commands)
    assert "/start" in formatted_cmd
    assert "25" in formatted_cmd

    bots = [
        {"bot_id": "image_bot", "users": 10, "clicks": 20, "commands": 30, "generations": 5},
    ]
    formatted_bots = format_bots_breakdown_table(bots)
    assert "image_bot" in formatted_bots
    assert "20" in formatted_bots

    models = [
        {
            "model_name": "google/gemini-2.5-flash-image",
            "total": 10,
            "success": 9,
            "avg_duration_ms": 1200,
        },
    ]
    formatted_models = format_models_table(models)
    assert "gemini-2.5-flash-im" in formatted_models or "gemini-2.5" in formatted_models
