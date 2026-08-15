import json
from pathlib import Path

import pytest
from pydantic import BaseModel

from platform_core.bot import GenerationStateData
from platform_core.db import (
    AnalyticsEvent,
    BotBreakdownMetric,
    BotEvent,
    ButtonClickMetric,
    CommandMetric,
    ErrorBreakdownMetric,
    GenerationLog,
    MessageBreakdownMetric,
    MetricsSummary,
    ModelBreakdownMetric,
    RecentEventMetric,
    StarTransaction,
    UserBalance,
    UserProfile,
    db,
)
from platform_core.events import (
    ButtonClickEvent,
    CommandEvent,
    CustomEvent,
    ErrorEvent,
    GenerationEvent,
    MessageSentEvent,
    PaymentEvent,
)
from platform_core.generators import GenerationRequest, GenerationResponse
from platform_core.modules import (
    AdminControlModule,
    BotInstanceConfig,
    ImageGenModule,
    ModuleConfig,
    ModuleInfo,
    MonetizationModule,
    PresetsModule,
    WebhookConfig,
)
from platform_core.payments import StarPackage
from platform_core.presets import PresetCollection, PromptPreset
from platform_core.queue import GenerationJob
from platform_core.server import GatewayRootResponse, HealthCheckResponse


def test_all_core_data_structures_are_pydantic_models():
    """Verify that all core platform data structures inherit from pydantic.BaseModel."""
    models_to_check = [
        UserProfile,
        UserBalance,
        StarTransaction,
        AnalyticsEvent,
        BotEvent,
        GenerationLog,
        ButtonClickMetric,
        CommandMetric,
        BotBreakdownMetric,
        ModelBreakdownMetric,
        MessageBreakdownMetric,
        ErrorBreakdownMetric,
        RecentEventMetric,
        MetricsSummary,
        GenerationJob,
        ModuleInfo,
        ModuleConfig,
        WebhookConfig,
        BotInstanceConfig,
        PromptPreset,
        PresetCollection,
        GenerationStateData,
        GenerationRequest,
        GenerationResponse,
        StarPackage,
        GatewayRootResponse,
        HealthCheckResponse,
        ButtonClickEvent,
        CommandEvent,
        CustomEvent,
        ErrorEvent,
        GenerationEvent,
        MessageSentEvent,
        PaymentEvent,
    ]

    for model_cls in models_to_check:
        assert issubclass(model_cls, BaseModel), (
            f"{model_cls.__name__} does not inherit from pydantic.BaseModel"
        )


def test_generation_job_pydantic_json_serialization():
    job = GenerationJob(
        job_id="job_pydantic_99",
        bot_id="image_bot_1",
        bot_token="12345:TOKEN",
        user_id=42,
        chat_id=100,
        status_message_id=200,
        prompt="A vibrant synthwave sunset over mountains",
        model_name="google/gemini-2.5-flash-image",
        media_type="image",
        cost=2,
        extra_params={"cfg_scale": 7.5, "seed": 12345},
    )

    # 1. Native Pydantic JSON serialization
    json_str = job.model_dump_json()
    assert isinstance(json_str, str)
    parsed_json = json.loads(json_str)
    assert parsed_json["job_id"] == "job_pydantic_99"
    assert parsed_json["cost"] == 2
    assert parsed_json["extra_params"]["seed"] == 12345

    # 2. Deserialization via model_validate_json
    reconstructed = GenerationJob.model_validate_json(json_str)
    assert reconstructed.job_id == job.job_id
    assert reconstructed.extra_params == job.extra_params
    assert reconstructed.prompt == job.prompt

    # 3. Helper methods to_json and from_json
    assert GenerationJob.from_json(job.to_json()).job_id == "job_pydantic_99"


def test_metrics_summary_and_breakdowns_serialization():
    btn = ButtonClickMetric(name="preset:anime", count=10, unique_users=5, avg_duration_ms=45)
    cmd = CommandMetric(name="/start", count=20, unique_users=15, avg_duration_ms=12)
    bot = BotBreakdownMetric(bot_id="bot_1", users=50, clicks=100, commands=80, generations=20)
    model = ModelBreakdownMetric(
        model_name="gemini", total=20, success=19, failed=1, avg_duration_ms=800
    )
    msg = MessageBreakdownMetric(type="text", count=50, unique_users=25, avg_chars=100)
    err = ErrorBreakdownMetric(
        error_type="Timeout", count=2, unique_users=2, last_message="Timed out"
    )
    evt = RecentEventMetric(
        event="/generate", bot_id="bot_1", user_id=123, duration_ms=50, created_at="12:00:00"
    )

    summary = MetricsSummary(
        total_users=50,
        total_events=300,
        total_commands=80,
        total_button_clicks=100,
        total_generations=20,
        successful_generations=19,
        failed_generations=1,
        total_messages_sent=50,
        total_errors=2,
        total_stars_earned=500,
        top_presets=[("preset:anime", 10)],
        top_buttons=[btn],
        top_commands=[cmd],
        bots_breakdown=[bot],
        models_breakdown=[model],
        messages_breakdown=[msg],
        errors_breakdown=[err],
        recent_events=[evt],
    )

    # Validate JSON serialization and schema completeness
    dumped_json = summary.model_dump_json()
    assert isinstance(dumped_json, str)
    loaded = MetricsSummary.model_validate_json(dumped_json)

    assert loaded.total_users == 50
    assert loaded.top_buttons[0].name == "preset:anime"
    assert loaded.models_breakdown[0].model_name == "gemini"

    # Validate dual access: attribute and dict subscript access
    assert summary.top_buttons[0].name == "preset:anime"
    assert summary["top_buttons"][0]["name"] == "preset:anime"
    assert summary.get("total_users") == 50


def test_module_info_pydantic_models():
    gen_mod = ImageGenModule()
    info_gen = gen_mod.get_module_info()
    assert isinstance(info_gen, ModuleInfo)
    assert info_gen.name == "image_gen"
    assert info_gen["presets_count"] == 0
    assert "default_model" in info_gen.details

    mon_mod = MonetizationModule()
    info_mon = mon_mod.get_module_info()
    assert isinstance(info_mon, ModuleInfo)
    assert info_mon.name == "monetization"
    assert info_mon.get("enable_credit_check") is True

    pres_mod = PresetsModule([])
    info_pres = pres_mod.get_module_info()
    assert isinstance(info_pres, ModuleInfo)
    assert info_pres.name == "presets"
    assert info_pres["presets_count"] == 0

    admin_mod = AdminControlModule()
    info_admin = admin_mod.get_module_info()
    assert isinstance(info_admin, ModuleInfo)
    assert info_admin.name == "admin_control"


def test_bot_instance_config_pydantic_validation(tmp_path: Path):
    cfg_data = {
        "bot_id": "test_validation_bot",
        "strategy": "webhook",
        "token_env": "TEST_TOKEN_VAR",
        "webhook": {"enabled": True, "path": "/webhook/test_bot"},
        "constants": {"welcome_bonus": 10},
        "promoted_presets": ["p1", "p2"],
        "modules": [
            {"name": "image_gen", "enabled": True, "options": {"default_model": "flux"}},
            {"name": "monetization", "enabled": False},
        ],
        "presets": [
            {
                "id": "p1",
                "title": "Preset One",
                "prompt_template": "P1 {user_prompt}",
            }
        ],
    }

    config = BotInstanceConfig.model_validate(cfg_data)
    assert config.bot_id == "test_validation_bot"
    assert config.strategy == "webhook"
    assert config.webhook.enabled is True
    assert len(config.modules) == 2
    assert config.modules[0].options["default_model"] == "flux"
    assert len(config.presets) == 1
    assert config.presets[0].title == "Preset One"

    # YAML serialization/loading verification
    yaml_file = tmp_path / "test_config.yaml"
    import yaml

    yaml_file.write_text(yaml.dump(cfg_data), encoding="utf-8")

    from_yaml_config = BotInstanceConfig.from_yaml_file(yaml_file)
    assert from_yaml_config.bot_id == "test_validation_bot"
    assert from_yaml_config.strategy == "webhook"


def test_server_pydantic_response_models():
    root_resp = GatewayRootResponse(configured_bots=["bot_a", "bot_b"])
    assert root_resp.service == "Telegram AI Bot Platform Webhook Gateway"
    assert root_resp.status == "online"
    assert root_resp.configured_bots == ["bot_a", "bot_b"]

    json_str = root_resp.model_dump_json()
    assert "bot_a" in json_str

    health_resp = HealthCheckResponse(
        active_bot_count=2, bot_ids=["bot_a", "bot_b"], pending_queue_length=0
    )
    assert health_resp.status == "healthy"
    assert health_resp.active_bot_count == 2


def test_fsm_generation_state_data_model():
    state_data = GenerationStateData(
        selected_preset_id="cyberpunk",
        reference_file_id="tg_file_12345",
        custom_prompt="flying cars",
    )
    assert state_data.selected_preset_id == "cyberpunk"
    assert state_data["reference_file_id"] == "tg_file_12345"
    assert state_data.get("custom_prompt") == "flying cars"

    # Validation from dict
    raw = {"selected_preset_id": "anime", "extra_data": {"mode": "fast"}}
    validated = GenerationStateData.model_validate(raw)
    assert validated.selected_preset_id == "anime"
    assert validated["mode"] == "fast"


@pytest.mark.asyncio
async def test_db_get_metrics_summary_returns_pydantic_metrics_summary():
    bot_id = "pydantic_db_test_bot"
    await db.record_event(
        BotEvent(
            bot_id=bot_id,
            user_id=5555,
            event_type="click",
            event_name="preset:cyberpunk",
            duration_ms=30,
        )
    )

    summary = await db.get_metrics_summary(bot_id=bot_id)
    assert isinstance(summary, MetricsSummary)
    assert summary.total_button_clicks >= 1
    assert len(summary.top_buttons) >= 1
    assert isinstance(summary.top_buttons[0], ButtonClickMetric)

    buttons = await db.get_button_click_metrics(bot_id=bot_id)
    assert isinstance(buttons, list)
    assert all(isinstance(b, ButtonClickMetric) for b in buttons)
