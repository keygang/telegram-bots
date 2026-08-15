from typing import Any

from platform_core.events.base import BaseEvent


class CustomEvent(BaseEvent):
    """
    Arbitrary custom event with dynamic name and key-value attributes.
    """

    name: str
    data: dict[str, Any] = {}

    def get_event_name(self) -> str:
        return self.name

    def to_properties(self) -> dict[str, Any]:
        return dict(self.data)
