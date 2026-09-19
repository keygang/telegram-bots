from collections.abc import Callable

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from platform_core.bot.handlers.common import _resolve_gettext
from platform_core.bot.keyboards import get_models_keyboard
from platform_core.db import UserProfile, db
from platform_core.generators import DEFAULT_AVAILABLE_MODELS

models_router = Router(name="models_router")


@models_router.message(Command("models"))
@models_router.callback_query(F.data == "models_menu")
async def handle_models_menu(
    event: Message | CallbackQuery,
    user_profile: UserProfile | None = None,
    _: Callable[..., str] | None = None,
) -> None:
    """Displays AI Model Selection menu with current active model checked."""
    gettext = _resolve_gettext(_)

    current_model = (
        user_profile and user_profile.selected_model
    ) or "google/gemini-2.5-flash-image"
    kb = get_models_keyboard(DEFAULT_AVAILABLE_MODELS, current_model, _=gettext)
    short_name = current_model.split("/")[-1]
    text = gettext("models_menu_title", current_model=short_name)

    if isinstance(event, CallbackQuery):
        await event.answer()
        await event.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    else:
        await event.answer(text, reply_markup=kb, parse_mode="Markdown")


@models_router.callback_query(F.data.startswith("set_model:"))
async def handle_set_model(
    callback: CallbackQuery,
    user_profile: UserProfile | None = None,
    _: Callable[..., str] | None = None,
) -> None:
    """Persists user model selection and refreshes the model menu."""
    gettext = _resolve_gettext(_)

    model_name = callback.data.split("set_model:")[1]
    user_id = callback.from_user.id

    # Persist user model selection
    await db.update_user_model(telegram_id=user_id, model_name=model_name)
    if user_profile:
        user_profile.selected_model = model_name

    short_name = model_name.split("/")[-1]
    alert_text = gettext("model_changed", model=short_name)
    await callback.answer(alert_text, show_alert=True)

    # Re-render models menu with new checkmark
    kb = get_models_keyboard(DEFAULT_AVAILABLE_MODELS, model_name, _=gettext)
    text = gettext("models_menu_title", current_model=short_name)
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
