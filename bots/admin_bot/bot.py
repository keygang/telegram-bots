import logging
from typing import Any, Callable, Dict, Awaitable, List, Optional
import yaml

from aiogram import Bot, Dispatcher, Router, F, BaseMiddleware
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from platform_core.fsm_storage import get_fsm_storage
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    TelegramObject,
    User,
)

from platform_core.config import settings
from platform_core.presets import preset_manager, PromptPreset
from platform_core.db import db

logger = logging.getLogger(__name__)


class AddPresetStates(StatesGroup):
    id = State()
    title = State()
    prompt_template = State()
    category = State()
    icon = State()
    target_bot_id = State()


class AdminAuthMiddleware(BaseMiddleware):
    """Middleware enforcing admin Telegram user ID authorization."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        user: Optional[User] = data.get("event_from_user")
        admin_ids = settings.admin_user_ids

        # If admin_ids are configured, check user authorization
        if admin_ids and user:
            if user.id not in admin_ids:
                message_text = (
                    f"⛔ <b>Access Denied</b>\n\n"
                    f"Your Telegram ID (<code>{user.id}</code>) is not authorized to access the Admin Bot."
                )
                if isinstance(event, Message):
                    await event.answer(message_text, parse_mode="HTML")
                elif isinstance(event, CallbackQuery):
                    await event.answer("⛔ Access Denied. Admin privileges required.", show_alert=True)
                return

        return await handler(event, data)


admin_router = Router(name="admin_router")
admin_router.message.middleware(AdminAuthMiddleware())
admin_router.callback_query.middleware(AdminAuthMiddleware())


def build_main_admin_keyboard() -> InlineKeyboardMarkup:
    """Builds the main dashboard inline menu."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🎨 Manage Presets", callback_data="admin_presets_list"),
                InlineKeyboardButton(text="➕ Add Preset", callback_data="admin_preset_add"),
            ],
            [
                InlineKeyboardButton(text="🔄 Seed Default Presets", callback_data="admin_preset_seed"),
                InlineKeyboardButton(text="🤖 Bot Instances", callback_data="admin_instances_list"),
            ],
            [
                InlineKeyboardButton(text="📊 System Analytics", callback_data="admin_analytics"),
            ],
        ]
    )


@admin_router.message(Command("start", "admin", "menu"))
async def cmd_admin_menu(message: Message, state: FSMContext):
    """Renders the main Admin Control Dashboard."""
    await state.clear()
    text = (
        "👑 <b>Platform Admin Control Panel</b>\n"
        "───────────────────────────────\n"
        "Welcome! Configure all Telegram bot instances, manage NoSQL prompt presets, "
        "and inspect telemetry in real time.\n\n"
        "Select an option below to begin:"
    )
    await message.answer(text, reply_markup=build_main_admin_keyboard(), parse_mode="HTML")


@admin_router.callback_query(F.data == "admin_menu")
async def cb_admin_menu(query: CallbackQuery, state: FSMContext):
    """Returns to the main admin menu."""
    await state.clear()
    text = (
        "👑 <b>Platform Admin Control Panel</b>\n"
        "───────────────────────────────\n"
        "Welcome! Select an option below to manage NoSQL presets and bot instances:"
    )
    await query.message.edit_text(text, reply_markup=build_main_admin_keyboard(), parse_mode="HTML")
    await query.answer()


# --- PRESET MANAGEMENT HANDLERS ---

@admin_router.callback_query(F.data == "admin_presets_list")
async def cb_presets_list(query: CallbackQuery):
    """Lists all presets stored in Supabase NoSQL store."""
    presets = await preset_manager.fetch_presets(include_inactive=True, force_reload=True)

    if not presets:
        text = "🎨 <b>NoSQL Prompt Presets</b>\n\nNo presets found in the database store."
        buttons = [[InlineKeyboardButton(text="🔄 Seed Defaults", callback_data="admin_preset_seed")]]
    else:
        text = (
            f"🎨 <b>NoSQL Prompt Presets ({len(presets)} total)</b>\n"
            "───────────────────────────────\n"
            "Click on any preset below to view details, edit, toggle active status, or delete:"
        )
        buttons = []
        for p in presets:
            status_icon = "🟢" if p.is_active else "🔴"
            target = f"[{p.target_bot_id}]" if p.target_bot_id and p.target_bot_id != "all" else "[ALL]"
            btn_text = f"{status_icon} {p.icon} {p.title} {target}"
            buttons.append([InlineKeyboardButton(text=btn_text, callback_data=f"pdetail:{p.id}")])

    buttons.append([
        InlineKeyboardButton(text="➕ Add Preset", callback_data="admin_preset_add"),
        InlineKeyboardButton(text="⬅️ Main Menu", callback_data="admin_menu")
    ])

    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")
    await query.answer()


@admin_router.callback_query(F.data.startswith("pdetail:"))
async def cb_preset_detail(query: CallbackQuery):
    """Displays detailed inspection card for a specific preset."""
    preset_id = query.data.split(":", 1)[1]
    preset = await preset_manager.get_preset_by_id(preset_id)

    if not preset:
        await query.answer("❌ Preset not found.", show_alert=True)
        return

    status_str = "🟢 Active" if preset.is_active else "🔴 Disabled"
    toggle_target = "false" if preset.is_active else "true"
    toggle_label = "🔴 Disable Preset" if preset.is_active else "🟢 Enable Preset"

    text = (
        f"🎨 <b>Preset Details: {preset.title}</b>\n"
        "───────────────────────────────\n"
        f"<b>ID:</b> <code>{preset.id}</code>\n"
        f"<b>Status:</b> {status_str}\n"
        f"<b>Category:</b> {preset.category}\n"
        f"<b>Icon:</b> {preset.icon}\n"
        f"<b>Target Bot:</b> <code>{preset.target_bot_id or 'all'}</code>\n"
        f"<b>Media Type:</b> {preset.media_type}\n"
        f"<b>Model:</b> <code>{preset.default_model}</code>\n"
        f"<b>Description:</b> {preset.description}\n\n"
        f"<b>Prompt Template:</b>\n<code>{preset.prompt_template}</code>\n"
    )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=toggle_label, callback_data=f"ptoggle:{preset.id}:{toggle_target}"),
                InlineKeyboardButton(text="🗑️ Delete", callback_data=f"pdel_confirm:{preset.id}"),
            ],
            [
                InlineKeyboardButton(text="📋 Back to Presets", callback_data="admin_presets_list"),
                InlineKeyboardButton(text="⬅️ Main Menu", callback_data="admin_menu"),
            ],
        ]
    )

    await query.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await query.answer()


@admin_router.callback_query(F.data.startswith("ptoggle:"))
async def cb_preset_toggle(query: CallbackQuery):
    """Toggles active status of a preset."""
    parts = query.data.split(":")
    preset_id = parts[1]
    new_state = parts[2].lower() == "true"

    updated = await preset_manager.toggle_preset_active(preset_id, new_state)
    if updated:
        status_msg = "enabled" if new_state else "disabled"
        await query.answer(f"✅ Preset '{preset_id}' {status_msg}!", show_alert=True)
    else:
        await query.answer("❌ Failed to update preset state.", show_alert=True)

    await cb_preset_detail(query)


@admin_router.callback_query(F.data.startswith("pdel_confirm:"))
async def cb_preset_del_confirm(query: CallbackQuery):
    """Prompts for confirmation before deleting a preset."""
    preset_id = query.data.split(":", 1)[1]
    text = (
        f"⚠️ <b>Delete Preset Confirmation</b>\n\n"
        f"Are you sure you want to permanently delete preset <code>{preset_id}</code> from the NoSQL database?"
    )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Yes, Delete", callback_data=f"pdel_do:{preset_id}"),
                InlineKeyboardButton(text="❌ Cancel", callback_data=f"pdetail:{preset_id}"),
            ]
        ]
    )
    await query.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await query.answer()


@admin_router.callback_query(F.data.startswith("pdel_do:"))
async def cb_preset_del_do(query: CallbackQuery):
    """Deletes the specified preset."""
    preset_id = query.data.split(":", 1)[1]
    success = await preset_manager.delete_preset(preset_id)
    if success:
        await query.answer(f"✅ Preset '{preset_id}' deleted successfully.", show_alert=True)
    else:
        await query.answer("❌ Error deleting preset.", show_alert=True)

    await cb_presets_list(query)


@admin_router.callback_query(F.data == "admin_preset_seed")
async def cb_preset_seed(query: CallbackQuery):
    """Seeds default built-in presets into Supabase NoSQL DB."""
    count = await preset_manager.sync_defaults_to_supabase()
    await query.answer(f"✅ Seeded {count} default presets into NoSQL store!", show_alert=True)
    await cb_presets_list(query)


# --- FSM WIZARD FOR CREATING NEW PRESET ---

@admin_router.callback_query(F.data == "admin_preset_add")
async def cb_start_add_preset(query: CallbackQuery, state: FSMContext):
    """Initiates FSM wizard to add a new custom preset."""
    await state.set_state(AddPresetStates.id)
    text = (
        "➕ <b>Add New Prompt Preset (Step 1/6)</b>\n"
        "───────────────────────────────\n"
        "Enter a unique <b>Preset ID</b> (slug format, e.g. <code>cyberpunk_neon</code>):"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Cancel", callback_data="admin_presets_list")]])
    await query.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await query.answer()


@admin_router.message(AddPresetStates.id)
async def process_preset_id(message: Message, state: FSMContext):
    preset_id = message.text.strip().lower().replace(" ", "_")
    await state.update_data(id=preset_id)
    await state.set_state(AddPresetStates.title)
    text = f"✅ Preset ID set to <code>{preset_id}</code>.\n\n<b>Step 2/6:</b> Enter the display <b>Title</b> (e.g. <i>Cyberpunk Neon City</i>):"
    await message.answer(text, parse_mode="HTML")


@admin_router.message(AddPresetStates.title)
async def process_preset_title(message: Message, state: FSMContext):
    title = message.text.strip()
    await state.update_data(title=title)
    await state.set_state(AddPresetStates.prompt_template)
    text = (
        f"✅ Title set to <b>{title}</b>.\n\n"
        "<b>Step 3/6:</b> Enter the <b>Prompt Template</b>.\n"
        "Include <code>{user_prompt}</code> placeholder where user prompt text will be injected:\n"
        "<i>Example: Cyberpunk futuristic city with glowing neon signs, {user_prompt}, 8k resolution</i>"
    )
    await message.answer(text, parse_mode="HTML")


@admin_router.message(AddPresetStates.prompt_template)
async def process_preset_template(message: Message, state: FSMContext):
    template = message.text.strip()
    await state.update_data(prompt_template=template)
    await state.set_state(AddPresetStates.category)
    text = "✅ Prompt template recorded.\n\n<b>Step 4/6:</b> Enter a <b>Category</b> (e.g. <code>Sci-Fi</code>, <code>Anime</code>, <code>Popular</code>):"
    await message.answer(text, parse_mode="HTML")


@admin_router.message(AddPresetStates.category)
async def process_preset_category(message: Message, state: FSMContext):
    category = message.text.strip()
    await state.update_data(category=category)
    await state.set_state(AddPresetStates.icon)
    text = "✅ Category set.\n\n<b>Step 5/6:</b> Enter an emoji <b>Icon</b> (e.g. 🤖, 🎨, 🌆):"
    await message.answer(text, parse_mode="HTML")


@admin_router.message(AddPresetStates.icon)
async def process_preset_icon(message: Message, state: FSMContext):
    icon = message.text.strip() or "🎨"
    await state.update_data(icon=icon)
    await state.set_state(AddPresetStates.target_bot_id)
    text = (
        "✅ Icon recorded.\n\n"
        "<b>Step 6/6:</b> Enter <b>Target Bot ID</b> (e.g. <code>image_bot_1</code>, or <code>all</code> for all bots):"
    )
    await message.answer(text, parse_mode="HTML")


@admin_router.message(AddPresetStates.target_bot_id)
async def process_preset_target_bot(message: Message, state: FSMContext):
    target_bot = message.text.strip().lower() or "all"
    data = await state.get_data()
    await state.clear()

    new_preset = PromptPreset(
        id=data["id"],
        title=data["title"],
        description=f"Custom preset: {data['title']}",
        icon=data["icon"],
        prompt_template=data["prompt_template"],
        category=data["category"],
        target_bot_id=target_bot,
        is_active=True,
    )

    saved = await preset_manager.save_preset(new_preset)
    text = (
        f"🎉 <b>Preset Created Successfully!</b>\n\n"
        f"Preset <b>{saved.title}</b> (<code>{saved.id}</code>) has been saved into the Supabase NoSQL database."
    )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎨 View Presets", callback_data="admin_presets_list")],
            [InlineKeyboardButton(text="⬅️ Main Menu", callback_data="admin_menu")],
        ]
    )
    await message.answer(text, reply_markup=kb, parse_mode="HTML")


# --- BOT INSTANCES & ANALYTICS ---

@admin_router.callback_query(F.data == "admin_instances_list")
async def cb_instances_list(query: CallbackQuery):
    """Lists all configured bot instances from instances/ directory."""
    from platform_core.cli import get_instance_config_files

    configs = get_instance_config_files()
    text = f"🤖 <b>Configured Bot Instances ({len(configs)} found)</b>\n───────────────────────────────\n"

    for cfg_path in configs:
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                cfg_data = yaml.safe_load(f) or {}
            b_id = cfg_data.get("bot_id", cfg_path.stem)
            modules = [m.get("name") for m in cfg_data.get("modules", []) if isinstance(m, dict) and m.get("enabled", True)]
            text += (
                f"• <b>Bot ID:</b> <code>{b_id}</code>\n"
                f"  <b>Config File:</b> <code>{cfg_path.name}</code>\n"
                f"  <b>Active Modules:</b> {', '.join(modules) if modules else 'None'}\n\n"
            )
        except Exception as e:
            text += f"• ❌ Error reading <code>{cfg_path.name}</code>: {e}\n\n"

    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Main Menu", callback_data="admin_menu")]])
    await query.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await query.answer()


@admin_router.message(Command("stats", "analytics"))
async def cmd_admin_stats(message: Message):
    """Displays platform metrics and telemetry summary for admins."""
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
        f"💬 <b>Commands Executed:</b> <code>{metrics['total_commands']}</code>\n"
        f"🖱️ <b>Button Clicks:</b> <code>{metrics['total_button_clicks']}</code>\n"
        f"🎨 <b>AI Generations:</b> <code>{metrics['total_generations']}</code> "
        f"(<code>{metrics['successful_generations']}</code> Succeeded)\n"
        f"⭐️ <b>Total Stars Earned:</b> <code>{metrics['total_stars_earned']}</code> Stars (XTR)\n"
        f"⏳ <b>Pending Queue Tasks:</b> <code>{q_len}</code>\n"
        f"💳 <b>Monetization:</b> Active (Telegram Stars XTR)\n"
    )

    if metrics.get("top_presets"):
        text += "\n🔥 <b>Top Used Presets:</b>\n"
        for preset_name, count in metrics["top_presets"]:
            text += f"• <code>{preset_name}</code>: {count} use(s)\n"

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🔄 Refresh", callback_data="admin_analytics"),
                InlineKeyboardButton(text="⬅️ Main Menu", callback_data="admin_menu"),
            ]
        ]
    )
    await message.answer(text, reply_markup=kb, parse_mode="HTML")


@admin_router.callback_query(F.data == "admin_analytics")
async def cb_analytics(query: CallbackQuery):
    """Displays platform metrics, DB telemetry summary, and queue status."""
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
        f"💬 <b>Commands Executed:</b> <code>{metrics['total_commands']}</code>\n"
        f"🖱️ <b>Button Clicks:</b> <code>{metrics['total_button_clicks']}</code>\n"
        f"🎨 <b>AI Generations:</b> <code>{metrics['total_generations']}</code> "
        f"(<code>{metrics['successful_generations']}</code> Succeeded)\n"
        f"⭐️ <b>Total Stars Earned:</b> <code>{metrics['total_stars_earned']}</code> Stars (XTR)\n"
        f"⏳ <b>Pending Queue Tasks:</b> <code>{q_len}</code>\n"
        f"💳 <b>Monetization:</b> Active (Telegram Stars XTR)\n"
    )

    if metrics.get("top_presets"):
        text += "\n🔥 <b>Top Used Presets:</b>\n"
        for preset_name, count in metrics["top_presets"]:
            text += f"• <code>{preset_name}</code>: {count} use(s)\n"

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🔄 Refresh", callback_data="admin_analytics"),
                InlineKeyboardButton(text="⬅️ Main Menu", callback_data="admin_menu"),
            ]
        ]
    )
    await query.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await query.answer()


async def run_admin_bot(bot_token: Optional[str] = None):
    """Launches the Admin Telegram Bot polling loop."""
    token = bot_token or settings.ADMIN_BOT_TOKEN
    logger.info("👑 Starting Admin Telegram Bot...")

    bot = Bot(token=token)
    dp = Dispatcher(storage=get_fsm_storage(key_prefix="fsm:admin_bot"))
    dp.include_router(admin_router)

    await dp.start_polling(bot)
