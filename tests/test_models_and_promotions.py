from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from aiogram.types import CallbackQuery, Message
from aiogram.types import User as TelegramUser

from platform_core.bot.handlers import handle_models_menu, handle_set_model
from platform_core.db import UserProfile, db
from platform_core.modules import ImageGenModule, ModularBotBuilder
from platform_core.presets import PromptPreset, preset_manager


@pytest.mark.asyncio
async def test_handle_models_menu_command():
    message = AsyncMock(spec=Message)
    message.answer = AsyncMock()

    user_profile = UserProfile(telegram_id=12345, selected_model="black-forest-labs/flux-1.1-pro")
    await handle_models_menu(message, user_profile=user_profile)

    message.answer.assert_called_once()
    args, kwargs = message.answer.call_args
    assert "flux-1.1-pro" in args[0]
    keyboard = kwargs.get("reply_markup")
    assert keyboard is not None
    # Check that flux-1.1-pro is marked with checkmark
    flux_button = None
    for row in keyboard.inline_keyboard:
        for btn in row:
            if "flux-1.1-pro" in btn.text:
                flux_button = btn
    assert flux_button is not None
    assert "✅" in flux_button.text


@pytest.mark.asyncio
async def test_handle_set_model_callback():
    callback = AsyncMock(spec=CallbackQuery)
    callback.data = "set_model:openai/dall-e-3"
    callback.from_user = TelegramUser(id=12345, is_bot=False, first_name="TestUser")
    callback.answer = AsyncMock()
    callback.message = AsyncMock(spec=Message)
    callback.message.edit_text = AsyncMock()

    user_profile = UserProfile(telegram_id=12345, selected_model="google/gemini-2.5-flash-image")
    await handle_set_model(callback, user_profile=user_profile)

    assert user_profile.selected_model == "openai/dall-e-3"
    callback.answer.assert_called_once()
    assert "dall-e-3" in callback.answer.call_args[0][0]

    # Verify db update
    db_profile = await db.sync_user(telegram_id=12345)
    assert db_profile.selected_model == "openai/dall-e-3"

    callback.message.edit_text.assert_called_once()
    args, _ = callback.message.edit_text.call_args
    assert "dall-e-3" in args[0]


@pytest.mark.asyncio
async def test_common_presets_with_bot_specific_promotions(tmp_path: Path):
    """
    Tests the scenario described by user:
    Two image bots share common presets from database/catalog,
    but Bot 1 promotes 'make you bald' (bald_portrait)
    and Bot 2 promotes 'Harry Potter' (harry_potter).
    Both bots can see all presets, but their promoted preset is shown first!
    """
    preset_manager.clear_custom_presets()
    await preset_manager.seed_presets_from_file("bots/image_bot/presets.yaml")

    # Define custom preset for Bot 1 (Bald Portrait)
    bald_preset = PromptPreset(
        id="bald_portrait",
        title="Make You Bold on Photo",
        description="Transform photo into a smooth bald look",
        icon="🧑‍𘲰",
        prompt_template="Hyper-realistic portrait of {user_prompt} completely bald, clean shaved head",
        category="Funny & Transformations",
    )

    # Bot 1 Builder: promotes 'bald_portrait'
    bot1_builder = (
        ModularBotBuilder(bot_id="bald_bot", token="12345:TOKEN_BALD")
        .add_module(ImageGenModule())
        .add_preset(bald_preset, promote=True)
    )
    _ = bot1_builder.build()

    # Bot 2 Builder: promotes 'harry_potter' (which is in standard defaults)
    bot2_builder = (
        ModularBotBuilder(bot_id="harry_potter_bot", token="12345:TOKEN_HP")
        .add_module(ImageGenModule())
        .set_promoted_preset_ids(["harry_potter"])
    )
    _ = bot2_builder.build()

    # 1. Fetch presets for Bot 1 (bald_bot)
    bot1_presets = await preset_manager.get_presets(media_type="image", bot_id="bald_bot")
    # Bot 1 should have bald_portrait at the beginning
    assert bot1_presets[0].id == "bald_portrait"
    # But Bot 1 should ALSO have all common presets including harry_potter, odyssey, etc.
    bot1_ids = [p.id for p in bot1_presets]
    assert "harry_potter" in bot1_ids
    assert "odyssey" in bot1_ids
    assert "cyberpunk" in bot1_ids

    # 2. Fetch presets for Bot 2 (harry_potter_bot)
    bot2_presets = await preset_manager.get_presets(media_type="image", bot_id="harry_potter_bot")
    # Bot 2 should have harry_potter at the beginning
    assert bot2_presets[0].id == "harry_potter"
    # But Bot 2 should ALSO have bald_portrait and other common presets
    bot2_ids = [p.id for p in bot2_presets]
    assert "bald_portrait" in bot2_ids
    assert "odyssey" in bot2_ids
    assert "cyberpunk" in bot2_ids


@pytest.mark.asyncio
async def test_bot_yaml_config_promoted_presets(tmp_path: Path):
    preset_manager.clear_custom_presets()
    await preset_manager.seed_presets_from_file("bots/image_bot/presets.yaml")

    config_file = tmp_path / "custom_bot.yaml"
    config_file.write_text(
        """
bot_id: "promo_test_bot"
token: "12345:TOKEN_PROMO"
promoted_presets:
  - "anime_hero"
  - "renaissance"
modules:
  - name: "image_gen"
    enabled: true
""",
        encoding="utf-8",
    )

    builder = ModularBotBuilder.from_config(config_file)
    _ = builder.build()

    presets = await preset_manager.get_presets(media_type="image", bot_id="promo_test_bot")
    assert len(presets) >= 2
    assert presets[0].id == "anime_hero"
    assert presets[1].id == "renaissance"
    # Remaining common presets follow
    remaining_ids = [p.id for p in presets[2:]]
    assert "odyssey" in remaining_ids
