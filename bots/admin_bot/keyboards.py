from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def build_main_admin_keyboard() -> InlineKeyboardMarkup:
    """Builds the main dashboard inline menu."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🎨 Manage Presets", callback_data="admin_presets_list"),
                InlineKeyboardButton(text="➕ Add Preset", callback_data="admin_preset_add"),
            ],
            [
                InlineKeyboardButton(
                    text="🔄 Seed Default Presets", callback_data="admin_preset_seed"
                ),
                InlineKeyboardButton(text="🤖 Bot Instances", callback_data="admin_instances_list"),
            ],
            [
                InlineKeyboardButton(text="📊 System Analytics", callback_data="admin_analytics"),
            ],
        ]
    )


def build_analytics_keyboard() -> InlineKeyboardMarkup:
    """Builds navigation keyboard for analytics overview."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🖱️ Button Clicks", callback_data="admin_analytics_buttons"
                ),
                InlineKeyboardButton(text="💬 Commands", callback_data="admin_analytics_commands"),
            ],
            [
                InlineKeyboardButton(
                    text="🤖 Multi-Bot Stats", callback_data="admin_analytics_bots"
                ),
                InlineKeyboardButton(
                    text="🎨 Generations", callback_data="admin_analytics_generations"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📤 Messages Sent", callback_data="admin_analytics_messages"
                ),
                InlineKeyboardButton(
                    text="🚨 Errors & Health", callback_data="admin_analytics_errors"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="⚡ Live Event Feed", callback_data="admin_analytics_live"
                ),
            ],
            [
                InlineKeyboardButton(text="🔄 Refresh", callback_data="admin_analytics"),
                InlineKeyboardButton(text="⬅️ Main Menu", callback_data="admin_menu"),
            ],
        ]
    )


def build_analytics_subview_keyboard(refresh_callback: str) -> InlineKeyboardMarkup:
    """Builds navigation keyboard for analytics subviews."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🔄 Refresh", callback_data=refresh_callback),
                InlineKeyboardButton(text="📊 Overview", callback_data="admin_analytics"),
            ],
            [
                InlineKeyboardButton(text="⬅️ Main Menu", callback_data="admin_menu"),
            ],
        ]
    )
