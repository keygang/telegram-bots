import logging
import time
from typing import Any, Callable, Dict, Awaitable, Optional
from aiogram import BaseMiddleware
from aiogram.types import (
    TelegramObject,
    Update,
    Message,
    CallbackQuery,
    PreCheckoutQuery,
    InlineQuery,
    User,
)
from platform_core.db import db, BotEvent
from platform_core.metrics.prometheus import record_prometheus_event

logger = logging.getLogger(__name__)


class MetricsMiddleware(BaseMiddleware):
    """
    Aiogram 3 Middleware that automatically collects telemetric events
    (command invocations, button clicks, media uploads, payments, and processing latency).
    Supports being registered on dp.update.outer_middleware as well as router-level middlewares.
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
        duration_ms = max(0, int((time.time() - start_time) * 1000))

        try:
            # Unwrap Update if outer update middleware was used
            inner_event = event.event if isinstance(event, Update) else event
            user: Optional[User] = data.get("event_from_user") or getattr(inner_event, "from_user", None)
            user_id = user.id if user else 0

            event_type = None
            event_name = None
            metadata: Dict[str, Any] = {}

            if isinstance(inner_event, Message):
                if inner_event.text:
                    if inner_event.text.startswith("/"):
                        event_type = "command"
                        # Extract command name and strip bot mentions (e.g. /start@my_bot -> /start)
                        raw_cmd = inner_event.text.split()[0]
                        event_name = raw_cmd.split("@")[0].lower()
                    else:
                        event_type = "message"
                        event_name = "prompt_text"
                    metadata["text_length"] = len(inner_event.text)
                elif inner_event.photo:
                    event_type = "media_upload"
                    event_name = "photo"
                    metadata["photo_sizes"] = len(inner_event.photo)
                elif inner_event.document:
                    event_type = "media_upload"
                    event_name = "document"
                    metadata["mime_type"] = inner_event.document.mime_type
                elif inner_event.successful_payment:
                    event_type = "payment"
                    event_name = "stars_payment"
                    metadata["total_amount"] = inner_event.successful_payment.total_amount
                    metadata["currency"] = inner_event.successful_payment.currency
                    metadata["invoice_payload"] = inner_event.successful_payment.invoice_payload
                else:
                    event_type = "message"
                    event_name = "other_media"

                if inner_event.chat:
                    metadata["chat_type"] = inner_event.chat.type

            elif isinstance(inner_event, CallbackQuery):
                event_type = "click"
                event_name = inner_event.data or "callback"
                if inner_event.message:
                    metadata["message_id"] = inner_event.message.message_id

            elif isinstance(inner_event, PreCheckoutQuery):
                event_type = "payment"
                event_name = f"pre_checkout:{inner_event.invoice_payload}"
                metadata["total_amount"] = inner_event.total_amount
                metadata["currency"] = inner_event.currency

            elif isinstance(inner_event, InlineQuery):
                event_type = "inline_query"
                event_name = "inline_search"
                metadata["query_length"] = len(inner_event.query) if inner_event.query else 0

            if event_type and event_name:
                record_prometheus_event(self.bot_id, event_type, event_name, duration_ms)
                await db.record_event(
                    BotEvent(
                        bot_id=self.bot_id,
                        user_id=user_id,
                        event_type=event_type,
                        event_name=event_name,
                        duration_ms=duration_ms,
                        metadata=metadata,
                    )
                )
        except Exception as err:
            logger.debug(f"Metrics collection error: {err}")

        return result

