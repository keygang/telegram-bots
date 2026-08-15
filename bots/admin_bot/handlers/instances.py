import yaml
from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

instances_router = Router(name="admin_instances_router")


@instances_router.callback_query(F.data == "admin_instances_list")
async def cb_instances_list(query: CallbackQuery):
    """Lists all configured bot instances from instances/ directory."""
    from platform_core.cli import get_instance_config_files

    configs = get_instance_config_files()
    text = f"🤖 <b>Configured Bot Instances ({len(configs)} found)</b>\n───────────────────────────────\n"

    for cfg_path in configs:
        try:
            with open(cfg_path, encoding="utf-8") as f:
                cfg_data = yaml.safe_load(f) or {}
            b_id = cfg_data.get("bot_id", cfg_path.stem)
            modules = [
                m.get("name")
                for m in cfg_data.get("modules", [])
                if isinstance(m, dict) and m.get("enabled", True)
            ]
            text += (
                f"• <b>Bot ID:</b> <code>{b_id}</code>\n"
                f"  <b>Config File:</b> <code>{cfg_path.name}</code>\n"
                f"  <b>Active Modules:</b> {', '.join(modules) if modules else 'None'}\n\n"
            )
        except Exception as e:
            text += f"• ❌ Error reading <code>{cfg_path.name}</code>: {e}\n\n"

    kb = InlineKeyboardMarkup(
        inline_keyboard=[[[InlineKeyboardButton(text="⬅️ Main Menu", callback_data="admin_menu")]]]
    )
    await query.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await query.answer()
