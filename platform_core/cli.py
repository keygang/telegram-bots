import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import List, Optional
import yaml
from platform_core.config import settings
from platform_core.modules.builder import ModularBotBuilder, ModularBot

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("platform_cli")

INSTANCES_DIR = Path("instances")


def get_instance_config_files() -> List[Path]:
    """Finds all instance YAML configuration files in instances/ directory."""
    if not INSTANCES_DIR.exists():
        return []
    configs = list(INSTANCES_DIR.glob("*.yaml")) + list(INSTANCES_DIR.glob("*.yml"))
    return sorted(configs)


def resolve_config_path(bot_name_or_path: str) -> Optional[Path]:
    """Resolves a bot name or path to a valid configuration file."""
    path = Path(bot_name_or_path)
    if path.exists() and path.is_file():
        return path

    if INSTANCES_DIR.exists():
        yaml_path = INSTANCES_DIR / f"{bot_name_or_path}.yaml"
        if yaml_path.exists():
            return yaml_path
        yml_path = INSTANCES_DIR / f"{bot_name_or_path}.yml"
        if yml_path.exists():
            return yml_path

    return None


def list_instances():
    """Prints a summary of all configured bot instances found in instances/."""
    configs = get_instance_config_files()
    if not configs:
        print("ℹ️ No bot instance configuration files found in instances/ directory.")
        return

    print(f"\n📋 Configured Bot Instances ({len(configs)} found in {INSTANCES_DIR.absolute()}):\n" + "─" * 70)
    for cfg_path in configs:
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            bot_id = data.get("bot_id", cfg_path.stem)
            token_env = data.get("token_env", "N/A")
            modules = [m.get("name") for m in data.get("modules", []) if isinstance(m, dict) and m.get("enabled", True)]
            preset_count = len(data.get("presets", []))
            print(f"  • Bot ID      : {bot_id}")
            print(f"    Config Path : {cfg_path}")
            print(f"    Token Env   : {token_env}")
            print(f"    Modules     : {', '.join(modules) if modules else 'None'}")
            print(f"    Presets     : {preset_count} inline preset(s)")
            print("─" * 70)
        except Exception as e:
            print(f"  ❌ Error reading {cfg_path}: {e}")


async def run_bot_instance(config_path: Path, force_mock: bool = False):
    """Loads a bot instance from YAML config and starts polling."""
    logger.info(f"Loading bot instance from configuration: {config_path}")
    builder = ModularBotBuilder.from_config(config_path)
    bot_app = builder.build()
    await bot_app.run(force_mock=force_mock)


async def run_all_instances(force_mock: bool = False):
    """Loads and starts all configured bot instances concurrently."""
    configs = get_instance_config_files()
    if configs:
        logger.info(f"🚀 Found {len(configs)} instance configs in instances/. Launching all concurrently...")
        bot_apps: List[ModularBot] = []
        for cfg_path in configs:
            try:
                builder = ModularBotBuilder.from_config(cfg_path)
                bot_apps.append(builder.build())
            except Exception as e:
                logger.error(f"Failed to load bot config from {cfg_path}: {e}")

        if bot_apps:
            await asyncio.gather(*[app.run(force_mock=force_mock) for app in bot_apps])
            return

    # Fallback if no instance files are defined
    logger.info("No YAML instance files found in instances/. Falling back to legacy default image bot...")
    from bots.image_bot.bot import run_image_bot
    await run_image_bot(force_mock=force_mock)


def main():
    parser = argparse.ArgumentParser(description="Extensible Telegram AI Bot Platform CLI Runner")
    subparsers = parser.add_subparsers(dest="command", help="Sub-commands")

    # Command: start
    start_parser = subparsers.add_parser("start", help="Start a Telegram bot instance")
    start_parser.add_argument(
        "bot_name",
        nargs="?",
        default="all",
        help="Name or path of the bot instance to launch (e.g. 'image_bot_1', 'all', or 'instances/image_bot_1.yaml')",
    )
    start_parser.add_argument(
        "--config",
        "-c",
        type=str,
        help="Explicit path to YAML bot instance config file",
    )
    start_parser.add_argument(
        "--mock",
        action="store_true",
        help="Force mock AI generator mode (no API keys required)",
    )

    # Command: server
    server_parser = subparsers.add_parser("server", help="Launch FastAPI Telegram Webhook Gateway Server")
    server_parser.add_argument("--host", default=settings.SERVER_HOST, help="Host interface to bind")
    server_parser.add_argument("--port", type=int, default=settings.SERVER_PORT, help="Port to bind")
    server_parser.add_argument("--reload", action="store_true", help="Enable uvicorn auto-reload")

    # Command: worker
    worker_parser = subparsers.add_parser("worker", help="Launch background AI Generation worker pool")
    worker_parser.add_argument("--concurrency", type=int, default=4, help="Worker concurrency count")
    worker_parser.add_argument("--mock", action="store_true", help="Force mock AI generator mode")

    # Command: list
    subparsers.add_parser("list", help="List all configured bot instances in instances/")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "list":
        list_instances()
        sys.exit(0)

    if args.command == "server":
        import uvicorn
        logger.info(f"🚀 Launching Webhook Gateway Server at http://{args.host}:{args.port}")
        uvicorn.run("platform_core.server:app", host=args.host, port=args.port, reload=args.reload)
        sys.exit(0)

    if args.command == "worker":
        from platform_core.queue.worker import AIWorkerPool
        force_mock = args.mock or settings.USE_MOCK_GENERATOR
        logger.info(f"⚙️ Launching AI Worker Pool (Concurrency: {args.concurrency}, Mock: {force_mock})")
        pool = AIWorkerPool(concurrency=args.concurrency, force_mock=force_mock)
        try:
            asyncio.run(pool.start())
        except KeyboardInterrupt:
            asyncio.run(pool.stop())
        sys.exit(0)

    if args.command == "start":
        force_mock = args.mock or settings.USE_MOCK_GENERATOR
        if force_mock:
            logger.info("⚡ Launching in MOCK mode (Offline testing with zero API credit usage)")

        config_file: Optional[Path] = None
        if args.config:
            config_file = Path(args.config)
            if not config_file.exists():
                logger.error(f"Specified config file not found: {args.config}")
                sys.exit(1)

        if not config_file and args.bot_name != "all":
            resolved = resolve_config_path(args.bot_name)
            if resolved:
                config_file = resolved
            elif args.bot_name == "image_bot":
                from bots.image_bot.bot import run_image_bot
                asyncio.run(run_image_bot(force_mock=force_mock))
                sys.exit(0)
            elif args.bot_name == "admin_bot":
                from bots.admin_bot.bot import run_admin_bot
                asyncio.run(run_admin_bot())
                sys.exit(0)
            else:
                logger.error(f"Could not find bot instance configuration for '{args.bot_name}' in instances/ directory.")
                sys.exit(1)

        if config_file:
            asyncio.run(run_bot_instance(config_file, force_mock=force_mock))
        else:
            asyncio.run(run_all_instances(force_mock=force_mock))


if __name__ == "__main__":
    main()
