from pathlib import Path
import pytest
from platform_core.cli import get_instance_config_files, resolve_config_path
from platform_core.modules import ModularBotBuilder


def test_instances_directory_configs_exist():
    configs = get_instance_config_files()
    assert len(configs) >= 2
    stems = [c.stem for c in configs]
    assert "image_bot_1" in stems
    assert "image_bot_2" in stems


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


def test_load_image_bot_2_inline_presets():
    path = resolve_config_path("image_bot_2")
    assert path is not None and path.exists()

    builder = ModularBotBuilder.from_config(path)
    assert builder.bot_id == "image_bot_2"
    assert len(builder._custom_presets) == 2
    assert builder._custom_presets[0].id == "anime_masterpiece"
    assert builder._custom_presets[1].id == "fantasy_realm"


def test_resolve_config_path_variants():
    assert resolve_config_path("image_bot_1") == Path("instances/image_bot_1.yaml")
    assert resolve_config_path("non_existent_bot") is None
