from typing import Any

from aiogram import Router
from aiogram.types import BotCommand

from platform_core.bot.middlewares import CreditCheckMiddleware
from platform_core.modules.base import BaseBotModule, ModuleInfo
from platform_core.payments.handlers import payments_router
from platform_core.payments.packages import STAR_PACKAGES, StarPackage


class MonetizationModule(BaseBotModule):
    """
    Pluggable Monetization Module.
    Provides Telegram Stars payment integration, credit check middleware,
    package management, and payment handlers.
    """

    name: str = "monetization"

    def __init__(
        self,
        star_packages: list[StarPackage] | None = None,
        enable_credit_check: bool = True,
        **_kwargs: Any,
    ):
        self.star_packages = star_packages or STAR_PACKAGES
        self.enable_credit_check = enable_credit_check
        self._router = payments_router

    @property
    def router(self) -> Router:
        return self._router

    @property
    def middlewares(self) -> list[Any]:
        if self.enable_credit_check:
            return [CreditCheckMiddleware()]
        return []

    def get_bot_commands(self) -> list[BotCommand]:
        return [
            BotCommand(command="buy", description="⭐️ Buy Credits with Telegram Stars"),
        ]

    def get_module_info(self) -> ModuleInfo:
        return ModuleInfo(
            name=self.name,
            details={
                "packages_count": len(self.star_packages),
                "enable_credit_check": self.enable_credit_check,
            },
        )
