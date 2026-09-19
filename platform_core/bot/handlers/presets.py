from collections.abc import Callable

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

import platform_core.bot.handlers as bot_handlers
from platform_core.bot.handlers.common import (
    _resolve_gettext,
    _resolve_reference_photo,
)
from platform_core.bot.keyboards import (
    get_cancel_keyboard,
    get_presets_keyboard,
    get_waiting_for_photo_keyboard,
)
from platform_core.bot.states import GenerationStates
from platform_core.presets import preset_manager

presets_router = Router(name="presets_router")


@presets_router.callback_query(F.data == "cancel_action")
@presets_router.message(Command("cancel"))
async def handle_cancel_action(
    event: Message | CallbackQuery,
    state: FSMContext,
    bot_id: str = "default_bot",
    _: Callable[..., str] | None = None,
) -> None:
    """Cancels current selection or active generation state."""
    gettext = _resolve_gettext(_)

    await state.clear()
    text = gettext("action_cancelled")
    presets = await preset_manager.get_presets("image", bot_id=bot_id)
    kb = get_presets_keyboard(presets, has_photo=False, _=gettext)

    if isinstance(event, CallbackQuery):
        await event.answer()
        await event.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    else:
        await event.answer(text, reply_markup=kb, parse_mode="Markdown")


@presets_router.callback_query(F.data.startswith("preset:"))
async def handle_preset_selection(
    callback: CallbackQuery,
    state: FSMContext,
    bot: Bot,
    bot_id: str = "default_bot",
    _: Callable[..., str] | None = None,
) -> None:
    """
    Handles style preset selection.
    If reference photo is already uploaded, immediately generates with photo.
    If no photo is uploaded yet, transitions to waiting_for_photo state so user can upload photo.
    """
    gettext = _resolve_gettext(_)

    preset_id = callback.data.split("preset:")[1]
    user_id = callback.from_user.id

    state_data = await state.get_data()
    has_photo = bool(state_data.get("reference_file_id") or state_data.get("reference_photo_bytes"))

    if preset_id == "custom":
        await state.set_state(GenerationStates.entering_custom_prompt)
        await callback.answer()
        prompt_text = (
            gettext("custom_prompt_with_photo") if has_photo else gettext("enter_custom_prompt")
        )
        await callback.message.answer(
            prompt_text,
            reply_markup=get_cancel_keyboard(_=gettext),
            parse_mode="Markdown",
        )
        return

    preset = await preset_manager.get_preset_by_id(preset_id)
    if not preset:
        await callback.answer("Preset not found.", show_alert=True)
        return

    # Flow A: Photo was already uploaded -> Generate immediately with photo
    if has_photo:
        await callback.answer(f"Selected: {preset.title}")
        ref_photo_bytes = await _resolve_reference_photo(bot, state_data)
        await state.clear()
        prompt = preset.build_prompt()
        await bot_handlers.run_generation_job(
            bot=bot,
            chat_id=callback.message.chat.id,
            user_id=user_id,
            prompt=prompt,
            preset_id=preset.id,
            reference_photo_bytes=ref_photo_bytes,
            media_type=preset.media_type,
            model_name=preset.default_model,
            bot_id=bot_id,
            _=gettext,
        )
        return

    # Flow B: No photo yet -> Store chosen preset and request photo upload from user
    await state.update_data(selected_preset_id=preset.id)
    await state.set_state(GenerationStates.waiting_for_photo)
    await callback.answer(f"Selected: {preset.title}")

    waiting_text = gettext("preset_selected_send_photo", preset_title=preset.title)
    kb = get_waiting_for_photo_keyboard(preset.id, _=gettext)
    await callback.message.answer(
        waiting_text,
        reply_markup=kb,
        parse_mode="Markdown",
    )
