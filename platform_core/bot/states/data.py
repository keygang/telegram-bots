from typing import Any

from pydantic import BaseModel, Field


class GenerationStateData(BaseModel):
    """
    Pydantic schema representing typed FSM state payload during media generation.
    Supports easy validation and serialization.
    """

    selected_preset_id: str | None = None
    reference_file_id: str | None = None
    reference_photo_bytes: bytes | None = None
    custom_prompt: str | None = None
    extra_data: dict[str, Any] = Field(default_factory=dict)

    def __getitem__(self, item: str) -> Any:
        if hasattr(self, item):
            return getattr(self, item)
        return self.extra_data.get(item)

    def get(self, item: str, default: Any = None) -> Any:
        if hasattr(self, item):
            val = getattr(self, item)
            return val if val is not None else default
        return self.extra_data.get(item, default)


__all__ = ["GenerationStateData"]
