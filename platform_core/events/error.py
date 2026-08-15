from typing import ClassVar

from platform_core.events.base import BaseEvent


class ErrorEvent(BaseEvent):
    """
    Event recorded when an application exception or external provider error occurs.
    """

    event_name: ClassVar[str] = "error"
    status: str = "error"

    error_type: str
    error_message: str
    stack_trace: str | None = None
    component: str | None = None

    def get_event_name(self) -> str:
        return f"error:{self.error_type}"
