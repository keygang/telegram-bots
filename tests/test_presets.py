import pytest

from platform_core.presets import get_preset_by_id, preset_manager


@pytest.mark.asyncio
async def test_preset_manager_fetching():
    await preset_manager.seed_presets_from_file("bots/image_bot/presets.yaml")
    presets = await preset_manager.fetch_presets(force_reload=True)
    assert len(presets) >= 6

    image_presets = await preset_manager.get_presets("image")
    assert len(image_presets) >= 6


@pytest.mark.asyncio
async def test_preset_manager_get_by_id():
    await preset_manager.seed_presets_from_file("bots/image_bot/presets.yaml")
    odyssey = await preset_manager.get_preset_by_id("odyssey")
    assert odyssey is not None
    assert odyssey.title == "Homer's Odyssey Warrior"


@pytest.mark.asyncio
async def test_seed_presets_script(tmp_path):
    custom_yaml = tmp_path / "test_presets.yaml"
    custom_yaml.write_text(
        """
presets:
  - id: "custom_db_1"
    title: "Custom DB Preset"
    description: "Custom description"
    prompt_template: "Prompt template {user_prompt}"
    category: "custom"
    media_type: "image"
""",
        encoding="utf-8",
    )
    count = await preset_manager.seed_presets_from_file(custom_yaml)
    assert count == 1

    fetched = await preset_manager.get_preset_by_id("custom_db_1")
    assert fetched is not None
    assert fetched.title == "Custom DB Preset"


def test_build_prompt():
    odyssey = get_preset_by_id("odyssey")
    prompt = odyssey.build_prompt("John Doe")
    assert "John Doe" in prompt
