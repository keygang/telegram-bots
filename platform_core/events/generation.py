from typing import ClassVar

from platform_core.events.base import BaseEvent


class GenerationEvent(BaseEvent):
    """
    Event recorded during AI content generation (image, text, audio).
    """

    event_name: ClassVar[str] = "generation"

    model_name: str
    prompt: str
    preset_id: str | None = None
    media_url: str | None = None
    aspect_ratio: str | None = None
    tokens_spent: int | None = None
    error_message: str | None = None

    def get_event_name(self) -> str:
        return "generation_completed" if self.status == "success" else "generation_failed"
