from collections.abc import Callable

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

import platform_core.bot.handlers as bot_handlers
from platform_core.bot.handlers.common import (
    _resolve_gettext,
    _resolve_reference_photo,
)
from platform_core.bot.keyboards import get_waiting_for_photo_keyboard
from platform_core.bot.states import GenerationStates
from platform_core.db import UserProfile

prompt_router = Router(name="prompt_router")


@prompt_router.message(F.text & ~F.text.startswith("/"))
async def handle_custom_text_prompt(
    message: Message,
    state: FSMContext,
    bot: Bot,
    bot_id: str = "default_bot",
    user_profile: UserProfile | None = None,
    _: Callable[..., str] | None = None,
) -> None:
    """
    Handles custom prompt text messages.
    If user has chosen a preset (waiting_for_photo state), rejects text prompt since presets only allow photo uploads.
    If photo was stored in state, generates with photo + custom prompt text.
    If no photo is in state (pure text prompt outside presets), generates pure text-to-image without photo.
    """
    gettext = _resolve_gettext(_)

    current_state = await state.get_state()
    state_data = await state.get_data()

    # If user selected a preset, only photo upload is allowed. Reject text prompts inside preset flow.
    if current_state == GenerationStates.waiting_for_photo.state:
        preset_id = state_data.get("selected_preset_id", "")
        kb = get_waiting_for_photo_keyboard(preset_id, _=gettext)
        await message.answer(
            gettext("preset_photo_required"),
            reply_markup=kb,
            parse_mode="Markdown",
        )
        return

    prompt = message.text.strip()
    user_id = message.from_user.id

    ref_photo_bytes = await _resolve_reference_photo(bot, state_data)
    model_name = (user_profile and user_profile.selected_model) or "google/gemini-2.5-flash-image"

    await state.clear()
    await bot_handlers.run_generation_job(
        bot=bot,
        chat_id=message.chat.id,
        user_id=user_id,
        prompt=prompt,
        reference_photo_bytes=ref_photo_bytes,
        media_type="image",
        model_name=model_name,
        bot_id=bot_id,
        _=gettext,
    )
