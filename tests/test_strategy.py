from unittest.mock import AsyncMock, patch

import pytest

from platform_core.config import PlatformSettings
from platform_core.modules.builder import ModularBotBuilder
from platform_core.server import BOT_INSTANCES, initialize_bot_instances


def test_default_platform_strategy():
    cfg = PlatformSettings()
    assert cfg.BOT_STRATEGY == "polling"


def test_builder_strategy_resolution(tmp_path):
    # Case 1: Explicit top-level strategy 'webhook'
    p1 = tmp_path / "bot1.yaml"
    p1.write_text("bot_id: bot1\nstrategy: webhook\n", encoding="utf-8")
    b1 = ModularBotBuilder.from_config(p1)
    assert b1.strategy == "webhook"

    # Case 2: Explicit top-level strategy 'polling'
    p2 = tmp_path / "bot2.yaml"
    p2.write_text("bot_id: bot2\nstrategy: polling\n", encoding="utf-8")
    b2 = ModularBotBuilder.from_config(p2)
    assert b2.strategy == "polling"

    # Case 3: Fallback from webhook.enabled = True
    p3 = tmp_path / "bot3.yaml"
    p3.write_text("bot_id: bot3\nwebhook:\n  enabled: true\n", encoding="utf-8")
    b3 = ModularBotBuilder.from_config(p3)
    assert b3.strategy == "webhook"

    # Case 4: Fallback from webhook.enabled = False -> polling
    p4 = tmp_path / "bot4.yaml"
    p4.write_text("bot_id: bot4\nwebhook:\n  enabled: false\n", encoding="utf-8")
    b4 = ModularBotBuilder.from_config(p4)
    assert b4.strategy == "polling"

    # Case 5: Default global fallback when neither is set
    p5 = tmp_path / "bot5.yaml"
    p5.write_text("bot_id: bot5\n", encoding="utf-8")
    b5 = ModularBotBuilder.from_config(p5)
    assert b5.strategy is None
    bot_app5 = b5.build()
    assert bot_app5.strategy == "polling"


@pytest.mark.asyncio
async def test_modular_bot_run_polling_clears_webhook():
    builder = ModularBotBuilder(
        bot_id="test_polling_bot", token="123456789:MOCK_TOKEN", strategy="polling"
    )
    bot_app = builder.build()

    with (
        patch.object(bot_app.bot, "delete_webhook", new_callable=AsyncMock) as mock_del,
        patch.object(bot_app.dp, "start_polling", new_callable=AsyncMock) as mock_poll,
    ):
        await bot_app.run(force_mock=True)

        mock_del.assert_awaited_once_with(drop_pending_updates=True)
        mock_poll.assert_awaited_once_with(bot_app.bot, bot_id="test_polling_bot", force_mock=True)


@pytest.mark.asyncio
async def test_server_initialization_skips_webhook_for_polling_bots():
    BOT_INSTANCES.clear()
    with patch("platform_core.server.settings.WEBHOOK_BASE_URL", "https://example.com"):
        await initialize_bot_instances()

        # Both admin_bot and image_bot_1 are set to polling strategy in instance configs
        assert len(BOT_INSTANCES) >= 2
        for bot_app in BOT_INSTANCES.values():
            assert bot_app.strategy == "polling"
            # Verify set_webhook was not invoked for polling bots
