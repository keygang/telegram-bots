from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from bots.admin_bot.states import AddPresetStates
from platform_core.presets import PromptPreset, preset_manager

presets_router = Router(name="admin_presets_router")


@presets_router.callback_query(F.data == "admin_presets_list")
async def cb_presets_list(query: CallbackQuery):
    """Lists all presets stored in Supabase NoSQL store."""
    presets = await preset_manager.fetch_presets(include_inactive=True, force_reload=True)

    if not presets:
        text = "🎨 <b>NoSQL Prompt Presets</b>\n\nNo presets found in the database store."
        buttons = [
            [InlineKeyboardButton(text="🔄 Seed Defaults", callback_data="admin_preset_seed")]
        ]
    else:
        text = (
            f"🎨 <b>NoSQL Prompt Presets ({len(presets)} total)</b>\n"
            "───────────────────────────────\n"
            "Click on any preset below to view details, edit, toggle active status, or delete:"
        )
        buttons = []
        for p in presets:
            status_icon = "🟢" if p.is_active else "🔴"
            target = (
                f"[{p.target_bot_id}]" if p.target_bot_id and p.target_bot_id != "all" else "[ALL]"
            )
            btn_text = f"{status_icon} {p.icon} {p.title} {target}"
            buttons.append([InlineKeyboardButton(text=btn_text, callback_data=f"pdetail:{p.id}")])

    buttons.append(
        [
            InlineKeyboardButton(text="➕ Add Preset", callback_data="admin_preset_add"),
            InlineKeyboardButton(text="⬅️ Main Menu", callback_data="admin_menu"),
        ]
    )

    await query.message.edit_text(
        text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML"
    )
    await query.answer()


@presets_router.callback_query(F.data.startswith("pdetail:"))
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
                InlineKeyboardButton(
                    text=toggle_label, callback_data=f"ptoggle:{preset.id}:{toggle_target}"
                ),
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


@presets_router.callback_query(F.data.startswith("ptoggle:"))
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


@presets_router.callback_query(F.data.startswith("pdel_confirm:"))
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


@presets_router.callback_query(F.data.startswith("pdel_do:"))
async def cb_preset_del_do(query: CallbackQuery):
    """Deletes the specified preset."""
    preset_id = query.data.split(":", 1)[1]
    success = await preset_manager.delete_preset(preset_id)
    if success:
        await query.answer(f"✅ Preset '{preset_id}' deleted successfully.", show_alert=True)
    else:
        await query.answer("❌ Error deleting preset.", show_alert=True)

    await cb_presets_list(query)


@presets_router.callback_query(F.data == "admin_preset_seed")
async def cb_preset_seed(query: CallbackQuery):
    """Seeds default built-in presets into Supabase NoSQL DB."""
    count = await preset_manager.sync_defaults_to_supabase()
    await query.answer(f"✅ Seeded {count} default presets into NoSQL store!", show_alert=True)
    await cb_presets_list(query)


@presets_router.callback_query(F.data == "admin_preset_add")
async def cb_start_add_preset(query: CallbackQuery, state: FSMContext):
    """Initiates FSM wizard to add a new custom preset."""
    await state.set_state(AddPresetStates.id)
    text = (
        "➕ <b>Add New Prompt Preset (Step 1/6)</b>\n"
        "───────────────────────────────\n"
        "Enter a unique <b>Preset ID</b> (slug format, e.g. <code>cyberpunk_neon</code>):"
    )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❌ Cancel", callback_data="admin_presets_list")]
        ]
    )
    await query.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await query.answer()


@presets_router.message(AddPresetStates.id)
async def process_preset_id(message: Message, state: FSMContext):
    preset_id = message.text.strip().lower().replace(" ", "_")
    await state.update_data(id=preset_id)
    await state.set_state(AddPresetStates.title)
    text = f"✅ Preset ID set to <code>{preset_id}</code>.\n\n<b>Step 2/6:</b> Enter the display <b>Title</b> (e.g. <i>Cyberpunk Neon City</i>):"
    await message.answer(text, parse_mode="HTML")


@presets_router.message(AddPresetStates.title)
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


@presets_router.message(AddPresetStates.prompt_template)
async def process_preset_template(message: Message, state: FSMContext):
    template = message.text.strip()
    await state.update_data(prompt_template=template)
    await state.set_state(AddPresetStates.category)
    text = "✅ Prompt template recorded.\n\n<b>Step 4/6:</b> Enter a <b>Category</b> (e.g. <code>Sci-Fi</code>, <code>Anime</code>, <code>Popular</code>):"
    await message.answer(text, parse_mode="HTML")


@presets_router.message(AddPresetStates.category)
async def process_preset_category(message: Message, state: FSMContext):
    category = message.text.strip()
    await state.update_data(category=category)
    await state.set_state(AddPresetStates.icon)
    text = "✅ Category set.\n\n<b>Step 5/6:</b> Enter an emoji <b>Icon</b> (e.g. 🤖, 🎨, 🌆):"
    await message.answer(text, parse_mode="HTML")


@presets_router.message(AddPresetStates.icon)
async def process_preset_icon(message: Message, state: FSMContext):
    icon = message.text.strip() or "🎨"
    await state.update_data(icon=icon)
    await state.set_state(AddPresetStates.target_bot_id)
    text = (
        "✅ Icon recorded.\n\n"
        "<b>Step 6/6:</b> Enter <b>Target Bot ID</b> (e.g. <code>image_bot_1</code>, or <code>all</code> for all bots):"
    )
    await message.answer(text, parse_mode="HTML")


@presets_router.message(AddPresetStates.target_bot_id)
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
