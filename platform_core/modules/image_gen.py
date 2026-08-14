from typing import Any, List, Optional
from aiogram import Router
from aiogram.types import BotCommand
from platform_core.bot.handlers import core_router
from platform_core.modules.base import BaseBotModule
from platform_core.presets import DEFAULT_IMAGE_PRESETS, PromptPreset


class ImageGenModule(BaseBotModule):
    """
    Pluggable Image Generation Module.
    Handles text-to-image, photo-to-photo, style presets, and model choices.
    """

    name: str = "image_gen"

    def __init__(
        self,
        default_model: str = "black-forest-labs/flux-schnell",
        custom_presets: Optional[List[PromptPreset]] = None,
        **_kwargs: Any,
    ):
        self.default_model = default_model
        self.custom_presets = custom_presets or DEFAULT_IMAGE_PRESETS
        self._router = core_router

    @property
    def router(self) -> Router:
        return self._router

    def get_presets(self) -> List[PromptPreset]:
        return self.custom_presets

    def get_bot_commands(self) -> List[BotCommand]:
        return [
            BotCommand(command="start", description="🚀 Start the AI Image Bot"),
            BotCommand(command="presets", description="🎨 Browse Image Style Presets"),
            BotCommand(command="models", description="⚙️ Select AI Image Model"),
            BotCommand(command="help", description="❓ Usage & Information"),
        ]
