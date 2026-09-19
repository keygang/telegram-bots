import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from platform_core.bot.middlewares.common import _get_user_from_event
from platform_core.db import db

logger = logging.getLogger(__name__)


class UserSyncMiddleware(BaseMiddleware):
    """Middleware that synchronizes Telegram user profile into Supabase DB."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = _get_user_from_event(event, data)

        if user:
            user_profile = await db.sync_user(
                telegram_id=user.id,
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name,
            )
            data["user_profile"] = user_profile

        return await handler(event, data)
