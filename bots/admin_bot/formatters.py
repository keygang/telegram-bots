from typing import Any

from platform_core.db import (
    BotBreakdownMetric,
    ButtonClickMetric,
    CommandMetric,
    ErrorBreakdownMetric,
    MessageBreakdownMetric,
    ModelBreakdownMetric,
    RecentEventMetric,
    db,
)


def format_button_clicks_table(
    buttons: list[ButtonClickMetric] | list[dict[str, Any]],
) -> str:
    """Formats ranked button click hits into an aligned monospaced table."""
    if not buttons:
        return "<i>No button clicks recorded yet.</i>"

    lines = [
        " #  Action                   Clicks  Users",
        "──────────────────────────────────────────",
    ]
    for idx, btn in enumerate(buttons[:15], start=1):
        name = btn.get("name", "unknown")
        if len(name) > 22:
            name = name[:20] + ".."
        clicks = str(btn.get("count", 0))
        users = str(btn.get("unique_users", 0))
        lines.append(f"{idx:<2}  {name:<24} {clicks:>6} {users:>6}")
    return "<pre>" + "\n".join(lines) + "</pre>"


def format_commands_table(
    commands: list[CommandMetric] | list[dict[str, Any]],
) -> str:
    """Formats ranked bot commands into an aligned monospaced table."""
    if not commands:
        return "<i>No commands recorded yet.</i>"

    lines = [
        " #  Command                  Runs   Users",
        "──────────────────────────────────────────",
    ]
    for idx, cmd in enumerate(commands[:15], start=1):
        name = cmd.get("name", "unknown")
        if len(name) > 22:
            name = name[:20] + ".."
        runs = str(cmd.get("count", 0))
        users = str(cmd.get("unique_users", 0))
        lines.append(f"{idx:<2}  {name:<24} {runs:>5} {users:>6}")
    return "<pre>" + "\n".join(lines) + "</pre>"


def format_bots_breakdown_table(
    bots: list[BotBreakdownMetric] | list[dict[str, Any]],
) -> str:
    """Formats cross-bot telemetry into an aligned monospaced table."""
    if not bots:
        return "<i>No bot activity recorded yet.</i>"

    lines = [
        "Bot ID         Users  Clicks   Cmds   Gens",
        "──────────────────────────────────────────",
    ]
    for b in bots:
        b_id = b.get("bot_id", "unknown")
        if len(b_id) > 13:
            b_id = b_id[:11] + ".."
        users = str(b.get("users", 0))
        clicks = str(b.get("clicks", 0))
        cmds = str(b.get("commands", 0))
        gens = str(b.get("generations", 0))
        lines.append(f"{b_id:<13}  {users:>5}  {clicks:>6}  {cmds:>5}  {gens:>5}")
    return "<pre>" + "\n".join(lines) + "</pre>"


def format_models_table(
    models: list[ModelBreakdownMetric] | list[dict[str, Any]],
) -> str:
    """Formats AI models usage and performance into an aligned monospaced table."""
    if not models:
        return "<i>No generation data recorded yet.</i>"

    lines = [
        "Model / Engine       Total   Succ   Avg(s)",
        "──────────────────────────────────────────",
    ]
    for m in models:
        m_name = m.get("model_name", "default")
        short_name = m_name.replace("google/", "").replace("black-forest-labs/", "")
        if len(short_name) > 19:
            short_name = short_name[:17] + ".."
        total = str(m.get("total", 0))
        succ = str(m.get("success", 0))
        avg_s = f"{m.get('avg_duration_ms', 0) / 1000.0:.1f}s"
        lines.append(f"{short_name:<19}  {total:>5}  {succ:>5}  {avg_s:>7}")
    return "<pre>" + "\n".join(lines) + "</pre>"


def format_messages_table(
    messages: list[MessageBreakdownMetric] | list[dict[str, Any]],
) -> str:
    """Formats bot outgoing messages by type into an aligned monospaced table."""
    if not messages:
        return "<i>No outgoing messages recorded yet.</i>"

    lines = [
        " #  Type                     Sent   Users",
        "──────────────────────────────────────────",
    ]
    for idx, msg in enumerate(messages[:15], start=1):
        m_type = msg.get("type", "text")
        if len(m_type) > 22:
            m_type = m_type[:20] + ".."
        count = str(msg.get("count", 0))
        users = str(msg.get("unique_users", 0))
        lines.append(f"{idx:<2}  {m_type:<24} {count:>5} {users:>6}")
    return "<pre>" + "\n".join(lines) + "</pre>"


def format_errors_table(
    errors: list[ErrorBreakdownMetric] | list[dict[str, Any]],
) -> str:
    """Formats platform errors breakdown into an aligned monospaced table."""
    if not errors:
        return "<i>🎉 No application errors recorded! All systems nominal.</i>"

    lines = [
        " #  Error Type               Count  Users",
        "──────────────────────────────────────────",
    ]
    for idx, err in enumerate(errors[:15], start=1):
        err_name = err.get("error_type", "Unknown")
        if len(err_name) > 22:
            err_name = err_name[:20] + ".."
        count = str(err.get("count", 0))
        users = str(err.get("unique_users", 0))
        lines.append(f"{idx:<2}  {err_name:<24} {count:>5} {users:>6}")
    return "<pre>" + "\n".join(lines) + "</pre>"


def format_live_events_table(
    events: list[RecentEventMetric] | list[dict[str, Any]],
) -> str:
    """Formats the latest real-time event feed into an aligned monospaced table."""
    if not events:
        return "<i>No real-time events in the live buffer.</i>"

    lines = ["Time     Bot          Event / Action", "──────────────────────────────────────────"]
    for evt in events[:12]:
        t_str = evt.get("created_at", "")
        b_id = evt.get("bot_id", "default")
        if len(b_id) > 11:
            b_id = b_id[:9] + ".."
        name = evt.get("event", "")
        if len(name) > 18:
            name = name[:16] + ".."
        lines.append(f"{t_str:<8} {b_id:<12} {name:<18}")
    return "<pre>" + "\n".join(lines) + "</pre>"


async def render_analytics_overview_text() -> str:
    """Generates the primary analytics summary text."""
    from platform_core.queue.broker import task_broker

    metrics = await db.get_metrics_summary()
    q_len = await task_broker.get_queue_length()
    user_count = metrics.get("total_users", len(db._in_memory_users))

    if db.client:
        try:
            res = db.client.table("users").select("telegram_id", count="exact").execute()
            if res.count is not None:
                user_count = res.count
        except Exception:
            pass

    text = (
        "📊 <b>Platform Analytics & System Status</b>\n"
        "───────────────────────────────\n"
        f"👥 <b>Total Users:</b> <code>{user_count}</code>\n"
        f"⚡ <b>Total Events / Hits:</b> <code>{metrics.get('total_events', 0)}</code>\n"
        f"💬 <b>Commands Executed:</b> <code>{metrics['total_commands']}</code>\n"
        f"🖱️ <b>Button Clicks:</b> <code>{metrics['total_button_clicks']}</code>\n"
        f"🎨 <b>AI Generations:</b> <code>{metrics['total_generations']}</code> "
        f"(<code>{metrics['successful_generations']}</code> Succeeded)\n"
        f"📤 <b>Messages Sent to Users:</b> <code>{metrics.get('total_messages_sent', 0)}</code>\n"
        f"🚨 <b>Application Errors:</b> <code>{metrics.get('total_errors', 0)}</code>\n"
        f"⭐️ <b>Total Stars Earned:</b> <code>{metrics['total_stars_earned']}</code> Stars (XTR)\n"
        f"⏳ <b>Pending Queue Tasks:</b> <code>{q_len}</code>\n"
        f"💳 <b>Monetization:</b> Active (Telegram Stars XTR)\n"
    )

    if metrics.get("top_presets"):
        text += "\n🔥 <b>Top Presets:</b>\n"
        for preset_name, count in metrics["top_presets"][:5]:
            text += f"• <code>{preset_name}</code>: {count} gen(s)\n"

    text += "\n<i>Tap below to view detailed breakdown tables:</i>"
    return text
