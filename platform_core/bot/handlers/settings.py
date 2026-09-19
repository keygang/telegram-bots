from collections.abc import Callable
from typing import Any

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from platform_core.bot.handlers.common import _resolve_gettext
from platform_core.bot.keyboards import (
    get_language_keyboard,
    get_settings_keyboard,
)
from platform_core.db import UserProfile, db
from platform_core.i18n import SUPPORTED_LANGUAGES, i18n

settings_router = Router(name="settings_router")


@settings_router.message(Command("settings"))
@settings_router.callback_query(F.data == "settings_menu")
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


@settings_router.callback_query(F.data == "change_language")
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


@settings_router.callback_query(F.data.startswith("set_lang:"))
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
