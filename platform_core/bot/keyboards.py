from typing import List, Optional, Callable, Dict
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from platform_core.presets.base import PromptPreset
from platform_core.payments.packages import StarPackage
from platform_core.i18n import i18n, SUPPORTED_LANGUAGES


def get_presets_keyboard(presets: List[PromptPreset], _: Optional[Callable[[str], str]] = None) -> InlineKeyboardMarkup:
    """Renders inline keyboard buttons for prompt presets with i18n support."""
    if _ is None:
        _ = lambda k, **kw: i18n.get(k, **kw)

    buttons = []
    for preset in presets:
        buttons.append([
            InlineKeyboardButton(
                text=f"{preset.icon} {preset.title}",
                callback_data=f"preset:{preset.id}"
            )
        ])
    buttons.append([InlineKeyboardButton(text=_("preset_custom_button"), callback_data="preset:custom")])
    buttons.append([InlineKeyboardButton(text=_("buy_credits_button"), callback_data="open_buy")])
    buttons.append([InlineKeyboardButton(text=_("btn_settings"), callback_data="settings_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_models_keyboard(models: List[str], current_model: str, _: Optional[Callable[[str], str]] = None) -> InlineKeyboardMarkup:
    """Renders inline keyboard buttons for selecting AI models."""
    if _ is None:
        _ = lambda k, **kw: i18n.get(k, **kw)

    buttons = []
    for model in models:
        prefix = "✅ " if model == current_model else "🔹 "
        short_name = model.split("/")[-1]
        buttons.append([
            InlineKeyboardButton(
                text=f"{prefix}{short_name}",
                callback_data=f"set_model:{model}"
            )
        ])
    buttons.append([InlineKeyboardButton(text=_("back_to_main_menu"), callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_star_packages_keyboard(packages: List[StarPackage], _: Optional[Callable[[str], str]] = None) -> InlineKeyboardMarkup:
    """Renders inline keyboard for Telegram Stars credit top-ups."""
    if _ is None:
        _ = lambda k, **kw: i18n.get(k, **kw)

    buttons = []
    for pkg in packages:
        buttons.append([
            InlineKeyboardButton(
                text=f"{pkg.icon} {pkg.title} ({pkg.credits_count} Credits) — ⭐️ {pkg.stars_amount} Stars",
                callback_data=f"buy_stars:{pkg.id}"
            )
        ])
    buttons.append([InlineKeyboardButton(text=_("back_to_presets"), callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_main_action_keyboard(user_credits: int, _: Optional[Callable[[str], str]] = None) -> InlineKeyboardMarkup:
    """Renders persistent quick action keyboard."""
    if _ is None:
        _ = lambda k, **kw: i18n.get(k, **kw)

    buttons = [
        [
            InlineKeyboardButton(text=_("btn_choose_preset"), callback_data="presets_menu"),
            InlineKeyboardButton(text=_("btn_upload_photo"), callback_data="upload_photo_menu"),
        ],
        [
            InlineKeyboardButton(text=_("btn_balance", credits=user_credits), callback_data="open_buy"),
            InlineKeyboardButton(text=_("btn_stats"), callback_data="show_stats"),
        ],
        [
            InlineKeyboardButton(text=_("btn_settings"), callback_data="settings_menu"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_settings_keyboard(_: Optional[Callable[[str], str]] = None) -> InlineKeyboardMarkup:
    """Renders settings keyboard with language change option."""
    if _ is None:
        _ = lambda k, **kw: i18n.get(k, **kw)

    buttons = [
        [InlineKeyboardButton(text=_("btn_change_language"), callback_data="change_language")],
        [InlineKeyboardButton(text=_("back_to_main_menu"), callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_language_keyboard(current_lang: str, _: Optional[Callable[[str], str]] = None) -> InlineKeyboardMarkup:
    """Renders language selection buttons."""
    if _ is None:
        _ = lambda k, **kw: i18n.get(k, **kw)

    buttons = []
    for lang_code, lang_name in SUPPORTED_LANGUAGES.items():
        prefix = "✅ " if lang_code == current_lang else "🌐 "
        buttons.append([
            InlineKeyboardButton(
                text=f"{prefix}{lang_name}",
                callback_data=f"set_lang:{lang_code}"
            )
        ])
    buttons.append([InlineKeyboardButton(text=_("back_to_main_menu"), callback_data="settings_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)
