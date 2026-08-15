from typing import ClassVar

from platform_core.events.base import BaseEvent


class ButtonClickEvent(BaseEvent):
    """
    Event recorded when a user clicks an inline keyboard button or callback query.
    """

    event_name: ClassVar[str] = "click"

    button_id: str
    menu: str | None = None
    message_id: int | None = None

    def get_event_name(self) -> str:
        return self.button_id
