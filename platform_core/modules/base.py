from abc import ABC, abstractmethod
from typing import Any

from aiogram import Bot, Dispatcher, Router
from aiogram.types import BotCommand
from pydantic import BaseModel, Field

from platform_core.presets.base import PromptPreset


class ModuleInfo(BaseModel):
    """
    Pydantic schema representing standardized module metadata.
    Supports strict JSON serialization and dict compatibility.
    """

    name: str
    description: str | None = None
    enabled: bool = True
    details: dict[str, Any] = Field(default_factory=dict)

    def __getitem__(self, item: str) -> Any:
        if hasattr(self, item):
            return getattr(self, item)
        return self.details.get(item)

    def get(self, item: str, default: Any = None) -> Any:
        if hasattr(self, item):
            val = getattr(self, item)
            return val if val is not None else default
        return self.details.get(item, default)


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
    def middlewares(self) -> list[Any]:
        """Returns a list of outer update middlewares required by this module."""
        return []

    def get_presets(self) -> list[PromptPreset]:
        """Returns custom PromptPresets contributed by this module."""
        return []

    def get_bot_commands(self) -> list[BotCommand]:
        """Returns Telegram BotCommand objects to register in the bot menu."""
        return []

    async def on_startup(self, bot: Bot, dp: Dispatcher) -> None:
        """Lifecycle hook executed prior to polling/webhook startup."""
        # Default no-op for modules that do not require custom startup logic
        return

    async def on_shutdown(self, bot: Bot, dp: Dispatcher) -> None:
        """Lifecycle hook executed during bot shutdown."""
        # Default no-op for modules that do not require custom shutdown logic
        return

    @abstractmethod
    def get_module_info(self) -> ModuleInfo:
        """Returns summary metadata describing this module."""
        return ModuleInfo(name=self.name)
