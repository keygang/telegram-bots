import logging

from aiogram import Bot, Dispatcher, Router

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
from bots.admin_bot.handlers import (
    analytics_router,
    cb_admin_menu,
    cb_analytics,
    cb_analytics_bots,
    cb_analytics_buttons,
    cb_analytics_commands,
    cb_analytics_errors,
    cb_analytics_generations,
    cb_analytics_live,
    cb_analytics_messages,
    cb_instances_list,
    cb_preset_del_confirm,
    cb_preset_del_do,
    cb_preset_detail,
    cb_preset_seed,
    cb_preset_toggle,
    cb_presets_list,
    cb_start_add_preset,
    cmd_admin_menu,
    cmd_admin_stats,
    instances_router,
    menu_router,
    presets_router,
    process_preset_category,
    process_preset_icon,
    process_preset_id,
    process_preset_target_bot,
    process_preset_template,
    process_preset_title,
)
from bots.admin_bot.keyboards import (
    build_analytics_keyboard,
    build_analytics_subview_keyboard,
    build_main_admin_keyboard,
)
from bots.admin_bot.middlewares import AdminAuthMiddleware
from bots.admin_bot.states import AddPresetStates
from platform_core.config import settings
from platform_core.fsm_storage import get_fsm_storage

logger = logging.getLogger(__name__)

# Master admin router configured with auth middleware
admin_router = Router(name="admin_router")
admin_router.message.middleware(AdminAuthMiddleware())
admin_router.callback_query.middleware(AdminAuthMiddleware())

# Include modular sub-routers
admin_router.include_router(menu_router)
admin_router.include_router(presets_router)
admin_router.include_router(instances_router)
admin_router.include_router(analytics_router)


async def run_admin_bot(bot_token: str | None = None):
    """Launches the Admin Telegram Bot polling loop."""
    from platform_core.bot.middlewares import I18nMiddleware, UserSyncMiddleware

    token = bot_token or settings.ADMIN_BOT_TOKEN
    logger.info("👑 Starting Admin Telegram Bot...")

    bot = Bot(token=token)
    dp = Dispatcher(storage=get_fsm_storage(key_prefix="fsm:admin_bot"))

    # Register core middlewares (Admin bot acts as CRM - no metrics tracking)
    dp.update.outer_middleware(UserSyncMiddleware())
    dp.update.outer_middleware(I18nMiddleware())

    dp.include_router(admin_router)

    await dp.start_polling(bot)


__all__ = [
    "AddPresetStates",
    "AdminAuthMiddleware",
    "admin_router",
    "build_analytics_keyboard",
    "build_analytics_subview_keyboard",
    "build_main_admin_keyboard",
    "cb_admin_menu",
    "cb_analytics",
    "cb_analytics_bots",
    "cb_analytics_buttons",
    "cb_analytics_commands",
    "cb_analytics_errors",
    "cb_analytics_generations",
    "cb_analytics_live",
    "cb_analytics_messages",
    "cb_instances_list",
    "cb_preset_del_confirm",
    "cb_preset_del_do",
    "cb_preset_detail",
    "cb_preset_seed",
    "cb_preset_toggle",
    "cb_presets_list",
    "cb_start_add_preset",
    "cmd_admin_menu",
    "cmd_admin_stats",
    "format_bots_breakdown_table",
    "format_button_clicks_table",
    "format_commands_table",
    "format_errors_table",
    "format_live_events_table",
    "format_messages_table",
    "format_models_table",
    "process_preset_category",
    "process_preset_icon",
    "process_preset_id",
    "process_preset_target_bot",
    "process_preset_template",
    "process_preset_title",
    "render_analytics_overview_text",
    "run_admin_bot",
]
