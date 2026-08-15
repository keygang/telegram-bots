import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

logger = logging.getLogger(__name__)


class MetricsMiddleware(BaseMiddleware):
    """
    Aiogram 3 Context Middleware that injects bot_id and EventTracker
    into handler context data. Event collection is explicitly invoked
    within handlers using typed Event dataclasses.
    """

    def __init__(self, bot_id: str = "default_bot"):
        super().__init__()
        self.bot_id = bot_id

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        from platform_core.events import get_tracker

        data["bot_id"] = self.bot_id
        data["tracker"] = get_tracker(self.bot_id)
        return await handler(event, data)
