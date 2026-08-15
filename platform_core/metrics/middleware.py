import time
from typing import Any, Callable, Dict, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from platform_core.db import db, BotEvent
from platform_core.metrics.prometheus import record_prometheus_event


class MetricsMiddleware(BaseMiddleware):
    """
    Aiogram 3 Middleware that automatically collects telemetric events
    (command invocations, button clicks, processing latency).
    """

    def __init__(self, bot_id: str = "default_bot"):
        super().__init__()
        self.bot_id = bot_id

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        # Inject bot_id into handler context data
        data["bot_id"] = self.bot_id

        start_time = time.time()
        result = await handler(event, data)
        duration_ms = int((time.time() - start_time) * 1000)

        if isinstance(event, Message) and event.from_user:
            event_name = event.text.split()[0] if event.text else "media_upload"
            event_type = "command" if event.text and event.text.startswith("/") else "message"
            record_prometheus_event(self.bot_id, event_type, event_name, duration_ms)
            await db.record_event(
                BotEvent(
                    bot_id=self.bot_id,
                    user_id=event.from_user.id,
                    event_type=event_type,
                    event_name=event_name,
                    duration_ms=duration_ms,
                )
            )
        elif isinstance(event, CallbackQuery) and event.from_user:
            event_name = event.data or "callback"
            record_prometheus_event(self.bot_id, "click", event_name, duration_ms)
            await db.record_event(
                BotEvent(
                    bot_id=self.bot_id,
                    user_id=event.from_user.id,
                    event_type="click",
                    event_name=event_name,
                    duration_ms=duration_ms,
                )
            )

        return result
