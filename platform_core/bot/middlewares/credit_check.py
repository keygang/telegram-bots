import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from platform_core.bot.middlewares.common import _get_user_from_event
from platform_core.db import db

logger = logging.getLogger(__name__)


class CreditCheckMiddleware(BaseMiddleware):
    """Middleware that ensures user has available generation credits."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = _get_user_from_event(event, data)

        if user:
            balance = await db.get_user_balance(user.id)
            data["user_balance"] = balance

        return await handler(event, data)
