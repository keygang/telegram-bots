from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from bots.admin_bot.formatters import (
    format_bots_breakdown_table,
    format_button_clicks_table,
    format_commands_table,
    format_errors_table,
    format_live_events_table,
    format_messages_table,
    format_models_table,
    render_analytics_overview_text,
)
from bots.admin_bot.keyboards import (
    build_analytics_keyboard,
    build_analytics_subview_keyboard,
)
from platform_core.db import db

analytics_router = Router(name="admin_analytics_router")


@analytics_router.message(Command("stats"))
async def cmd_admin_stats(message: Message):
    """Displays platform metrics and telemetry summary for admins."""
    text = await render_analytics_overview_text()
    await message.answer(text, reply_markup=build_analytics_keyboard(), parse_mode="HTML")


@analytics_router.callback_query(F.data == "admin_analytics")
async def cb_analytics(query: CallbackQuery):
    """Displays platform metrics, DB telemetry summary, and queue status."""
    text = await render_analytics_overview_text()
    await query.message.edit_text(text, reply_markup=build_analytics_keyboard(), parse_mode="HTML")
    await query.answer()


@analytics_router.callback_query(F.data == "admin_analytics_buttons")
async def cb_analytics_buttons(query: CallbackQuery):
    """Renders tabular button click analytics."""
    summary = await db.get_metrics_summary()
    top_buttons = summary.get("top_buttons", [])
    total_clicks = summary.get("total_button_clicks", 0)

    table_text = format_button_clicks_table(top_buttons)
    text = (
        "🖱️ <b>Button Click Telemetry Table</b>\n"
        "───────────────────────────────\n"
        f"{table_text}\n\n"
        f"📈 <b>Total Clicks:</b> <code>{total_clicks}</code> | "
        f"🎯 <b>Unique Buttons:</b> <code>{len(top_buttons)}</code>"
    )
    await query.message.edit_text(
        text,
        reply_markup=build_analytics_subview_keyboard("admin_analytics_buttons"),
        parse_mode="HTML",
    )
    await query.answer()


@analytics_router.callback_query(F.data == "admin_analytics_commands")
async def cb_analytics_commands(query: CallbackQuery):
    """Renders tabular bot command analytics."""
    summary = await db.get_metrics_summary()
    top_commands = summary.get("top_commands", [])
    total_commands = summary.get("total_commands", 0)

    table_text = format_commands_table(top_commands)
    text = (
        "💬 <b>Command Execution Telemetry Table</b>\n"
        "───────────────────────────────\n"
        f"{table_text}\n\n"
        f"📈 <b>Total Commands:</b> <code>{total_commands}</code> | "
        f"🎯 <b>Unique Commands:</b> <code>{len(top_commands)}</code>"
    )
    await query.message.edit_text(
        text,
        reply_markup=build_analytics_subview_keyboard("admin_analytics_commands"),
        parse_mode="HTML",
    )
    await query.answer()


@analytics_router.callback_query(F.data == "admin_analytics_bots")
async def cb_analytics_bots(query: CallbackQuery):
    """Renders multi-bot breakdown table."""
    summary = await db.get_metrics_summary()
    bots_breakdown = summary.get("bots_breakdown", [])

    table_text = format_bots_breakdown_table(bots_breakdown)
    text = (
        "🤖 <b>Multi-Bot Platform Telemetry Table</b>\n"
        "───────────────────────────────\n"
        f"{table_text}\n\n"
        f"🤖 <b>Active Bots Tracked:</b> <code>{len(bots_breakdown)}</code>"
    )
    await query.message.edit_text(
        text,
        reply_markup=build_analytics_subview_keyboard("admin_analytics_bots"),
        parse_mode="HTML",
    )
    await query.answer()


@analytics_router.callback_query(F.data == "admin_analytics_generations")
async def cb_analytics_generations(query: CallbackQuery):
    """Renders AI generation and model telemetry table."""
    summary = await db.get_metrics_summary()
    models_breakdown = summary.get("models_breakdown", [])
    top_presets = summary.get("top_presets", [])
    total_gens = summary.get("total_generations", 0)
    succ_gens = summary.get("successful_generations", 0)
    succ_rate = (succ_gens / total_gens * 100) if total_gens > 0 else 100.0

    table_text = format_models_table(models_breakdown)
    text = (
        "🎨 <b>AI Generations & Models Telemetry</b>\n"
        "───────────────────────────────\n"
        f"{table_text}\n\n"
        f"📈 <b>Total Generations:</b> <code>{total_gens}</code>\n"
        f"✅ <b>Success Rate:</b> <code>{succ_rate:.1f}%</code> (<code>{succ_gens}</code> OK)\n"
    )

    if top_presets:
        text += "\n🔥 <b>Preset Popularity:</b>\n"
        for name, count in top_presets[:5]:
            text += f"• <code>{name}</code>: {count} gen(s)\n"

    await query.message.edit_text(
        text,
        reply_markup=build_analytics_subview_keyboard("admin_analytics_generations"),
        parse_mode="HTML",
    )
    await query.answer()


@analytics_router.callback_query(F.data == "admin_analytics_messages")
async def cb_analytics_messages(query: CallbackQuery):
    """Renders outgoing bot messages breakdown table."""
    summary = await db.get_metrics_summary()
    messages_breakdown = summary.get("messages_breakdown", [])
    total_messages = summary.get("total_messages_sent", 0)

    table_text = format_messages_table(messages_breakdown)
    text = (
        "📤 <b>Outgoing Messages Telemetry Table</b>\n"
        "───────────────────────────────\n"
        f"{table_text}\n\n"
        f"📈 <b>Total Messages Sent:</b> <code>{total_messages}</code>"
    )
    await query.message.edit_text(
        text,
        reply_markup=build_analytics_subview_keyboard("admin_analytics_messages"),
        parse_mode="HTML",
    )
    await query.answer()


@analytics_router.callback_query(F.data == "admin_analytics_errors")
async def cb_analytics_errors(query: CallbackQuery):
    """Renders platform errors breakdown table."""
    summary = await db.get_metrics_summary()
    errors_breakdown = summary.get("errors_breakdown", [])
    total_errors = summary.get("total_errors", 0)

    table_text = format_errors_table(errors_breakdown)
    text = (
        "🚨 <b>Application Errors & Platform Health</b>\n"
        "───────────────────────────────\n"
        f"{table_text}\n\n"
        f"⚠️ <b>Total Error Events:</b> <code>{total_errors}</code>"
    )
    await query.message.edit_text(
        text,
        reply_markup=build_analytics_subview_keyboard("admin_analytics_errors"),
        parse_mode="HTML",
    )
    await query.answer()


@analytics_router.callback_query(F.data == "admin_analytics_live")
async def cb_analytics_live(query: CallbackQuery):
    """Renders recent real-time event stream buffer."""
    summary = await db.get_metrics_summary()
    recent_events = summary.get("recent_events", [])

    table_text = format_live_events_table(recent_events)
    text = (
        "⚡ <b>Real-Time Event Stream Feed (Last 12 Events)</b>\n"
        "───────────────────────────────\n"
        f"{table_text}\n\n"
        f"ℹ️ <i>Showing the most recent platform telemetry occurrences in chronological order.</i>"
    )
    await query.message.edit_text(
        text,
        reply_markup=build_analytics_subview_keyboard("admin_analytics_live"),
        parse_mode="HTML",
    )
    await query.answer()
