from collections.abc import Callable

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

import platform_core.bot.handlers as bot_handlers
from platform_core.bot.handlers.common import _resolve_gettext
from platform_core.bot.keyboards import (
    get_cancel_keyboard,
    get_presets_keyboard,
)
from platform_core.bot.states import GenerationStates
from platform_core.presets import preset_manager

photo_router = Router(name="photo_router")


@photo_router.message(F.photo)
async def handle_photo_upload(
    message: Message,
    state: FSMContext,
    bot: Bot,
    bot_id: str = "default_bot",
    _: Callable[..., str] | None = None,
) -> None:
    """
    Handles user photo upload.
    If user already selected a preset (waiting_for_photo), immediately triggers generation.
    If photo has a text caption, uses caption as prompt directly with photo.
    Otherwise, saves photo reference_file_id in state and prompts user to pick a style preset.
    """
    gettext = _resolve_gettext(_)

    photo = message.photo[-1]  # Highest resolution
    state_data = await state.get_data()
    selected_preset_id = state_data.get("selected_preset_id")

    current_state = await state.get_state()

    # Flow B continuation: Preset was chosen first, now photo is uploaded
    if selected_preset_id or current_state == GenerationStates.waiting_for_photo.state:
        file_info = await bot.get_file(photo.file_id)
        photo_bytes_io = await bot.download_file(file_info.file_path)
        photo_bytes = photo_bytes_io.read()

        preset = (
            await preset_manager.get_preset_by_id(selected_preset_id)
            if selected_preset_id
            else None
        )
        if preset:
            await state.clear()
            prompt = preset.build_prompt()
            await bot_handlers.run_generation_job(
                bot=bot,
                chat_id=message.chat.id,
                user_id=message.from_user.id,
                prompt=prompt,
                preset_id=preset.id,
                reference_photo_bytes=photo_bytes,
                media_type=preset.media_type,
                model_name=preset.default_model,
                bot_id=bot_id,
                _=gettext,
            )
            return

    # Flow C: User is in Custom Prompt mode and uploads a photo
    if current_state == GenerationStates.entering_custom_prompt.state:
        if message.caption and message.caption.strip():
            file_info = await bot.get_file(photo.file_id)
            photo_bytes_io = await bot.download_file(file_info.file_path)
            photo_bytes = photo_bytes_io.read()

            caption_prompt = message.caption.strip()
            await state.clear()
            await bot_handlers.run_generation_job(
                bot=bot,
                chat_id=message.chat.id,
                user_id=message.from_user.id,
                prompt=caption_prompt,
                reference_photo_bytes=photo_bytes,
                media_type="image",
                bot_id=bot_id,
                _=gettext,
            )
            return

        # Store photo reference in state and ask for text prompt
        await state.update_data(reference_file_id=photo.file_id, selected_preset_id=None)
        await message.answer(
            gettext("custom_prompt_photo_received"),
            reply_markup=get_cancel_keyboard(_=gettext),
            parse_mode="Markdown",
        )
        return

    # Direct photo upload with caption prompt
    if message.caption and message.caption.strip():
        file_info = await bot.get_file(photo.file_id)
        photo_bytes_io = await bot.download_file(file_info.file_path)
        photo_bytes = photo_bytes_io.read()

        caption_prompt = message.caption.strip()
        await state.clear()
        await bot_handlers.run_generation_job(
            bot=bot,
            chat_id=message.chat.id,
            user_id=message.from_user.id,
            prompt=caption_prompt,
            reference_photo_bytes=photo_bytes,
            media_type="image",
            bot_id=bot_id,
            _=gettext,
        )
        return

    # Flow A start: Photo uploaded first -> Store lightweight file_id and prompt to choose a preset
    await state.update_data(reference_file_id=photo.file_id, selected_preset_id=None)
    await state.set_state(GenerationStates.selecting_preset)

    presets = await preset_manager.get_presets("image", bot_id=bot_id)
    kb = get_presets_keyboard(presets, has_photo=True, _=gettext)
    await message.answer(
        gettext("photo_received"),
        reply_markup=kb,
        parse_mode="Markdown",
    )
