import base64
import contextlib
import logging
import time
import uuid
from collections.abc import Callable
from typing import Any

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message

from platform_core.bot.keyboards import (
    get_cancel_keyboard,
    get_help_keyboard,
    get_language_keyboard,
    get_models_keyboard,
    get_presets_keyboard,
    get_settings_keyboard,
    get_star_packages_keyboard,
    get_waiting_for_photo_keyboard,
)
from platform_core.bot.states import GenerationStateData, GenerationStates
from platform_core.db import UserBalance, UserProfile, db
from platform_core.events import (
    CommandEvent,
    GenerationEvent,
    MessageSentEvent,
    get_tracker,
)
from platform_core.generators import DEFAULT_AVAILABLE_MODELS, GenerationRequest, GeneratorFactory
from platform_core.i18n import SUPPORTED_LANGUAGES, i18n
from platform_core.payments.packages import STAR_PACKAGES
from platform_core.presets import preset_manager
from platform_core.queue import GenerationJob, task_broker

logger = logging.getLogger(__name__)
core_router = Router(name="core_router")


def _resolve_gettext(_: Callable[..., str] | None) -> Callable[..., str]:
    return _ if _ is not None else i18n.get


def get_translator(data_dict: dict[str, Any]) -> Callable[..., str]:
    """Helper to extract translation function from handler data or fallback to default."""
    if "_" in data_dict and callable(data_dict["_"]):
        return data_dict["_"]
    user_lang = data_dict.get("user_lang", "en")

    def _tr(key: str, **kwargs: Any) -> str:
        return i18n.get(key, lang=user_lang, **kwargs)

    return _tr


async def run_generation_job(
    bot: Bot,
    chat_id: int,
    user_id: int,
    prompt: str,
    preset_id: str | None = None,
    reference_photo_bytes: bytes | None = None,
    media_type: str = "image",
    model_name: str = "google/gemini-2.5-flash-image",
    bot_id: str = "default_bot",
    force_mock: bool = False,
    use_queue: bool = True,
    _: Callable[..., str] | None = None,
) -> None:
    """Executes AI generation workflow, checks credits, delivers media, and logs history."""
    gettext = _resolve_gettext(_)
    tracker = get_tracker(bot_id)

    # 1. Credit Check
    has_credit = await db.deduct_user_credit(user_id, amount=1)
    if not has_credit:
        kb = get_star_packages_keyboard(STAR_PACKAGES, _=gettext)
        await bot.send_message(
            chat_id=chat_id,
            text=gettext("out_of_credits"),
            reply_markup=kb,
            parse_mode="Markdown",
        )
        await tracker.track(
            MessageSentEvent(
                distinct_id=user_id,
                bot_id=bot_id,
                message_type="out_of_credits",
                has_reply_markup=True,
            )
        )
        return

    status_msg = await bot.send_message(
        chat_id=chat_id,
        text=gettext("generating_creation"),
        parse_mode="Markdown",
    )

    if use_queue:
        ref_b64 = None
        if reference_photo_bytes:
            ref_b64 = base64.b64encode(reference_photo_bytes).decode("utf-8")

        job = GenerationJob(
            job_id=str(uuid.uuid4()),
            bot_id=bot_id,
            bot_token=bot.token,
            user_id=user_id,
            chat_id=chat_id,
            status_message_id=status_msg.message_id,
            prompt=prompt,
            model_name=model_name,
            media_type=media_type,
            cost=1,
            reference_photo_b64=ref_b64,
        )
        await task_broker.enqueue_job(job)
        return

    start_time = time.time()
    generator = GeneratorFactory.get_generator(force_mock=force_mock)

    req = GenerationRequest(
        prompt=prompt,
        model_name=model_name,
        reference_photo_bytes=reference_photo_bytes,
        media_type=media_type,
    )

    res = await generator.generate(req)
    duration_ms = res.duration_ms or int((time.time() - start_time) * 1000)

    if res.status == "success":
        # Deliver generated result
        if res.media_bytes:
            input_file = BufferedInputFile(
                res.media_bytes, filename=f"generation_{int(time.time())}.jpg"
            )
            await bot.send_photo(
                chat_id=chat_id,
                photo=input_file,
                caption=gettext(
                    "generation_complete", prompt=prompt[:100], latency=duration_ms / 1000.0
                ),
                parse_mode="Markdown",
            )
        elif res.media_urls:
            first_url = res.media_urls[0]
            await bot.send_photo(
                chat_id=chat_id,
                photo=first_url,
                caption=gettext(
                    "generation_complete", prompt=prompt[:100], latency=duration_ms / 1000.0
                ),
                parse_mode="Markdown",
            )

        with contextlib.suppress(Exception):
            await bot.delete_message(chat_id=chat_id, message_id=status_msg.message_id)

        # Explicitly track generation and message sent
        await tracker.track(
            GenerationEvent(
                distinct_id=user_id,
                bot_id=bot_id,
                model_name=model_name,
                prompt=prompt,
                preset_id=preset_id,
                media_url=res.media_urls[0] if res.media_urls else None,
                status="success",
                duration_ms=duration_ms,
            )
        )
        await tracker.track(
            MessageSentEvent(
                distinct_id=user_id,
                bot_id=bot_id,
                message_type="photo",
                has_reply_markup=False,
            )
        )
    else:
        # Failure
        await status_msg.edit_text(
            gettext("generation_failed", error=res.error_message or "Unknown error"),
            parse_mode="Markdown",
        )
        # Refund credit on engine failure
        await db.add_user_credits(
            user_id=user_id,
            bot_id=bot_id,
            stars_paid=0,
            credits_to_add=1,
            telegram_charge_id="refund",
        )

        await tracker.track(
            GenerationEvent(
                distinct_id=user_id,
                bot_id=bot_id,
                model_name=model_name,
                prompt=prompt,
                preset_id=preset_id,
                status="failed",
                duration_ms=duration_ms,
                error_message=res.error_message,
            )
        )


@core_router.message(CommandStart())
async def handle_start_command(
    message: Message,
    user_balance: UserBalance | None = None,
    bot_id: str = "default_bot",
    _: Callable[..., str] | None = None,
) -> None:
    gettext = _resolve_gettext(_)

    tracker = get_tracker(bot_id)
    await tracker.track(
        CommandEvent(
            distinct_id=message.from_user.id,
            bot_id=bot_id,
            command="/start",
        )
    )

    credits = user_balance.credits_remaining if user_balance else 3
    presets = await preset_manager.get_presets("image", bot_id=bot_id)
    welcome_text = gettext("welcome_text", credits=credits)
    kb = get_presets_keyboard(presets, _=gettext)
    await message.answer(welcome_text, reply_markup=kb, parse_mode="Markdown")

    await tracker.track(
        MessageSentEvent(
            distinct_id=message.from_user.id,
            bot_id=bot_id,
            message_type="menu",
            text_length=len(welcome_text),
            has_reply_markup=True,
        )
    )


@core_router.message(Command("generate"))
@core_router.message(Command("create"))
@core_router.message(Command("presets"))
@core_router.callback_query(F.data == "generate_menu")
@core_router.callback_query(F.data == "presets_menu")
@core_router.callback_query(F.data == "main_menu")
async def handle_presets_menu(
    event: Message | CallbackQuery,
    bot_id: str = "default_bot",
    _: Callable[..., str] | None = None,
) -> None:
    gettext = _resolve_gettext(_)

    presets = await preset_manager.get_presets("image", bot_id=bot_id)
    kb = get_presets_keyboard(presets, _=gettext)
    text = gettext("presets_menu_title")
    if isinstance(event, CallbackQuery):
        await event.answer()
        await event.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    else:
        await event.answer(text, reply_markup=kb, parse_mode="Markdown")


@core_router.message(Command("reload_presets"))
async def handle_reload_presets_command(
    message: Message,
    _: Callable[..., str] | None = None,
) -> None:
    """Admin command to force reload remote presets from Supabase or Remote JSON URL."""
    gettext = _resolve_gettext(_)

    reloaded = await preset_manager.fetch_presets(force_reload=True)
    await message.answer(
        gettext("presets_refreshed", count=len(reloaded)),
        parse_mode="Markdown",
    )


@core_router.message(Command("buy"))
@core_router.message(Command("stars"))
@core_router.message(Command("balance"))
@core_router.callback_query(F.data == "open_buy")
async def handle_buy_menu(
    event: Message | CallbackQuery,
    user_balance: UserBalance | None = None,
    _: Callable[..., str] | None = None,
) -> None:
    gettext = _resolve_gettext(_)

    user_id = event.from_user.id
    balance = user_balance or await db.get_user_balance(user_id)
    text = gettext(
        "buy_menu_title", credits=balance.credits_remaining, stars=balance.total_stars_spent
    )
    kb = get_star_packages_keyboard(STAR_PACKAGES, _=gettext)
    if isinstance(event, CallbackQuery):
        await event.answer()
        await event.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    else:
        await event.answer(text, reply_markup=kb, parse_mode="Markdown")


# --- HELP & DOCUMENTATION HANDLERS ---


@core_router.message(Command("help"))
@core_router.message(Command("info"))
@core_router.callback_query(F.data == "help_menu")
async def handle_help_command(
    event: Message | CallbackQuery,
    bot_id: str = "default_bot",
    _: Callable[..., str] | None = None,
) -> None:
    """Handles /help command and displays complete usage documentation and shortcuts."""
    gettext = _resolve_gettext(_)

    tracker = get_tracker(bot_id)
    user_id = event.from_user.id
    await tracker.track(
        CommandEvent(
            distinct_id=user_id,
            bot_id=bot_id,
            command="/help",
        )
    )

    text = gettext("help_text")
    kb = get_help_keyboard(_=gettext)

    if isinstance(event, CallbackQuery):
        await event.answer()
        await event.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    else:
        await event.answer(text, reply_markup=kb, parse_mode="Markdown")

    await tracker.track(
        MessageSentEvent(
            distinct_id=user_id,
            bot_id=bot_id,
            message_type="help",
            text_length=len(text),
            has_reply_markup=True,
        )
    )


# --- SETTINGS & LOCALIZATION HANDLERS ---


@core_router.message(Command("settings"))
@core_router.callback_query(F.data == "settings_menu")
async def handle_settings_menu(
    event: Message | CallbackQuery,
    user_lang: str = "en",
    _: Callable[..., str] | None = None,
) -> None:
    gettext = _resolve_gettext(_)

    lang_display = SUPPORTED_LANGUAGES.get(user_lang, user_lang)
    text = gettext("settings_title", language=lang_display)
    kb = get_settings_keyboard(_=gettext)

    if isinstance(event, CallbackQuery):
        await event.answer()
        await event.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    else:
        await event.answer(text, reply_markup=kb, parse_mode="Markdown")


@core_router.callback_query(F.data == "change_language")
async def handle_change_language_menu(
    callback: CallbackQuery,
    user_lang: str = "en",
    _: Callable[..., str] | None = None,
) -> None:
    gettext = _resolve_gettext(_)

    await callback.answer()
    text = gettext("select_language_title")
    kb = get_language_keyboard(current_lang=user_lang, _=gettext)
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")


@core_router.callback_query(F.data.startswith("set_lang:"))
async def handle_set_language(
    callback: CallbackQuery,
    user_profile: UserProfile | None = None,
) -> None:
    lang_code = callback.data.split("set_lang:")[1]
    normalized_lang = i18n.normalize_language_code(lang_code)
    user_id = callback.from_user.id

    # Update database / profile persistently
    await db.update_user_language(telegram_id=user_id, language_code=normalized_lang)

    def new_translator(key: str, **kwargs: Any) -> str:
        return i18n.get(key, lang=normalized_lang, **kwargs)

    lang_display = SUPPORTED_LANGUAGES.get(normalized_lang, normalized_lang)
    alert_text = new_translator("language_changed", language=lang_display)

    await callback.answer(alert_text, show_alert=True)

    # Render updated settings menu in newly selected language
    text = new_translator("settings_title", language=lang_display)
    kb = get_settings_keyboard(_=new_translator)
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")


# --- MODEL SELECTION HANDLERS ---


@core_router.message(Command("models"))
@core_router.callback_query(F.data == "models_menu")
async def handle_models_menu(
    event: Message | CallbackQuery,
    user_profile: UserProfile | None = None,
    _: Callable[..., str] | None = None,
) -> None:
    """Displays AI Model Selection menu with current active model checked."""
    gettext = _resolve_gettext(_)

    current_model = (
        user_profile and user_profile.selected_model
    ) or "google/gemini-2.5-flash-image"
    kb = get_models_keyboard(DEFAULT_AVAILABLE_MODELS, current_model, _=gettext)
    short_name = current_model.split("/")[-1]
    text = gettext("models_menu_title", current_model=short_name)

    if isinstance(event, CallbackQuery):
        await event.answer()
        await event.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    else:
        await event.answer(text, reply_markup=kb, parse_mode="Markdown")


@core_router.callback_query(F.data.startswith("set_model:"))
async def handle_set_model(
    callback: CallbackQuery,
    user_profile: UserProfile | None = None,
    _: Callable[..., str] | None = None,
) -> None:
    """Persists user model selection and refreshes the model menu."""
    gettext = _resolve_gettext(_)

    model_name = callback.data.split("set_model:")[1]
    user_id = callback.from_user.id

    # Persist user model selection
    await db.update_user_model(telegram_id=user_id, model_name=model_name)
    if user_profile:
        user_profile.selected_model = model_name

    short_name = model_name.split("/")[-1]
    alert_text = gettext("model_changed", model=short_name)
    await callback.answer(alert_text, show_alert=True)

    # Re-render models menu with new checkmark
    kb = get_models_keyboard(DEFAULT_AVAILABLE_MODELS, model_name, _=gettext)
    text = gettext("models_menu_title", current_model=short_name)
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")


# --- GENERATION & PROMPT HANDLERS ---


@core_router.callback_query(F.data == "cancel_action")
@core_router.message(Command("cancel"))
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


async def _resolve_reference_photo(
    bot: Bot, state_data: dict[str, Any] | GenerationStateData
) -> bytes | None:
    """
    Resolves photo bytes from FSM state data.
    Supports lightweight reference_file_id (downloaded on demand) and legacy reference_photo_bytes.
    """
    if isinstance(state_data, GenerationStateData):
        ref_bytes = state_data.reference_photo_bytes
        ref_file_id = state_data.reference_file_id
    else:
        ref_bytes = state_data.get("reference_photo_bytes")
        ref_file_id = state_data.get("reference_file_id")

    if ref_bytes:
        return ref_bytes
    if ref_file_id:
        file_info = await bot.get_file(ref_file_id)
        photo_bytes_io = await bot.download_file(file_info.file_path)
        return photo_bytes_io.read()
    return None


@core_router.callback_query(F.data.startswith("preset:"))
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
        await run_generation_job(
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


@core_router.message(F.photo)
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
            await run_generation_job(
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
            await run_generation_job(
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
        await run_generation_job(
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


@core_router.message(F.text & ~F.text.startswith("/"))
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
    await run_generation_job(
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
