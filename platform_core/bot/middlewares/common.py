from typing import Any

from aiogram.types import TelegramObject, Update, User


def _get_user_from_event(event: TelegramObject, data: dict[str, Any]) -> User | None:
    """Helper to safely extract the Telegram User across Update and specific event types."""
    user = data.get("event_from_user")
    if user:
        return user
    inner = event.event if isinstance(event, Update) else event
    return getattr(inner, "from_user", None)
