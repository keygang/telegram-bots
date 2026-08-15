from collections.abc import Callable

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from platform_core.i18n import SUPPORTED_LANGUAGES, i18n
from platform_core.payments.packages import StarPackage
from platform_core.presets.base import PromptPreset


def _resolve_gettext(_: Callable[..., str] | None) -> Callable[..., str]:
    return _ if _ is not None else i18n.get


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


def get_cancel_keyboard(_: Callable[..., str] | None = None) -> InlineKeyboardMarkup:
    """Renders simple cancellation keyboard."""
    gettext = _resolve_gettext(_)

    buttons = [
        [InlineKeyboardButton(text=gettext("cancel_action_button"), callback_data="cancel_action")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


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


def get_star_packages_keyboard(
    packages: list[StarPackage],
    _: Callable[..., str] | None = None,
) -> InlineKeyboardMarkup:
    """Renders inline keyboard for Telegram Stars credit top-ups."""
    gettext = _resolve_gettext(_)

    buttons: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(
                text=f"{pkg.icon} {pkg.title} ({pkg.credits_count} Credits) — ⭐️ {pkg.stars_amount} Stars",
                callback_data=f"buy_stars:{pkg.id}",
            )
        ]
        for pkg in packages
    ]
    buttons.append(
        [InlineKeyboardButton(text=gettext("back_to_presets"), callback_data="main_menu")]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


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
