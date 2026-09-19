from aiogram import Bot
from aiogram.types import LabeledPrice, Message

from platform_core.events import MessageSentEvent, get_tracker
from platform_core.payments.packages import StarPackage


async def send_star_invoice(
    bot: Bot, chat_id: int, package: StarPackage, bot_id: str = "default_bot"
) -> Message:
    """
    Sends a native Telegram Stars invoice to the user.
    """
    prices = [LabeledPrice(label=package.title, amount=package.stars_amount)]
    msg = await bot.send_invoice(
        chat_id=chat_id,
        title=f"{package.icon} {package.title}",
        description=package.description,
        payload=f"pkg:{package.id}",
        currency="XTR",  # Telegram Stars Currency Code
        prices=prices,
        provider_token="",  # Blank required for Telegram Stars
    )
    tracker = get_tracker(bot_id)
    await tracker.track(
        MessageSentEvent(
            distinct_id=chat_id,
            bot_id=bot_id,
            message_type="invoice",
            has_reply_markup=True,
        )
    )
    return msg


__all__ = ["send_star_invoice"]
