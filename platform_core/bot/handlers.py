import base64
import io
import logging
import time
import uuid
from typing import List, Optional, Callable, Dict, Any
from aiogram import Router, F, Bot
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from platform_core.bot.keyboards import (
    get_presets_keyboard,
    get_models_keyboard,
    get_star_packages_keyboard,
    get_main_action_keyboard,
    get_settings_keyboard,
    get_language_keyboard,
)
from platform_core.bot.states import GenerationStates
from platform_core.db import db, GenerationLog, UserBalance, UserProfile
from platform_core.generators import GeneratorFactory, GenerationRequest
from platform_core.i18n import i18n, SUPPORTED_LANGUAGES
from platform_core.payments.packages import STAR_PACKAGES
from platform_core.presets import preset_manager, PromptPreset
from platform_core.queue import task_broker, GenerationJob

logger = logging.getLogger(__name__)
core_router = Router(name="core_router")


def get_translator(data_dict: Dict[str, Any]) -> Callable[..., str]:
    """Helper to extract translation function from handler data or fallback to default."""
    if "_" in data_dict and callable(data_dict["_"]):
        return data_dict["_"]
    user_lang = data_dict.get("user_lang", "en")
    return lambda key, **kwargs: i18n.get(key, lang=user_lang, **kwargs)


async def run_generation_job(
    bot: Bot,
    chat_id: int,
    user_id: int,
    prompt: str,
    preset_id: Optional[str] = None,
    reference_photo_bytes: Optional[bytes] = None,
    media_type: str = "image",
    model_name: str = "black-forest-labs/flux-schnell",
    bot_id: str = "default_bot",
    force_mock: bool = False,
    use_queue: bool = True,
    _: Optional[Callable[..., str]] = None,
):
    """Executes AI generation workflow, checks credits, delivers media, and logs history."""
    if _ is None:
        _ = lambda k, **kw: i18n.get(k, **kw)

    # 1. Credit Check
    has_credit = await db.deduct_user_credit(user_id, amount=1)
    if not has_credit:
        kb = get_star_packages_keyboard(STAR_PACKAGES, _=_)
        await bot.send_message(
            chat_id=chat_id,
            text=_("out_of_credits"),
            reply_markup=kb,
            parse_mode="Markdown",
        )
        return

    status_msg = await bot.send_message(
        chat_id=chat_id,
        text=_("generating_creation"),
        parse_mode="Markdown"
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
            input_file = BufferedInputFile(res.media_bytes, filename=f"generation_{int(time.time())}.jpg")
            await bot.send_photo(
                chat_id=chat_id,
                photo=input_file,
                caption=_("generation_complete", prompt=prompt[:100], latency=duration_ms / 1000.0),
                parse_mode="Markdown",
            )
        elif res.media_urls:
            first_url = res.media_urls[0]
            await bot.send_photo(
                chat_id=chat_id,
                photo=first_url,
                caption=_("generation_complete", prompt=prompt[:100], latency=duration_ms / 1000.0),
                parse_mode="Markdown",
            )

        try:
            await bot.delete_message(chat_id=chat_id, message_id=status_msg.message_id)
        except Exception:
            pass

        # Log generation
        await db.log_generation(
            GenerationLog(
                bot_id=bot_id,
                user_id=user_id,
                model_name=model_name,
                prompt=prompt,
                preset_id=preset_id,
                media_url=res.media_urls[0] if res.media_urls else None,
                status="success",
                duration_ms=duration_ms,
            )
        )
    else:
        # Failure
        await status_msg.edit_text(
            _("generation_failed", error=res.error_message or "Unknown error"),
            parse_mode="Markdown"
        )
        # Refund credit on engine failure
        await db.add_user_credits(user_id=user_id, bot_id=bot_id, stars_paid=0, credits_to_add=1, telegram_charge_id="refund")

        await db.log_generation(
            GenerationLog(
                bot_id=bot_id,
                user_id=user_id,
                model_name=model_name,
                prompt=prompt,
                preset_id=preset_id,
                status="failed",
                duration_ms=duration_ms,
                error_message=res.error_message,
            )
        )


@core_router.message(CommandStart())
async def handle_start_command(message: Message, user_balance: Optional[UserBalance] = None, _: Optional[Callable[..., str]] = None):
    if _ is None:
        _ = lambda k, **kw: i18n.get(k, **kw)

    credits = user_balance.credits_remaining if user_balance else 3
    presets = await preset_manager.get_presets("image")
    welcome_text = _("welcome_text", credits=credits)
    kb = get_presets_keyboard(presets, _=_)
    await message.answer(welcome_text, reply_markup=kb, parse_mode="Markdown")


@core_router.message(Command("presets"))
@core_router.callback_query(F.data == "presets_menu")
@core_router.callback_query(F.data == "main_menu")
async def handle_presets_menu(event: Message | CallbackQuery, _: Optional[Callable[..., str]] = None):
    if _ is None:
        _ = lambda k, **kw: i18n.get(k, **kw)

    presets = await preset_manager.get_presets("image")
    kb = get_presets_keyboard(presets, _=_)
    text = _("presets_menu_title")
    if isinstance(event, CallbackQuery):
        await event.answer()
        await event.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    else:
        await event.answer(text, reply_markup=kb, parse_mode="Markdown")


@core_router.message(Command("reload_presets"))
async def handle_reload_presets_command(message: Message, _: Optional[Callable[..., str]] = None):
    """Admin command to force reload remote presets from Supabase or Remote JSON URL."""
    if _ is None:
        _ = lambda k, **kw: i18n.get(k, **kw)

    reloaded = await preset_manager.fetch_presets(force_reload=True)
    await message.answer(
        _("presets_refreshed", count=len(reloaded)),
        parse_mode="Markdown"
    )


@core_router.message(Command("buy"))
@core_router.message(Command("stars"))
@core_router.message(Command("balance"))
@core_router.callback_query(F.data == "open_buy")
async def handle_buy_menu(event: Message | CallbackQuery, user_balance: Optional[UserBalance] = None, _: Optional[Callable[..., str]] = None):
    if _ is None:
        _ = lambda k, **kw: i18n.get(k, **kw)

    user_id = event.from_user.id
    balance = user_balance or await db.get_user_balance(user_id)
    text = _("buy_menu_title", credits=balance.credits_remaining, stars=balance.total_stars_spent)
    kb = get_star_packages_keyboard(STAR_PACKAGES, _=_)
    if isinstance(event, CallbackQuery):
        await event.answer()
        await event.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    else:
        await event.answer(text, reply_markup=kb, parse_mode="Markdown")


@core_router.message(Command("stats"))
@core_router.callback_query(F.data == "show_stats")
async def handle_stats_command(event: Message | CallbackQuery, bot_id: str = "default_bot", _: Optional[Callable[..., str]] = None):
    if _ is None:
        _ = lambda k, **kw: i18n.get(k, **kw)

    metrics = await db.get_metrics_summary(bot_id=bot_id)
    text = _(
        "stats_title",
        total_users=metrics['total_users'],
        total_commands=metrics['total_commands'],
        total_button_clicks=metrics['total_button_clicks'],
        total_generations=metrics['total_generations'],
        successful_generations=metrics['successful_generations'],
        total_stars_earned=metrics['total_stars_earned'],
    )
    if metrics["top_presets"]:
        text += _("top_presets")
        for preset_name, count in metrics["top_presets"]:
            text += f"• `{preset_name}`: {count}\n"

    if isinstance(event, CallbackQuery):
        await event.answer()
        await event.message.answer(text, parse_mode="Markdown")
    else:
        await event.answer(text, parse_mode="Markdown")


# --- SETTINGS & LOCALIZATION HANDLERS ---

@core_router.message(Command("settings"))
@core_router.callback_query(F.data == "settings_menu")
async def handle_settings_menu(
    event: Message | CallbackQuery,
    user_lang: str = "en",
    _: Optional[Callable[..., str]] = None
):
    if _ is None:
        _ = lambda k, **kw: i18n.get(k, **kw)

    lang_display = SUPPORTED_LANGUAGES.get(user_lang, user_lang)
    text = _("settings_title", language=lang_display)
    kb = get_settings_keyboard(_=_)

    if isinstance(event, CallbackQuery):
        await event.answer()
        await event.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    else:
        await event.answer(text, reply_markup=kb, parse_mode="Markdown")


@core_router.callback_query(F.data == "change_language")
async def handle_change_language_menu(
    callback: CallbackQuery,
    user_lang: str = "en",
    _: Optional[Callable[..., str]] = None
):
    if _ is None:
        _ = lambda k, **kw: i18n.get(k, **kw)

    await callback.answer()
    text = _("select_language_title")
    kb = get_language_keyboard(current_lang=user_lang, _=_)
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")


@core_router.callback_query(F.data.startswith("set_lang:"))
async def handle_set_language(
    callback: CallbackQuery,
    user_profile: Optional[UserProfile] = None
):
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


# --- GENERATION & PROMPT HANDLERS ---

@core_router.callback_query(F.data.startswith("preset:"))
async def handle_preset_selection(
    callback: CallbackQuery,
    state: FSMContext,
    bot: Bot,
    bot_id: str = "default_bot",
    _: Optional[Callable[..., str]] = None
):
    if _ is None:
        _ = lambda k, **kw: i18n.get(k, **kw)

    preset_id = callback.data.split("preset:")[1]
    user_id = callback.from_user.id

    if preset_id == "custom":
        await state.set_state(GenerationStates.entering_custom_prompt)
        await callback.answer()
        await callback.message.answer(
            _("enter_custom_prompt"),
            parse_mode="Markdown"
        )
        return

    preset = await preset_manager.get_preset_by_id(preset_id)
    if not preset:
        await callback.answer("Preset not found.", show_alert=True)
        return

    await callback.answer(f"Selected: {preset.title}")

    # Check if state has uploaded reference photo
    state_data = await state.get_data()
    ref_photo_bytes = state_data.get("reference_photo_bytes")

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
        _=_
    )


@core_router.message(F.photo)
async def handle_photo_upload(
    message: Message,
    state: FSMContext,
    bot: Bot,
    _: Optional[Callable[..., str]] = None
):
    """Handles photo upload for photo-to-photo face avatar generation."""
    if _ is None:
        _ = lambda k, **kw: i18n.get(k, **kw)

    photo = message.photo[-1]  # Highest resolution
    file_info = await bot.get_file(photo.file_id)
    photo_bytes_io = await bot.download_file(file_info.file_path)
    photo_bytes = photo_bytes_io.read()

    await state.update_data(reference_photo_bytes=photo_bytes)
    await state.set_state(GenerationStates.selecting_preset)

    presets = await preset_manager.get_presets("image")
    kb = get_presets_keyboard(presets, _=_)
    await message.answer(
        _("photo_received"),
        reply_markup=kb,
        parse_mode="Markdown"
    )


@core_router.message(F.text & ~F.text.startswith("/"))
async def handle_custom_text_prompt(
    message: Message,
    state: FSMContext,
    bot: Bot,
    bot_id: str = "default_bot",
    _: Optional[Callable[..., str]] = None
):
    """Handles custom prompt text messages."""
    if _ is None:
        _ = lambda k, **kw: i18n.get(k, **kw)

    prompt = message.text.strip()
    user_id = message.from_user.id

    state_data = await state.get_data()
    ref_photo_bytes = state_data.get("reference_photo_bytes")

    await run_generation_job(
        bot=bot,
        chat_id=message.chat.id,
        user_id=user_id,
        prompt=prompt,
        reference_photo_bytes=ref_photo_bytes,
        media_type="image",
        bot_id=bot_id,
        _=_
    )
    await state.clear()
