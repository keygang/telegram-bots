import logging

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, LabeledPrice, Message, PreCheckoutQuery

from platform_core.db.supabase_client import db
from platform_core.events import (
    ButtonClickEvent,
    MessageSentEvent,
    PaymentEvent,
    get_tracker,
)
from platform_core.payments.packages import StarPackage, get_package_by_id

logger = logging.getLogger(__name__)
payments_router = Router(name="payments_router")


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


@payments_router.callback_query(F.data.startswith("buy_stars:"))
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


@payments_router.pre_checkout_query()
async def process_pre_checkout(pre_checkout_query: PreCheckoutQuery):
    """
    Pre-checkout query handler to confirm payment availability.
    """
    logger.info(
        f"Received PreCheckoutQuery ID: {pre_checkout_query.id} for payload: {pre_checkout_query.invoice_payload}"
    )
    await pre_checkout_query.answer(ok=True)


@payments_router.message(F.successful_payment)
async def process_successful_payment(message: Message, bot_id: str = "default_bot"):
    """
    Fulfills user credit top-up after Telegram Stars payment verification.
    """
    payment = message.successful_payment
    payload = payment.invoice_payload
    package_id = payload.replace("pkg:", "")
    package = get_package_by_id(package_id)

    credits_to_add = package.credits_count if package else payment.total_amount
    user_id = message.from_user.id
    stars_paid = payment.total_amount

    balance = await db.add_user_credits(
        user_id=user_id,
        bot_id=bot_id,
        stars_paid=stars_paid,
        credits_to_add=credits_to_add,
        telegram_charge_id=payment.telegram_payment_charge_id,
    )

    tracker = get_tracker(bot_id)
    await tracker.track(
        PaymentEvent(
            distinct_id=user_id,
            bot_id=bot_id,
            stars_amount=stars_paid,
            credits_added=credits_to_add,
            charge_id=payment.telegram_payment_charge_id,
            provider_charge_id=payment.provider_payment_charge_id,
            invoice_payload=payload,
        )
    )

    confirm_text = (
        f"🎉 **Payment Successful!**\n\n"
        f"Thank you for purchasing **{stars_paid} Telegram Stars**!\n"
        f"➕ **+{credits_to_add} Credits** added to your account.\n"
        f"💳 **Total Balance**: {balance.credits_remaining} Credits\n\n"
        f"Start generating now by sending a prompt or photo!"
    )
    await message.answer(confirm_text)
    await tracker.track(
        MessageSentEvent(
            distinct_id=user_id,
            bot_id=bot_id,
            message_type="text",
            text_length=len(confirm_text),
        )
    )
