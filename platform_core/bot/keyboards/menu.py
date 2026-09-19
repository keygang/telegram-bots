from collections.abc import Callable

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from platform_core.bot.keyboards.common import _resolve_gettext


def get_main_action_keyboard(
    user_credits: int,
    _: Callable[..., str] | None = None,
) -> InlineKeyboardMarkup:
    """Renders persistent quick action keyboard."""
    gettext = _resolve_gettext(_)

    buttons = [
        [
            InlineKeyboardButton(text=gettext("btn_choose_preset"), callback_data="presets_menu"),
            InlineKeyboardButton(
                text=gettext("btn_upload_photo"), callback_data="upload_photo_menu"
            ),
        ],
        [
            InlineKeyboardButton(
                text=gettext("btn_balance", credits=user_credits), callback_data="open_buy"
            ),
            InlineKeyboardButton(text=gettext("btn_settings"), callback_data="settings_menu"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


__all__ = ["get_main_action_keyboard"]
