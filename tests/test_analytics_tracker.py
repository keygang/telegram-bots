import pytest

from platform_core.db import AnalyticsEvent, db
from platform_core.events import (
    ButtonClickEvent,
    CommandEvent,
    CustomEvent,
    ErrorEvent,
    GenerationEvent,
    MessageSentEvent,
    PaymentEvent,
    get_tracker,
)


@pytest.mark.asyncio
async def test_track_command_event():
    tracker = get_tracker("test_cmd_bot")
    user_id = 112233

    cmd_evt = CommandEvent(
        distinct_id=user_id,
        command="/start",
        chat_type="private",
        text_length=6,
        duration_ms=10,
    )

    result = await tracker.track(cmd_evt)

    assert isinstance(result, AnalyticsEvent)
    assert result.event == "/start"
    assert result.distinct_id == str(user_id)
    assert result.bot_id == "test_cmd_bot"
    assert result.duration_ms == 10
    assert result.properties["chat_type"] == "private"
    assert result.properties["text_length"] == 6


@pytest.mark.asyncio
async def test_track_button_click_event():
    tracker = get_tracker("test_click_bot")
    user_id = 223344

    click_evt = ButtonClickEvent(
        distinct_id=user_id,
        button_id="preset_cyberpunk",
        menu="presets_main",
        message_id=456,
        duration_ms=15,
    )

    result = await tracker.track(click_evt)

    assert result.event == "preset_cyberpunk"
    assert result.properties["button_id"] == "preset_cyberpunk"
    assert result.properties["menu"] == "presets_main"
    assert result.properties["message_id"] == 456


@pytest.mark.asyncio
async def test_track_generation_event_and_timed():
    tracker = get_tracker("test_gen_bot")
    user_id = 334455

    # Test direct track
    gen_evt = GenerationEvent(
        distinct_id=user_id,
        model_name="google/gemini-2.5-flash-image",
        prompt="Cyberpunk street at night",
        preset_id="cyberpunk",
        duration_ms=1200,
        status="success",
        media_url="https://example.com/art.png",
        tokens_spent=1,
    )
    result = await tracker.track(gen_evt)

    assert result.event == "generation_completed"
    assert result.status == "success"
    assert result.properties["model_name"] == "google/gemini-2.5-flash-image"
    assert result.properties["preset_id"] == "cyberpunk"
    assert result.properties["tokens_spent"] == 1

    # Test timed context manager with GenerationEvent
    async with tracker.timed(
        GenerationEvent,
        distinct_id=user_id,
        model_name="flux-schnell",
        prompt="Futuristic car",
    ) as ctx:
        ctx["media_url"] = "https://example.com/car.png"

    events = await db.query_events(event="generation_completed", distinct_id=str(user_id))
    assert len(events) >= 2
    latest = events[0]
    assert latest.properties["model_name"] == "flux-schnell"
    assert latest.properties["media_url"] == "https://example.com/car.png"
    assert latest.duration_ms is not None


@pytest.mark.asyncio
async def test_track_payment_and_error_events():
    tracker = get_tracker("test_pay_bot")
    user_id = 445566

    pay_evt = PaymentEvent(
        distinct_id=user_id,
        stars_amount=100,
        credits_added=50,
        charge_id="tg_charge_abc123",
        invoice_payload="credits_pack_50",
    )
    pay_res = await tracker.track(pay_evt)
    assert pay_res.event == "payment_completed"
    assert pay_res.properties["stars_amount"] == 100
    assert pay_res.properties["credits_added"] == 50

    err_evt = ErrorEvent(
        distinct_id=user_id,
        error_type="ProviderTimeout",
        error_message="Upstream API took too long",
        component="fal_ai_client",
    )
    err_res = await tracker.track(err_evt)
    assert err_res.event == "error:ProviderTimeout"
    assert err_res.status == "error"
    assert err_res.properties["component"] == "fal_ai_client"


@pytest.mark.asyncio
async def test_track_custom_event_and_properties_filtering():
    tracker = get_tracker("custom_analytics_bot", environment="staging")

    evt1 = CustomEvent(
        distinct_id=556677,
        name="ab_test_exposure",
        data={"experiment": "new_ui_v2", "variant": "B"},
    )
    evt2 = CustomEvent(
        distinct_id=556678,
        name="ab_test_exposure",
        data={"experiment": "new_ui_v2", "variant": "A"},
    )

    await tracker.track(evt1)
    await tracker.track(evt2)

    results_variant_b = await db.query_events(
        bot_id="custom_analytics_bot",
        event="ab_test_exposure",
        property_filters={"variant": "B"},
    )
    assert len(results_variant_b) == 1
    assert results_variant_b[0].properties["variant"] == "B"
    assert results_variant_b[0].properties["environment"] == "staging"


@pytest.mark.asyncio
async def test_track_message_sent_event():
    tracker = get_tracker("test_msg_bot")
    user_id = 998877

    msg_evt = MessageSentEvent(
        distinct_id=user_id,
        message_type="photo",
        text_length=120,
        has_reply_markup=True,
        chat_type="private",
        duration_ms=45,
    )

    result = await tracker.track(msg_evt)

    assert result.event == "message_sent:photo"
    assert result.distinct_id == str(user_id)
    assert result.properties["message_type"] == "photo"
    assert result.properties["text_length"] == 120
    assert result.properties["has_reply_markup"] is True

    summary = await db.get_metrics_summary(bot_id="test_msg_bot")
    assert summary["total_messages_sent"] >= 1
    assert any(m["type"] == "photo" for m in summary["messages_breakdown"])


@pytest.mark.asyncio
async def test_disabled_tracker_analytics_ignored():
    disabled_tracker = get_tracker("crm_bot", enabled=False)
    user_id = 12345

    cmd_evt = CommandEvent(
        distinct_id=user_id,
        bot_id="crm_bot",
        command="/crm_menu",
    )
    btn_evt = ButtonClickEvent(
        distinct_id=user_id,
        bot_id="crm_bot",
        button_id="crm_analytics",
    )

    await disabled_tracker.track(cmd_evt)
    await disabled_tracker.track(btn_evt)

    # Verify events are not saved to database/analytics store
    events = await db.query_events(bot_id="crm_bot")
    assert len(events) == 0

    summary = await db.get_metrics_summary()
    assert not any(b["bot_id"] == "crm_bot" for b in summary["bots_breakdown"])
