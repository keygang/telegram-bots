import json
from pathlib import Path
import pytest
from platform_core.presets import (
    load_presets_from_dict,
    load_presets_from_yaml_string,
    load_presets_from_yaml_file,
    load_presets_from_json_file,
    preset_manager,
    PromptPreset,
)

SAMPLE_YAML = """
presets:
  - id: "test_cyberpunk"
    title: "Test Cyberpunk"
    description: "Cyberpunk test preset"
    icon: "🌆"
    category: "scifi"
    media_type: "image"
    prompt_template: "Cyberpunk style {user_prompt}"
    default_model: "flux-schnell"
"""


def test_load_presets_from_dict():
    data = [
        {
            "id": "dict_preset_1",
            "title": "Dict Preset 1",
            "description": "Desc 1",
            "prompt_template": "Template {user_prompt}",
        }
    ]
    presets = load_presets_from_dict(data)
    assert len(presets) == 1
    assert presets[0].id == "dict_preset_1"


def test_load_presets_from_yaml_string():
    presets = load_presets_from_yaml_string(SAMPLE_YAML)
    assert len(presets) == 1
    assert presets[0].id == "test_cyberpunk"
    assert presets[0].title == "Test Cyberpunk"


def test_load_presets_from_yaml_file(tmp_path: Path):
    yaml_file = tmp_path / "custom_presets.yaml"
    yaml_file.write_text(SAMPLE_YAML, encoding="utf-8")

    presets = load_presets_from_yaml_file(yaml_file)
    assert len(presets) == 1
    assert presets[0].id == "test_cyberpunk"


def test_load_presets_from_json_file(tmp_path: Path):
    json_file = tmp_path / "custom_presets.json"
    json_content = {
        "presets": [
            {
                "id": "json_preset",
                "title": "JSON Preset",
                "description": "JSON Desc",
                "prompt_template": "JSON Prompt {user_prompt}",
            }
        ]
    }
    json_file.write_text(json.dumps(json_content), encoding="utf-8")

    presets = load_presets_from_json_file(json_file)
    assert len(presets) == 1
    assert presets[0].id == "json_preset"


@pytest.mark.asyncio
async def test_preset_manager_custom_registration():
    preset_manager.clear_custom_presets()
    custom = PromptPreset(
        id="custom_override_id",
        title="Custom Title",
        description="Custom Desc",
        prompt_template="Prompt {user_prompt}",
    )
    preset_manager.register_preset(custom)

    all_presets = await preset_manager.get_presets(force_reload=True)
    assert any(p.id == "custom_override_id" for p in all_presets)

    found = await preset_manager.get_preset_by_id("custom_override_id")
    assert found is not None
    assert found.title == "Custom Title"
