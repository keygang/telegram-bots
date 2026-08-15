from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import (
    CallbackQuery,
    Message,
    TelegramObject,
    User,
)

from platform_core.config import settings


class AdminAuthMiddleware(BaseMiddleware):
    """Middleware enforcing admin Telegram user ID authorization."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user: User | None = data.get("event_from_user")
        admin_ids = settings.admin_user_ids

        # If admin_ids are configured, check user authorization
        if admin_ids and user and user.id not in admin_ids:
            message_text = (
                f"⛔ <b>Access Denied</b>\n\n"
                f"Your Telegram ID (<code>{user.id}</code>) is not authorized to access the Admin Bot."
            )
            if isinstance(event, Message):
                await event.answer(message_text, parse_mode="HTML")
            elif isinstance(event, CallbackQuery):
                await event.answer("⛔ Access Denied. Admin privileges required.", show_alert=True)
            return

        return await handler(event, data)
