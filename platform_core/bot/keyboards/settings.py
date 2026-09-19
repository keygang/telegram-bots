from collections.abc import Callable

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from platform_core.bot.keyboards.common import _resolve_gettext
from platform_core.i18n import SUPPORTED_LANGUAGES


def get_settings_keyboard(_: Callable[..., str] | None = None) -> InlineKeyboardMarkup:
    """Renders settings keyboard with language change and model options."""
    gettext = _resolve_gettext(_)

    buttons = [
        [
            InlineKeyboardButton(
                text=gettext("btn_change_language"), callback_data="change_language"
            )
        ],
        [InlineKeyboardButton(text=gettext("btn_change_model"), callback_data="models_menu")],
        [InlineKeyboardButton(text=gettext("btn_help"), callback_data="help_menu")],
        [InlineKeyboardButton(text=gettext("back_to_main_menu"), callback_data="main_menu")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_language_keyboard(
    current_lang: str,
    _: Callable[..., str] | None = None,
) -> InlineKeyboardMarkup:
    """Renders language selection buttons."""
    gettext = _resolve_gettext(_)

    buttons: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(
                text=f"{'✅ ' if lang_code == current_lang else '🌐 '}{lang_name}",
                callback_data=f"set_lang:{lang_code}",
            )
        ]
        for lang_code, lang_name in SUPPORTED_LANGUAGES.items()
    ]
    buttons.append(
        [InlineKeyboardButton(text=gettext("back_to_main_menu"), callback_data="settings_menu")]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


__all__ = [
    "get_language_keyboard",
    "get_settings_keyboard",
]
