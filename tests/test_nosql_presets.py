import pytest
from platform_core.presets import PromptPreset, preset_manager
from platform_core.db.nosql import nosql_manager


@pytest.mark.asyncio
async def test_nosql_preset_crud():
    preset = PromptPreset(
        id="test_nosql_1",
        title="Test NoSQL Preset",
        description="Testing NoSQL preset storage",
        icon="🚀",
        prompt_template="A futuristic space station, {user_prompt}",
        category="Sci-Fi",
        media_type="image",
        target_bot_id="image_bot_1",
        is_active=True,
    )

    # 1. Save preset
    saved = await nosql_manager.save_preset(preset)
    assert saved.id == "test_nosql_1"
    assert saved.title == "Test NoSQL Preset"

    # 2. Get preset by ID
    fetched = await nosql_manager.get_preset_by_id("test_nosql_1")
    assert fetched is not None
    assert fetched.prompt_template == "A futuristic space station, {user_prompt}"

    # 3. Presets ordering with bot_id prioritization (common presets with bot promotion)
    bot1_presets = await nosql_manager.get_presets(bot_id="image_bot_1")
    assert any(p.id == "test_nosql_1" for p in bot1_presets)
    assert bot1_presets[0].id == "test_nosql_1"  # Promoted to top for image_bot_1

    bot2_presets = await nosql_manager.get_presets(bot_id="image_bot_2")
    assert any(p.id == "test_nosql_1" for p in bot2_presets)  # Common preset accessible to image_bot_2

    # 4. Toggle active status
    updated = await nosql_manager.toggle_preset_active("test_nosql_1", is_active=False)
    assert updated is not None
    assert updated.is_active is False

    active_only = await nosql_manager.get_presets(bot_id="image_bot_1", include_inactive=False)
    assert not any(p.id == "test_nosql_1" for p in active_only)

    all_with_inactive = await nosql_manager.get_presets(bot_id="image_bot_1", include_inactive=True)
    assert any(p.id == "test_nosql_1" for p in all_with_inactive)

    # 5. Delete preset
    del_res = await nosql_manager.delete_preset("test_nosql_1")
    assert del_res is True

    deleted_check = await nosql_manager.get_preset_by_id("test_nosql_1")
    assert deleted_check is None


@pytest.mark.asyncio
async def test_preset_manager_nosql_integration():
    preset = PromptPreset(
        id="test_mgr_1",
        title="Manager NoSQL Integration",
        description="Integration test",
        prompt_template="High resolution fantasy landscape, {user_prompt}",
        target_bot_id="all",
    )

    await preset_manager.save_preset(preset)

    presets = await preset_manager.get_presets(force_reload=True)
    assert any(p.id == "test_mgr_1" for p in presets)

    # Clean up
    await preset_manager.delete_preset("test_mgr_1")
    after_del = await preset_manager.get_presets(force_reload=True, include_inactive=True)
    assert not any(p.id == "test_mgr_1" for p in after_del)
