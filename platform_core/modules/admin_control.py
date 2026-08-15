from typing import Any, List
from aiogram import Router
from aiogram.types import BotCommand
from platform_core.modules.base import BaseBotModule
from bots.admin_bot.bot import admin_router


class AdminControlModule(BaseBotModule):
    """
    Pluggable Admin Control Module for Managing Platform Bot Instances,
    Presets, and Analytics Telemetry.
    """

    name: str = "admin_control"

    def __init__(self, **_kwargs: Any):
        self._router = admin_router

    @property
    def router(self) -> Router:
        return self._router

    def get_bot_commands(self) -> List[BotCommand]:
        return [
            BotCommand(command="admin", description="👑 Open Admin Dashboard"),
            BotCommand(command="menu", description="👑 Open Admin Dashboard"),
            BotCommand(command="stats", description="📊 View Platform Telemetry & Metrics"),
        ]
