from unittest.mock import AsyncMock, MagicMock
import pytest
from aiogram.types import User as TelegramUser, Message, CallbackQuery, Chat
from platform_core.config import settings
from platform_core.presets import PromptPreset, preset_manager
from bots.admin_bot.bot import (
    AdminAuthMiddleware,
    cmd_admin_menu,
    cb_presets_list,
    cb_preset_detail,
    cb_preset_toggle,
    cb_preset_del_do,
)


@pytest.mark.asyncio
async def test_admin_auth_middleware_denied():
    middleware = AdminAuthMiddleware()
    handler = AsyncMock()

    # Configure admin IDs
    settings.ADMIN_USER_IDS_RAW = "99999,88888"

    # Non-admin user event
    non_admin_user = TelegramUser(id=11111, is_bot=False, first_name="Unauthorized")
    event = MagicMock(spec=Message)
    event.answer = AsyncMock()

    data = {"event_from_user": non_admin_user}

    result = await middleware(handler, event, data)
    assert result is None
    handler.assert_not_called()
    event.answer.assert_called_once()
    assert "Access Denied" in event.answer.call_args[0][0]

    settings.ADMIN_USER_IDS_RAW = None  # Reset


@pytest.mark.asyncio
async def test_admin_auth_middleware_allowed():
    middleware = AdminAuthMiddleware()
    handler = AsyncMock(return_value="handled_ok")

    settings.ADMIN_USER_IDS_RAW = "99999,88888"

    admin_user = TelegramUser(id=99999, is_bot=False, first_name="AuthorizedAdmin")
    event = MagicMock(spec=Message)
    data = {"event_from_user": admin_user}

    result = await middleware(handler, event, data)
    assert result == "handled_ok"
    handler.assert_called_once_with(event, data)

    settings.ADMIN_USER_IDS_RAW = None  # Reset


@pytest.mark.asyncio
async def test_admin_menu_handler():
    message = AsyncMock(spec=Message)
    message.answer = AsyncMock()
    state = AsyncMock()

    await cmd_admin_menu(message, state)

    state.clear.assert_called_once()
    message.answer.assert_called_once()
    assert "Platform Admin Control Panel" in message.answer.call_args[0][0]


@pytest.mark.asyncio
async def test_admin_preset_management_handlers():
    # 1. Create test preset
    test_p = PromptPreset(
        id="adm_test_1",
        title="Admin Test Preset",
        description="For unit testing admin bot",
        prompt_template="Test prompt, {user_prompt}",
        is_active=True,
    )
    await preset_manager.save_preset(test_p)

    # 2. Test cb_presets_list
    cb_list = AsyncMock(spec=CallbackQuery)
    cb_list.message = AsyncMock()
    cb_list.message.edit_text = AsyncMock()
    cb_list.answer = AsyncMock()

    await cb_presets_list(cb_list)
    cb_list.message.edit_text.assert_called_once()
    assert "NoSQL Prompt Presets" in cb_list.message.edit_text.call_args[0][0]

    # 3. Test cb_preset_detail
    cb_detail = AsyncMock(spec=CallbackQuery)
    cb_detail.data = "pdetail:adm_test_1"
    cb_detail.message = AsyncMock()
    cb_detail.message.edit_text = AsyncMock()
    cb_detail.answer = AsyncMock()

    await cb_preset_detail(cb_detail)
    cb_detail.message.edit_text.assert_called_once()
    assert "Admin Test Preset" in cb_detail.message.edit_text.call_args[0][0]

    # 4. Test cb_preset_toggle
    cb_toggle = AsyncMock(spec=CallbackQuery)
    cb_toggle.data = "ptoggle:adm_test_1:false"
    cb_toggle.message = AsyncMock()
    cb_toggle.message.edit_text = AsyncMock()
    cb_toggle.answer = AsyncMock()

    await cb_preset_toggle(cb_toggle)
    updated = await preset_manager.get_preset_by_id("adm_test_1")
    assert updated.is_active is False

    # 5. Test cb_preset_del_do
    cb_del = AsyncMock(spec=CallbackQuery)
    cb_del.data = "pdel_do:adm_test_1"
    cb_del.message = AsyncMock()
    cb_del.message.edit_text = AsyncMock()
    cb_del.answer = AsyncMock()

    await cb_preset_del_do(cb_del)
    deleted = await preset_manager.get_preset_by_id("adm_test_1")
    assert deleted is None


def test_build_main_admin_keyboard():
    from bots.admin_bot.bot import build_main_admin_keyboard
    kb = build_main_admin_keyboard()
    assert kb.inline_keyboard
    for row in kb.inline_keyboard:
        for button in row:
            assert button.text
            assert button.callback_data is not None
            assert len(button.callback_data) > 0

