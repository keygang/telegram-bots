from collections.abc import Callable

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from platform_core.bot.keyboards.common import _resolve_gettext


def get_help_keyboard(_: Callable[..., str] | None = None) -> InlineKeyboardMarkup:
    """Renders help menu keyboard with quick navigation."""
    gettext = _resolve_gettext(_)

    buttons = [
        [
            InlineKeyboardButton(text=gettext("btn_choose_preset"), callback_data="presets_menu"),
            InlineKeyboardButton(text=gettext("btn_models"), callback_data="models_menu"),
        ],
        [
            InlineKeyboardButton(text=gettext("buy_credits_button"), callback_data="open_buy"),
            InlineKeyboardButton(text=gettext("btn_settings"), callback_data="settings_menu"),
        ],
        [InlineKeyboardButton(text=gettext("back_to_main_menu"), callback_data="main_menu")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


__all__ = ["get_help_keyboard"]
