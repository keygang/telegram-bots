from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bots.admin_bot.keyboards import build_main_admin_keyboard

menu_router = Router(name="admin_menu_router")


@menu_router.message(Command("start", "admin", "menu"))
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


@menu_router.callback_query(F.data == "admin_menu")
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
