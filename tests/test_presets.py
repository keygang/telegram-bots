import pytest
from platform_core.presets import preset_manager, DEFAULT_IMAGE_PRESETS, get_preset_by_id


@pytest.mark.asyncio
async def test_preset_manager_fetching():
    presets = await preset_manager.fetch_presets(force_reload=True)
    assert len(presets) >= 5

    image_presets = await preset_manager.get_presets("image")
    assert len(image_presets) >= 5


@pytest.mark.asyncio
async def test_preset_manager_get_by_id():
    odyssey = await preset_manager.get_preset_by_id("odyssey")
    assert odyssey is not None
    assert odyssey.title == "Homer's Odyssey Warrior"


def test_build_prompt():
    odyssey = get_preset_by_id("odyssey")
    prompt = odyssey.build_prompt("John Doe")
    assert "John Doe" in prompt
