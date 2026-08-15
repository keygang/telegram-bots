import logging
import os
from pathlib import Path
from typing import Any

import yaml
from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand
from pydantic import BaseModel, Field

from platform_core.bot.middlewares import I18nMiddleware, UserSyncMiddleware
from platform_core.config import settings
from platform_core.fsm_storage import BaseStorage, get_fsm_storage
from platform_core.metrics import MetricsMiddleware
from platform_core.modules.admin_control import AdminControlModule
from platform_core.modules.base import BaseBotModule
from platform_core.modules.image_gen import ImageGenModule
from platform_core.modules.monetization import MonetizationModule
from platform_core.modules.presets_module import PresetsModule
from platform_core.presets import PromptPreset, preset_manager

logger = logging.getLogger(__name__)


class WebhookConfig(BaseModel):
    """Configuration for bot Telegram webhook delivery."""

    enabled: bool = False
    path: str | None = None
    url: str | None = None


class ModuleConfig(BaseModel):
    """Configuration for an attached bot module."""

    name: str
    enabled: bool = True
    options: dict[str, Any] = Field(default_factory=dict)


class BotInstanceConfig(BaseModel):
    """
    Strictly typed Pydantic Schema for Bot Instance Configuration.
    Supports complete YAML/JSON serialization, validation, and defaults.
    """

    bot_id: str | None = None
    strategy: str | None = None
    token: str | None = None
    token_env: str | None = None
    webhook: WebhookConfig | None = None
    constants: dict[str, Any] = Field(default_factory=dict)
    promoted_presets: list[str] = Field(default_factory=list)
    promoted_preset_ids: list[str] = Field(default_factory=list)
    modules: list[ModuleConfig] = Field(default_factory=list)
    presets_file: str | None = None
    presets: list[PromptPreset] = Field(default_factory=list)

    @classmethod
    def from_yaml_file(cls, file_path: str | Path) -> "BotInstanceConfig":
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Bot config file not found: {path}")

        with open(path, encoding="utf-8") as f:
            raw: dict[str, Any] = yaml.safe_load(f) or {}

        if "bot_id" not in raw or not raw["bot_id"]:
            raw["bot_id"] = path.stem

        return cls.model_validate(raw)


class ModularBot:
    """
    Assembled Modular Bot instance ready to run.
    Contains the underlying aiogram Bot, Dispatcher, and registered modules.
    """

    def __init__(
        self,
        bot: Bot,
        dp: Dispatcher,
        bot_id: str,
        modules: list[BaseBotModule],
        commands: list[BotCommand],
        constants: dict[str, Any] | None = None,
        strategy: str | None = None,
    ):
        self.bot = bot
        self.dp = dp
        self.bot_id = bot_id
        self.modules = modules
        self.commands = commands
        self.constants = constants or {}
        self.strategy = (strategy or settings.BOT_STRATEGY).lower()

    async def run(self, force_mock: bool = False) -> None:
        """
        Executes startup hooks, registers bot menu commands, and starts Telegram polling loop or webhook setup based on strategy.
        """
        # Execute startup hooks for all modules
        for mod in self.modules:
            await mod.on_startup(self.bot, self.dp)

        # Register menu commands with Telegram if commands are provided
        if self.commands:
            try:
                await self.bot.set_my_commands(self.commands)
                logger.info(f"Registered {len(self.commands)} menu commands for bot {self.bot_id}.")
            except Exception as e:
                logger.warning(f"Could not set bot commands for {self.bot_id}: {e}")

        try:
            if self.strategy == "webhook":
                logger.info(
                    f"🌐 Modular Telegram Bot [{self.bot_id}] configured for WEBHOOK strategy."
                )
                if settings.WEBHOOK_BASE_URL:
                    webhook_url = f"{settings.WEBHOOK_BASE_URL.rstrip('/')}/webhook/{self.bot_id}"
                    secret_token = settings.WEBHOOK_SECRET_TOKEN
                    try:
                        await self.bot.set_webhook(
                            url=webhook_url,
                            secret_token=secret_token,
                            drop_pending_updates=True,
                        )
                        logger.info(f"🌐 Webhook set for [{self.bot_id}] -> {webhook_url}")
                    except Exception as e:
                        logger.error(f"Failed to set webhook for [{self.bot_id}]: {e}")
                else:
                    logger.warning(
                        f"Webhook strategy enabled for [{self.bot_id}], but WEBHOOK_BASE_URL is not set."
                    )
            else:
                logger.info(f"🤖 Modular Telegram Bot [{self.bot_id}] starting POLLING loop...")
                try:
                    await self.bot.delete_webhook(drop_pending_updates=True)
                    logger.info(f"Cleared webhooks for [{self.bot_id}] prior to long polling.")
                except Exception as e:
                    logger.debug(f"Could not clear webhook for [{self.bot_id}]: {e}")

                await self.dp.start_polling(self.bot, bot_id=self.bot_id, force_mock=force_mock)
        finally:
            for mod in self.modules:
                await mod.on_shutdown(self.bot, self.dp)
            await self.bot.session.close()


class ModularBotBuilder:
    """
    Fluent builder for creating modular Telegram bot instances.
    """

    def __init__(self, bot_id: str, token: str | None = None, strategy: str | None = None):
        self.bot_id = bot_id
        self.token = token
        self.strategy = strategy
        self.constants: dict[str, Any] = {}
        self._modules: list[BaseBotModule] = []
        self._custom_presets: list[PromptPreset] = []
        self._promoted_preset_ids: list[str] = []

    def add_module(self, module: BaseBotModule) -> "ModularBotBuilder":
        """Adds a feature module to the bot."""
        self._modules.append(module)
        return self

    def set_promoted_preset_ids(self, preset_ids: list[str]) -> "ModularBotBuilder":
        """Sets the preset IDs that should be prioritized at the beginning for this bot."""
        self._promoted_preset_ids = list(preset_ids)
        return self

    def load_presets_from_yaml(
        self, file_path: str | Path, promote: bool = True
    ) -> "ModularBotBuilder":
        """Loads and attaches custom presets from a YAML file."""
        mod = PresetsModule.from_yaml_file(file_path)
        self._modules.append(mod)
        if promote:
            for p in mod.get_presets():
                if p.id not in self._promoted_preset_ids:
                    self._promoted_preset_ids.append(p.id)
        return self

    def load_presets_from_json(
        self, file_path: str | Path, promote: bool = True
    ) -> "ModularBotBuilder":
        """Loads and attaches custom presets from a JSON file."""
        mod = PresetsModule.from_json_file(file_path)
        self._modules.append(mod)
        if promote:
            for p in mod.get_presets():
                if p.id not in self._promoted_preset_ids:
                    self._promoted_preset_ids.append(p.id)
        return self

    def add_preset(self, preset: PromptPreset, promote: bool = True) -> "ModularBotBuilder":
        """Attaches an individual custom preset."""
        self._custom_presets.append(preset)
        if promote and preset.id not in self._promoted_preset_ids:
            self._promoted_preset_ids.append(preset.id)
        return self

    @classmethod
    def from_config(cls, config_path: str | Path) -> "ModularBotBuilder":
        """
        Creates a ModularBotBuilder pre-configured from a YAML configuration file.
        Supports tokens, environment variable names, custom constants, modules, and presets
        validated strictly via BotInstanceConfig Pydantic model.
        """
        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(f"Bot config file not found: {path}")

        cfg = BotInstanceConfig.from_yaml_file(path)

        bot_id = cfg.bot_id or path.stem
        token = cfg.token or (os.getenv(cfg.token_env) if cfg.token_env else None)

        strat = cfg.strategy
        if not strat and cfg.webhook is not None:
            strat = "webhook" if cfg.webhook.enabled else "polling"

        builder = cls(bot_id=bot_id, token=token, strategy=strat)

        builder.constants = cfg.constants

        promoted_ids = cfg.promoted_presets or cfg.promoted_preset_ids
        if promoted_ids:
            builder.set_promoted_preset_ids([str(pid) for pid in promoted_ids])

        # Parse modules
        for m_item in cfg.modules:
            if not m_item.enabled:
                continue

            m_name = m_item.name
            opts = m_item.options

            if m_name == "monetization":
                builder.add_module(MonetizationModule(**opts))
            elif m_name == "image_gen":
                builder.add_module(ImageGenModule(**opts))
            elif m_name == "admin_control":
                builder.add_module(AdminControlModule(**opts))
            elif m_name == "presets":
                preset_file = opts.get("file")
                mod_promoted = opts.get("promoted_presets") or opts.get("promoted_preset_ids")
                if isinstance(mod_promoted, list):
                    for pid in mod_promoted:
                        if str(pid) not in builder._promoted_preset_ids:
                            builder._promoted_preset_ids.append(str(pid))
                if preset_file:
                    preset_path = Path(preset_file)
                    if not preset_path.is_absolute():
                        preset_path = path.parent / preset_path
                    if preset_path.exists():
                        builder.load_presets_from_yaml(preset_path, promote=True)

        # Top-level presets_file or presets
        if cfg.presets_file:
            p_path = Path(cfg.presets_file)
            if not p_path.is_absolute():
                p_path = path.parent / p_path
            if p_path.exists():
                builder.load_presets_from_yaml(p_path, promote=True)

        for preset in cfg.presets:
            builder.add_preset(preset, promote=True)

        return builder

    def build(self, storage: BaseStorage | None = None) -> ModularBot:
        """Assembles the ModularBot instance."""
        token = self.token
        if not token or ":" not in token:
            token = settings.IMAGE_BOT_TOKEN

        if storage is None:
            storage = get_fsm_storage(key_prefix=f"fsm:{self.bot_id}")

        bot = Bot(token=token)
        dp = Dispatcher(storage=storage)

        # Core outer middlewares
        dp.update.outer_middleware(UserSyncMiddleware())
        dp.update.outer_middleware(I18nMiddleware())
        dp.update.outer_middleware(MetricsMiddleware(bot_id=self.bot_id))

        aggregated_commands: list[BotCommand] = []
        registered_router_names = set()

        for module in self._modules:
            # Register module middlewares
            for mw in module.middlewares:
                dp.update.outer_middleware(mw)

            # Register module router if not registered
            r = module.router
            if r.name not in registered_router_names:
                if r.parent_router is not None:
                    r._parent_router = None
                dp.include_router(r)
                registered_router_names.add(r.name)

            # Register presets provided by module
            presets = module.get_presets()
            if presets:
                preset_manager.register_presets(presets, bot_id=self.bot_id, promote=False)

            # Collect menu commands
            for cmd in module.get_bot_commands():
                if not any(c.command == cmd.command for c in aggregated_commands):
                    aggregated_commands.append(cmd)

        if self._custom_presets:
            preset_manager.register_presets(self._custom_presets, bot_id=self.bot_id, promote=False)

        if self._promoted_preset_ids:
            preset_manager.register_bot_promoted_presets(self.bot_id, self._promoted_preset_ids)

        return ModularBot(
            bot=bot,
            dp=dp,
            bot_id=self.bot_id,
            modules=self._modules,
            commands=aggregated_commands,
            constants=self.constants,
            strategy=self.strategy,
        )
