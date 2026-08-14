from typing import Optional
from pydantic import BaseModel


class PromptPreset(BaseModel):
    """
    Schema for a reusable AI Generation Prompt Preset.
    Allows easy customization of prompts, models, icons, and photo-to-photo behavior.
    """
    id: str
    title: str
    description: str
    icon: str = "🎨"
    prompt_template: str
    negative_prompt: Optional[str] = "blurry, low quality, distorted face, bad anatomy"
    category: str = "popular"
    media_type: str = "image"  # "image" or "video"
    default_model: str = "black-forest-labs/flux-schnell"
    supports_reference_photo: bool = True
    is_active: bool = True
    target_bot_id: Optional[str] = "all"  # "all" or specific bot_id e.g. "image_bot_1"

    def build_prompt(self, user_input: str = "") -> str:
        """Inject user text or description into the template."""
        if "{user_prompt}" in self.prompt_template:
            return self.prompt_template.format(user_prompt=user_input if user_input else "a person")
        elif user_input:
            return f"{self.prompt_template}, {user_input}"
        return self.prompt_template
