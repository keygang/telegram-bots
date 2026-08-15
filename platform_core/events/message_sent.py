from typing import ClassVar

from platform_core.events.base import BaseEvent


class MessageSentEvent(BaseEvent):
    """
    Event recorded when the bot dispatches an outgoing message to a user.
    Tracks message types (text, photo, document, invoice, menu, callback_answer),
    character volume, presence of inline keyboards, and delivery latency.
    """

    event_name: ClassVar[str] = "message_sent"

    message_type: str = "text"  # "text", "photo", "document", "invoice", "menu", "callback_answer"
    text_length: int | None = None
    has_reply_markup: bool = False
    chat_type: str | None = "private"
    is_edit: bool = False

    def get_event_name(self) -> str:
        return f"message_sent:{self.message_type}"
