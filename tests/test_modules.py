from pathlib import Path

from platform_core.modules import (
    AdminControlModule,
    ImageGenModule,
    ModularBotBuilder,
    MonetizationModule,
)
from platform_core.presets import PromptPreset


def test_modules_instantiation():
    monetization = MonetizationModule()
    image_gen = ImageGenModule()
    admin_control = AdminControlModule()

    assert monetization.name == "monetization"
    assert image_gen.name == "image_gen"
    assert admin_control.name == "admin_control"

    cmds_monetization = monetization.get_bot_commands()
    assert any(c.command == "buy" for c in cmds_monetization)
    assert not any(c.command == "start" for c in cmds_monetization)

    cmds_image = image_gen.get_bot_commands()
    assert any(c.command == "generate" for c in cmds_image)
    assert not any(c.command == "start" for c in cmds_image)
    assert not any(c.command == "stats" for c in cmds_image)

    cmds_admin = admin_control.get_bot_commands()
    assert any(c.command == "admin" for c in cmds_admin)
    assert any(c.command == "stats" for c in cmds_admin)
    assert not any(c.command == "start" for c in cmds_admin)


def test_builder_fluent_assembly():
    builder = (
        ModularBotBuilder(bot_id="test_bot", token="123456789:AAA_BBB_CCC")
        .add_module(MonetizationModule())
        .add_module(ImageGenModule(default_model="google/gemini-2.5-flash-image"))
        .add_preset(
            PromptPreset(
                id="inline_preset_1",
                title="Inline 1",
                description="Desc 1",
                prompt_template="Inline {user_prompt}",
            )
        )
    )

    bot_app = builder.build()
    assert bot_app.bot_id == "test_bot"
    assert len(bot_app.modules) == 2
    assert len(bot_app.commands) >= 4


def test_builder_from_yaml_config(tmp_path: Path):
    presets_yaml = tmp_path / "my_presets.yaml"
    presets_yaml.write_text(
        """
presets:
  - id: "yaml_bot_preset"
    title: "YAML Bot Preset"
    description: "YAML Desc"
    prompt_template: "Template {user_prompt}"
""",
        encoding="utf-8",
    )

    config_yaml = tmp_path / "bot_config.yaml"
    config_yaml.write_text(
        f"""
bot_id: "config_test_bot"
token: "12345:TOKEN_TEST"
modules:
  - name: "monetization"
    enabled: true
  - name: "image_gen"
    enabled: true
    options:
      default_model: "google/gemini-2.5-flash-image"
  - name: "presets"
    enabled: true
    options:
      file: "{presets_yaml}"
  - name: "admin_control"
    enabled: true
""",
        encoding="utf-8",
    )

    builder = ModularBotBuilder.from_config(config_yaml)
    bot_app = builder.build()

    assert bot_app.bot_id == "config_test_bot"
    assert len(bot_app.modules) == 4
