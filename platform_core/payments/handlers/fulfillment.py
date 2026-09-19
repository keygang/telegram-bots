from aiogram import F, Router
from aiogram.types import Message

from platform_core.db.supabase_client import db
from platform_core.events import (
    MessageSentEvent,
    PaymentEvent,
    get_tracker,
)
from platform_core.payments.packages import get_package_by_id

fulfillment_router = Router(name="fulfillment_router")


@fulfillment_router.message(F.successful_payment)
async def process_successful_payment(message: Message, bot_id: str = "default_bot"):
    """
    Fulfills user credit top-up after Telegram Stars payment verification.
    """
    payment = message.successful_payment
    charge_id = payment.telegram_payment_charge_id
    user_id = message.from_user.id

    # Check if transaction was already processed to prevent duplicate fulfillment & event tracking
    existing_tx = await db.get_star_transaction(charge_id)
    if existing_tx:
        balance = await db.get_user_balance(user_id)
        await message.answer(
            f"ℹ️ **Payment Already Processed**\n\n"
            f"This payment has already been credited to your account.\n"
            f"💳 **Total Balance**: {balance.credits_remaining} Credits"
        )
        return

    payload = payment.invoice_payload
    package_id = payload.replace("pkg:", "")
    package = get_package_by_id(package_id)

    credits_to_add = package.credits_count if package else payment.total_amount
    stars_paid = payment.total_amount

    balance = await db.add_user_credits(
        user_id=user_id,
        bot_id=bot_id,
        stars_paid=stars_paid,
        credits_to_add=credits_to_add,
        telegram_charge_id=charge_id,
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


__all__ = ["fulfillment_router", "process_successful_payment"]
