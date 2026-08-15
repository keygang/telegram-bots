from unittest.mock import AsyncMock, patch

import pytest
from aiogram.types import CallbackQuery, Message
from aiogram.types import User as TelegramUser

from platform_core.bot.handlers import handle_help_command
from platform_core.bot.keyboards import get_help_keyboard
from platform_core.i18n import i18n


@pytest.mark.asyncio
async def test_handle_help_command_message():
    message = AsyncMock(spec=Message)
    message.from_user = TelegramUser(id=12345, is_bot=False, first_name="TestUser")
    message.answer = AsyncMock()

    with patch("platform_core.bot.handlers.get_tracker") as mock_get_tracker:
        mock_tracker = AsyncMock()
        mock_get_tracker.return_value = mock_tracker

        await handle_help_command(message, bot_id="test_bot")

        # Verify message answer was sent with help text and keyboard
        message.answer.assert_called_once()
        args, kwargs = message.answer.call_args
        assert "Help & Usage Guide" in args[0]
        assert kwargs.get("parse_mode") == "Markdown"
        keyboard = kwargs.get("reply_markup")
        assert keyboard is not None
        assert len(keyboard.inline_keyboard) >= 2

        # Verify tracker recorded both CommandEvent and MessageSentEvent
        assert mock_tracker.track.call_count == 2
        command_event = mock_tracker.track.call_args_list[0][0][0]
        assert command_event.command == "/help"
        assert command_event.distinct_id == 12345

        sent_event = mock_tracker.track.call_args_list[1][0][0]
        assert sent_event.message_type == "help"
        assert sent_event.distinct_id == 12345


@pytest.mark.asyncio
async def test_handle_help_command_callback():
    callback = AsyncMock(spec=CallbackQuery)
    callback.data = "help_menu"
    callback.from_user = TelegramUser(id=67890, is_bot=False, first_name="User2")
    callback.answer = AsyncMock()
    callback.message = AsyncMock(spec=Message)
    callback.message.edit_text = AsyncMock()

    with patch("platform_core.bot.handlers.get_tracker") as mock_get_tracker:
        mock_tracker = AsyncMock()
        mock_get_tracker.return_value = mock_tracker

        await handle_help_command(callback, bot_id="test_bot")

        callback.answer.assert_called_once()
        callback.message.edit_text.assert_called_once()
        args, kwargs = callback.message.edit_text.call_args
        assert "Help & Usage Guide" in args[0]
        assert kwargs.get("parse_mode") == "Markdown"


@pytest.mark.asyncio
async def test_handle_help_command_i18n_ru():
    message = AsyncMock(spec=Message)
    message.from_user = TelegramUser(id=11111, is_bot=False, first_name="RuUser")
    message.answer = AsyncMock()

    def ru_gettext(key: str, **kwargs) -> str:
        return i18n.get(key, lang="ru", **kwargs)

    with patch("platform_core.bot.handlers.get_tracker") as mock_get_tracker:
        mock_tracker = AsyncMock()
        mock_get_tracker.return_value = mock_tracker

        await handle_help_command(message, bot_id="test_bot", _=ru_gettext)

        message.answer.assert_called_once()
        args, _kwargs = message.answer.call_args
        assert "Справка" in args[0]
        assert "/generate" in args[0]


def test_get_help_keyboard_structure():
    kb = get_help_keyboard()
    flat_buttons = [btn for row in kb.inline_keyboard for btn in row]
    callbacks = [btn.callback_data for btn in flat_buttons]

    assert "presets_menu" in callbacks
    assert "models_menu" in callbacks
    assert "open_buy" in callbacks
    assert "settings_menu" in callbacks
    assert "main_menu" in callbacks
