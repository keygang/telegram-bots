from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery

from platform_core.events import ButtonClickEvent, get_tracker
from platform_core.payments.handlers.invoice import send_star_invoice
from platform_core.payments.packages import get_package_by_id

buy_router = Router(name="buy_router")


@buy_router.callback_query(F.data.startswith("buy_stars:"))
async def process_buy_stars_callback(
    callback: CallbackQuery, bot: Bot, bot_id: str = "default_bot"
):
    package_id = callback.data.split("buy_stars:")[1]
    tracker = get_tracker(bot_id)
    await tracker.track(
        ButtonClickEvent(
            distinct_id=callback.from_user.id,
            bot_id=bot_id,
            button_id=callback.data,
            menu="buy_stars",
        )
    )

    package = get_package_by_id(package_id)
    if not package:
        await callback.answer("Selected package not found.", show_alert=True)
        return

    await callback.answer()
    await send_star_invoice(bot, callback.message.chat.id, package, bot_id=bot_id)


__all__ = ["buy_router", "process_buy_stars_callback"]
