from pathlib import Path
import pytest
from platform_core.cli import get_instance_config_files, resolve_config_path
from platform_core.modules import ModularBotBuilder


def test_instances_directory_configs_exist():
    configs = get_instance_config_files()
    assert len(configs) >= 2
    stems = [c.stem for c in configs]
    assert "image_bot_1" in stems
    assert "admin_bot" in stems


def test_load_image_bot_1_config():
    path = resolve_config_path("image_bot_1")
    assert path is not None and path.exists()

    builder = ModularBotBuilder.from_config(path)
    assert builder.bot_id == "image_bot_1"
    assert builder.constants.get("daily_free_credits") == 3
    assert builder.constants.get("bot_title") == "Standard AI Image Studio"

    bot_app = builder.build()
    assert bot_app.bot_id == "image_bot_1"
    assert bot_app.constants.get("daily_free_credits") == 3


def test_load_admin_bot_config():
    path = resolve_config_path("admin_bot")
    assert path is not None and path.exists()

    builder = ModularBotBuilder.from_config(path)
    assert builder.bot_id == "admin_bot"
    assert builder.constants.get("bot_title") == "Platform Admin Control Bot"


def test_resolve_config_path_variants():
    assert resolve_config_path("image_bot_1") == Path("instances/image_bot_1.yaml")
    assert resolve_config_path("admin_bot") == Path("instances/admin_bot.yaml")
    assert resolve_config_path("non_existent_bot") is None

