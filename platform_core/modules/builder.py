import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import yaml
from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand
from platform_core.bot.middlewares import UserSyncMiddleware, I18nMiddleware
from platform_core.config import settings
from platform_core.metrics import MetricsMiddleware
from platform_core.modules.admin_control import AdminControlModule
from platform_core.modules.base import BaseBotModule
from platform_core.modules.image_gen import ImageGenModule
from platform_core.modules.monetization import MonetizationModule
from platform_core.modules.presets_module import PresetsModule
from platform_core.presets import preset_manager, PromptPreset

from aiogram.fsm.storage.memory import MemoryStorage
try:
    from aiogram.fsm.storage.redis import RedisStorage
    import redis.asyncio as aioredis
except ImportError:
    RedisStorage = None
    aioredis = None

logger = logging.getLogger(__name__)


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
        modules: List[BaseBotModule],
        commands: List[BotCommand],
        constants: Optional[Dict[str, Any]] = None,
        strategy: Optional[str] = None,
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
                logger.info(f"🌐 Modular Telegram Bot [{self.bot_id}] configured for WEBHOOK strategy.")
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
                    logger.warning(f"Webhook strategy enabled for [{self.bot_id}], but WEBHOOK_BASE_URL is not set.")
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

    def __init__(self, bot_id: str, token: Optional[str] = None, strategy: Optional[str] = None):
        self.bot_id = bot_id
        self.token = token
        self.strategy = strategy
        self.constants: Dict[str, Any] = {}
        self._modules: List[BaseBotModule] = []
        self._custom_presets: List[PromptPreset] = []

    def add_module(self, module: BaseBotModule) -> "ModularBotBuilder":
        """Adds a feature module to the bot."""
        self._modules.append(module)
        return self

    def load_presets_from_yaml(self, file_path: Union[str, Path]) -> "ModularBotBuilder":
        """Loads and attaches custom presets from a YAML file."""
        mod = PresetsModule.from_yaml_file(file_path)
        self._modules.append(mod)
        return self

    def load_presets_from_json(self, file_path: Union[str, Path]) -> "ModularBotBuilder":
        """Loads and attaches custom presets from a JSON file."""
        mod = PresetsModule.from_json_file(file_path)
        self._modules.append(mod)
        return self

    def add_preset(self, preset: PromptPreset) -> "ModularBotBuilder":
        """Attaches an individual custom preset."""
        self._custom_presets.append(preset)
        return self

    @classmethod
    def from_config(cls, config_path: Union[str, Path]) -> "ModularBotBuilder":
        """
        Creates a ModularBotBuilder pre-configured from a YAML configuration file.
        Supports tokens, environment variable names, custom constants, modules, and presets.
        """
        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(f"Bot config file not found: {path}")

        with open(path, "r", encoding="utf-8") as f:
            cfg: Dict[str, Any] = yaml.safe_load(f) or {}

        bot_id = cfg.get("bot_id") or path.stem
        token_env = cfg.get("token_env")
        token = cfg.get("token") or (os.getenv(token_env) if token_env else None)

        strat = cfg.get("strategy")
        if not strat:
            webhook_cfg = cfg.get("webhook", {})
            if isinstance(webhook_cfg, dict) and "enabled" in webhook_cfg:
                strat = "webhook" if webhook_cfg["enabled"] else "polling"

        builder = cls(bot_id=bot_id, token=token, strategy=strat)
        builder.constants = cfg.get("constants", {})

        # Parse modules
        modules_cfg = cfg.get("modules", [])
        for m_item in modules_cfg:
            if not isinstance(m_item, dict) or not m_item.get("enabled", True):
                continue

            m_name = m_item.get("name")
            opts = m_item.get("options", {})

            if m_name == "monetization":
                builder.add_module(MonetizationModule(**opts))
            elif m_name == "image_gen":
                builder.add_module(ImageGenModule(**opts))
            elif m_name == "admin_control":
                builder.add_module(AdminControlModule(**opts))
            elif m_name == "presets":
                preset_file = opts.get("file")
                if preset_file:
                    preset_path = Path(preset_file)
                    if not preset_path.is_absolute():
                        preset_path = path.parent / preset_path
                    if preset_path.exists():
                        builder.load_presets_from_yaml(preset_path)

        # Top-level presets_file or presets
        presets_file = cfg.get("presets_file")
        if presets_file:
            p_path = Path(presets_file)
            if not p_path.is_absolute():
                p_path = path.parent / p_path
            if p_path.exists():
                builder.load_presets_from_yaml(p_path)

        inline_presets = cfg.get("presets", [])
        if isinstance(inline_presets, list):
            for p_dict in inline_presets:
                if isinstance(p_dict, dict):
                    preset = PromptPreset(
                        id=p_dict["id"],
                        title=p_dict["title"],
                        description=p_dict.get("description", ""),
                        prompt_template=p_dict.get("prompt_template", "{user_prompt}"),
                        negative_prompt=p_dict.get("negative_prompt"),
                        aspect_ratio=p_dict.get("aspect_ratio", "1:1"),
                        category=p_dict.get("category", "General"),
                        icon=p_dict.get("icon", "✨"),
                    )
                    builder.add_preset(preset)

        return builder

    def build(self) -> ModularBot:
        """Assembles the ModularBot instance."""
        token = self.token
        if not token or ":" not in token:
            token = settings.IMAGE_BOT_TOKEN

        storage = MemoryStorage()
        if settings.REDIS_URL and RedisStorage and aioredis:
            try:
                redis_client = aioredis.from_url(settings.REDIS_URL)
                storage = RedisStorage(redis=redis_client)
            except Exception as e:
                logger.warning(f"Could not initialize RedisStorage ({e}), falling back to MemoryStorage.")

        bot = Bot(token=token)
        dp = Dispatcher(storage=storage)

        # Core outer middlewares
        dp.update.outer_middleware(UserSyncMiddleware())
        dp.update.outer_middleware(I18nMiddleware())
        dp.update.outer_middleware(MetricsMiddleware(bot_id=self.bot_id))

        aggregated_commands: List[BotCommand] = []
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
                preset_manager.register_presets(presets)

            # Collect menu commands
            for cmd in module.get_bot_commands():
                if not any(c.command == cmd.command for c in aggregated_commands):
                    aggregated_commands.append(cmd)

        if self._custom_presets:
            preset_manager.register_presets(self._custom_presets)

        return ModularBot(
            bot=bot,
            dp=dp,
            bot_id=self.bot_id,
            modules=self._modules,
            commands=aggregated_commands,
            constants=self.constants,
            strategy=self.strategy,
        )
