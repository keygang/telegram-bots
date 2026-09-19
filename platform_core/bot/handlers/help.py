from collections.abc import Callable

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

import platform_core.bot.handlers as bot_handlers
from platform_core.bot.handlers.common import _resolve_gettext
from platform_core.bot.keyboards import get_help_keyboard
from platform_core.events import (
    CommandEvent,
    MessageSentEvent,
)

help_router = Router(name="help_router")


@help_router.message(Command("help"))
@help_router.callback_query(F.data == "help_menu")
async def handle_help_command(
    event: Message | CallbackQuery,
    bot_id: str = "default_bot",
    _: Callable[..., str] | None = None,
) -> None:
    """Handles /help command and displays complete usage documentation and shortcuts."""
    gettext = _resolve_gettext(_)

    tracker = bot_handlers.get_tracker(bot_id)
    user_id = event.from_user.id
    await tracker.track(
        CommandEvent(
            distinct_id=user_id,
            bot_id=bot_id,
            command="/help",
        )
    )

    text = gettext("help_text")
    kb = get_help_keyboard(_=gettext)

    if isinstance(event, CallbackQuery):
        await event.answer()
        await event.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    else:
        await event.answer(text, reply_markup=kb, parse_mode="Markdown")

    await tracker.track(
        MessageSentEvent(
            distinct_id=user_id,
            bot_id=bot_id,
            message_type="help",
            text_length=len(text),
            has_reply_markup=True,
        )
    )
