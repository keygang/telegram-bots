import logging
from aiogram import Router, F, Bot
from aiogram.types import Message, PreCheckoutQuery, LabeledPrice, CallbackQuery
from platform_core.db import db, BotEvent
from platform_core.payments.packages import StarPackage, get_package_by_id

logger = logging.getLogger(__name__)
payments_router = Router(name="payments_router")


async def send_star_invoice(bot: Bot, chat_id: int, package: StarPackage) -> Message:
    """
    Sends a native Telegram Stars invoice to the user.
    """
    prices = [LabeledPrice(label=package.title, amount=package.stars_amount)]
    return await bot.send_invoice(
        chat_id=chat_id,
        title=f"{package.icon} {package.title}",
        description=package.description,
        payload=f"pkg:{package.id}",
        currency="XTR",  # Telegram Stars Currency Code
        prices=prices,
        provider_token="",  # Blank required for Telegram Stars
    )


@payments_router.callback_query(F.data.startswith("buy_stars:"))
async def process_buy_stars_callback(callback: CallbackQuery, bot: Bot):
    package_id = callback.data.split("buy_stars:")[1]
    package = get_package_by_id(package_id)
    if not package:
        await callback.answer("Selected package not found.", show_alert=True)
        return

    await callback.answer()
    await send_star_invoice(bot, callback.message.chat.id, package)


@payments_router.pre_checkout_query()
async def process_pre_checkout(pre_checkout_query: PreCheckoutQuery):
    """
    Pre-checkout query handler to confirm payment availability.
    """
    logger.info(f"Received PreCheckoutQuery ID: {pre_checkout_query.id} for payload: {pre_checkout_query.invoice_payload}")
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
        telegram_charge_id=payment.telegram_payment_charge_id
    )

    await db.record_event(
        BotEvent(
            bot_id=bot_id,
            user_id=user_id,
            event_type="payment",
            event_name=f"stars_payment:{stars_paid}",
            metadata={"stars": stars_paid, "credits_added": credits_to_add, "charge_id": payment.telegram_payment_charge_id}
        )
    )

    await message.answer(
        f"🎉 **Payment Successful!**\n\n"
        f"Thank you for purchasing **{stars_paid} Telegram Stars**!\n"
        f"➕ **+{credits_to_add} Credits** added to your account.\n"
        f"💳 **Total Balance**: {balance.credits_remaining} Credits\n\n"
        f"Start generating now by sending a prompt or photo!"
    )
