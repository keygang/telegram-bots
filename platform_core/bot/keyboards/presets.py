from collections.abc import Callable

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from platform_core.bot.keyboards.common import _resolve_gettext, get_cancel_keyboard
from platform_core.presets.base import PromptPreset


def get_presets_keyboard(
    presets: list[PromptPreset],
    has_photo: bool = False,
    _: Callable[..., str] | None = None,
) -> InlineKeyboardMarkup:
    """Renders inline keyboard buttons for prompt presets with i18n support."""
    gettext = _resolve_gettext(_)

    buttons: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(
                text=f"{preset.icon} {preset.title}",
                callback_data=f"preset:{preset.id}",
            )
        ]
        for preset in presets
    ]

    custom_label = (
        gettext("custom_prompt_with_photo") if has_photo else gettext("preset_custom_button")
    )
    buttons.append([InlineKeyboardButton(text=custom_label, callback_data="preset:custom")])

    if has_photo:
        buttons.append(
            [
                InlineKeyboardButton(
                    text=gettext("cancel_action_button"), callback_data="cancel_action"
                )
            ]
        )
    else:
        buttons.append(
            [InlineKeyboardButton(text=gettext("buy_credits_button"), callback_data="open_buy")]
        )
        buttons.append(
            [InlineKeyboardButton(text=gettext("btn_settings"), callback_data="settings_menu")]
        )

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_waiting_for_photo_keyboard(
    preset_id: str,
    _: Callable[..., str] | None = None,
) -> InlineKeyboardMarkup:
    """Renders keyboard when waiting for user to upload their photo for a selected preset."""
    gettext = _resolve_gettext(_)

    buttons = [
        [InlineKeyboardButton(text=gettext("back_to_presets"), callback_data="presets_menu")],
        [InlineKeyboardButton(text=gettext("cancel_action_button"), callback_data="cancel_action")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


__all__ = [
    "get_cancel_keyboard",
    "get_presets_keyboard",
    "get_waiting_for_photo_keyboard",
]
