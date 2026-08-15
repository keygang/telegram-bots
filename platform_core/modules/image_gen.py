from typing import Any

from aiogram import Router
from aiogram.types import BotCommand

from platform_core.bot.handlers import core_router
from platform_core.modules.base import BaseBotModule, ModuleInfo
from platform_core.presets import PromptPreset

DEFAULT_AVAILABLE_MODELS: list[str] = [
    "google/gemini-2.5-flash-image",
    "black-forest-labs/flux-1.1-pro",
    "openai/dall-e-3",
    "stabilityai/stable-diffusion-3.5-large",
    "recraft-ai/recraft-v3",
]


class ImageGenModule(BaseBotModule):
    """
    Pluggable Image Generation Module.
    Handles text-to-image, photo-to-photo, style presets, and model choices.
    """

    name: str = "image_gen"

    def __init__(
        self,
        default_model: str = "google/gemini-2.5-flash-image",
        available_models: list[str] | None = None,
        custom_presets: list[PromptPreset] | None = None,
        **_kwargs: Any,
    ):
        self.default_model = default_model
        self.available_models = available_models or list(DEFAULT_AVAILABLE_MODELS)
        self.custom_presets = list(custom_presets) if custom_presets is not None else []
        self._router = core_router

    @property
    def router(self) -> Router:
        return self._router

    def get_presets(self) -> list[PromptPreset]:
        return self.custom_presets

    def get_bot_commands(self) -> list[BotCommand]:
        return [
            BotCommand(command="generate", description="🎨 Generate & Create Artwork"),
            BotCommand(command="models", description="⚙️ Select AI Image Model"),
            BotCommand(command="help", description="❓ Usage & Information"),
        ]

    def get_module_info(self) -> ModuleInfo:
        return ModuleInfo(
            name=self.name,
            details={
                "default_model": self.default_model,
                "available_models": self.available_models,
                "presets_count": len(self.custom_presets),
            },
        )
