from abc import ABC
from typing import Any, List
from aiogram import Bot, Dispatcher, Router
from aiogram.types import BotCommand
from platform_core.presets.base import PromptPreset


class BaseBotModule(ABC):
    """
    Abstract Base Class for all pluggable Bot Modules.
    Provides a standardized interface to bundle aiogram Routers, Middlewares,
    Custom Presets, Bot Menu Commands, and Lifecycle Hooks.
    """

    name: str = "base_module"

    @property
    def router(self) -> Router:
        """Returns the aiogram Router associated with this module."""
        return Router(name=self.name)

    @property
    def middlewares(self) -> List[Any]:
        """Returns a list of outer update middlewares required by this module."""
        return []

    def get_presets(self) -> List[PromptPreset]:
        """Returns custom PromptPresets contributed by this module."""
        return []

    def get_bot_commands(self) -> List[BotCommand]:
        """Returns Telegram BotCommand objects to register in the bot menu."""
        return []

    async def on_startup(self, bot: Bot, dp: Dispatcher) -> None:
        """Lifecycle hook executed prior to polling startup."""
        pass

    async def on_shutdown(self, bot: Bot, dp: Dispatcher) -> None:
        """Lifecycle hook executed during bot shutdown."""
        pass
