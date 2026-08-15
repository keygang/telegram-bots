from typing import ClassVar

from platform_core.events.base import BaseEvent


class CommandEvent(BaseEvent):
    """
    Event recorded when a user executes a Telegram bot command (e.g. /start, /help, /presets).
    """

    event_name: ClassVar[str] = "command"

    command: str
    args: str | None = None
    chat_type: str | None = None
    text_length: int | None = None

    def get_event_name(self) -> str:
        # Returns command as event name (e.g. "/start") or "command"
        return self.command if self.command.startswith("/") else f"/{self.command}"
