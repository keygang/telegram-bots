import logging
from pathlib import Path
from platform_core.config import settings
from platform_core.modules import (
    ModularBotBuilder,
    MonetizationModule,
    ImageGenModule,
    PresetsModule,
)

logger = logging.getLogger("image_bot")


async def run_image_bot(force_mock: bool = False):
    """
    Launches the Image Generation Telegram Bot instance using Modular Architecture.
    """
    presets_yaml = Path(__file__).parent / "presets.yaml"

    builder = (
        ModularBotBuilder(bot_id="image_bot", token=settings.IMAGE_BOT_TOKEN)
        .add_module(MonetizationModule())
        .add_module(ImageGenModule(default_model="google/gemini-2.5-flash-image"))
    )

    if presets_yaml.exists():
        builder.add_module(PresetsModule.from_yaml_file(presets_yaml))

    bot_app = builder.build()
    await bot_app.run(force_mock=force_mock)
