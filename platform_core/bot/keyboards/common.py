from collections.abc import Callable

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from platform_core.i18n import i18n


def _resolve_gettext(_: Callable[..., str] | None) -> Callable[..., str]:
    return _ if _ is not None else i18n.get


def get_cancel_keyboard(_: Callable[..., str] | None = None) -> InlineKeyboardMarkup:
    """Renders simple cancellation keyboard."""
    gettext = _resolve_gettext(_)

    buttons = [
        [InlineKeyboardButton(text=gettext("cancel_action_button"), callback_data="cancel_action")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)
