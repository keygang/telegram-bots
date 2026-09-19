from collections.abc import Callable

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from platform_core.bot.keyboards.common import _resolve_gettext
from platform_core.payments.packages import StarPackage


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


__all__ = ["get_star_packages_keyboard"]
