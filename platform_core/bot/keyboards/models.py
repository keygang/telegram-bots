from collections.abc import Callable

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from platform_core.bot.keyboards.common import _resolve_gettext


def get_models_keyboard(
    models: list[str],
    current_model: str,
    _: Callable[..., str] | None = None,
) -> InlineKeyboardMarkup:
    """Renders inline keyboard buttons for selecting AI models."""
    gettext = _resolve_gettext(_)

    buttons: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(
                text=f"{'✅ ' if model == current_model else '🔹 '}{model.split('/')[-1]}",
                callback_data=f"set_model:{model}",
            )
        ]
        for model in models
    ]
    buttons.append(
        [InlineKeyboardButton(text=gettext("back_to_main_menu"), callback_data="main_menu")]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


__all__ = ["get_models_keyboard"]
