from collections.abc import Callable

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message

import platform_core.bot.handlers as bot_handlers
from platform_core.bot.handlers.common import _resolve_gettext
from platform_core.bot.keyboards import (
    get_presets_keyboard,
    get_star_packages_keyboard,
)
from platform_core.db import UserBalance, db
from platform_core.events import (
    CommandEvent,
    MessageSentEvent,
)
from platform_core.payments.packages import STAR_PACKAGES
from platform_core.presets import preset_manager

menu_router = Router(name="menu_router")


@menu_router.message(CommandStart())
async def handle_start_command(
    message: Message,
    user_balance: UserBalance | None = None,
    bot_id: str = "default_bot",
    _: Callable[..., str] | None = None,
) -> None:
    gettext = _resolve_gettext(_)

    tracker = bot_handlers.get_tracker(bot_id)
    await tracker.track(
        CommandEvent(
            distinct_id=message.from_user.id,
            bot_id=bot_id,
            command="/start",
        )
    )

    credits = user_balance.credits_remaining if user_balance else 3
    presets = await preset_manager.get_presets("image", bot_id=bot_id)
    welcome_text = gettext("welcome_text", credits=credits)
    kb = get_presets_keyboard(presets, _=gettext)
    await message.answer(welcome_text, reply_markup=kb, parse_mode="Markdown")

    await tracker.track(
        MessageSentEvent(
            distinct_id=message.from_user.id,
            bot_id=bot_id,
            message_type="menu",
            text_length=len(welcome_text),
            has_reply_markup=True,
        )
    )


@menu_router.message(Command("generate"))
@menu_router.callback_query(F.data == "generate_menu")
@menu_router.callback_query(F.data == "presets_menu")
@menu_router.callback_query(F.data == "main_menu")
async def handle_presets_menu(
    event: Message | CallbackQuery,
    bot_id: str = "default_bot",
    _: Callable[..., str] | None = None,
) -> None:
    gettext = _resolve_gettext(_)

    presets = await preset_manager.get_presets("image", bot_id=bot_id)
    kb = get_presets_keyboard(presets, _=gettext)
    text = gettext("presets_menu_title")
    if isinstance(event, CallbackQuery):
        await event.answer()
        await event.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    else:
        await event.answer(text, reply_markup=kb, parse_mode="Markdown")


@menu_router.message(Command("reload_presets"))
async def handle_reload_presets_command(
    message: Message,
    _: Callable[..., str] | None = None,
) -> None:
    """Admin command to force reload remote presets from Supabase or Remote JSON URL."""
    gettext = _resolve_gettext(_)

    reloaded = await preset_manager.fetch_presets(force_reload=True)
    await message.answer(
        gettext("presets_refreshed", count=len(reloaded)),
        parse_mode="Markdown",
    )


@menu_router.message(Command("buy"))
@menu_router.callback_query(F.data == "open_buy")
async def handle_buy_menu(
    event: Message | CallbackQuery,
    user_balance: UserBalance | None = None,
    _: Callable[..., str] | None = None,
) -> None:
    gettext = _resolve_gettext(_)

    user_id = event.from_user.id
    balance = user_balance or await db.get_user_balance(user_id)
    text = gettext(
        "buy_menu_title", credits=balance.credits_remaining, stars=balance.total_stars_spent
    )
    kb = get_star_packages_keyboard(STAR_PACKAGES, _=gettext)
    if isinstance(event, CallbackQuery):
        await event.answer()
        await event.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    else:
        await event.answer(text, reply_markup=kb, parse_mode="Markdown")
