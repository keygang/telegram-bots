import pytest

from platform_core.db import db


@pytest.mark.asyncio
async def test_user_sync_and_balance():
    user_id = 999111222
    profile = await db.sync_user(telegram_id=user_id, username="test_hero", first_name="Test")
    assert profile.telegram_id == user_id
    assert profile.username == "test_hero"

    balance = await db.get_user_balance(user_id)
    initial_credits = balance.credits_remaining
    assert initial_credits >= 1

    # Test credit deduction
    success = await db.deduct_user_credit(user_id, amount=1)
    assert success is True

    new_balance = await db.get_user_balance(user_id)
    assert new_balance.credits_remaining == initial_credits - 1


@pytest.mark.asyncio
async def test_star_payment_credits():
    user_id = 888777666
    balance_before = await db.get_user_balance(user_id)
    initial_credits = balance_before.credits_remaining

    new_bal = await db.add_user_credits(
        user_id=user_id,
        bot_id="image_bot",
        stars_paid=25,
        credits_to_add=10,
        telegram_charge_id="ch_test_123",
    )

    assert new_bal.credits_remaining == initial_credits + 10
    assert new_bal.total_stars_spent == 25


@pytest.mark.asyncio
async def test_atomic_credit_deduction_concurrency():
    import asyncio

    user_id = 777111333
    balance = await db.get_user_balance(user_id)
    # Set known balance of 2 credits
    balance.credits_remaining = 2

    # Launch 5 concurrent deduction requests
    results = await asyncio.gather(
        db.deduct_user_credit(user_id, amount=1),
        db.deduct_user_credit(user_id, amount=1),
        db.deduct_user_credit(user_id, amount=1),
        db.deduct_user_credit(user_id, amount=1),
        db.deduct_user_credit(user_id, amount=1),
    )

    # Exactly 2 should succeed, 3 should fail
    success_count = sum(1 for r in results if r is True)
    failure_count = sum(1 for r in results if r is False)
    assert success_count == 2
    assert failure_count == 3

    final_balance = await db.get_user_balance(user_id)
    assert final_balance.credits_remaining == 0


@pytest.mark.asyncio
async def test_idempotent_star_payment_credits():
    user_id = 666222111
    balance_before = await db.get_user_balance(user_id)
    initial_credits = balance_before.credits_remaining
    initial_stars = balance_before.total_stars_spent

    charge_id = "ch_duplicate_test_unique_456"

    # First credit addition
    bal1 = await db.add_user_credits(
        user_id=user_id,
        bot_id="image_bot",
        stars_paid=50,
        credits_to_add=25,
        telegram_charge_id=charge_id,
    )
    assert bal1.credits_remaining == initial_credits + 25
    assert bal1.total_stars_spent == initial_stars + 50

    # Duplicate call with the same charge_id should NOT add credits or stars
    bal2 = await db.add_user_credits(
        user_id=user_id,
        bot_id="image_bot",
        stars_paid=50,
        credits_to_add=25,
        telegram_charge_id=charge_id,
    )
    assert bal2.credits_remaining == initial_credits + 25
    assert bal2.total_stars_spent == initial_stars + 50

    # Verify transaction lookup
    tx = await db.get_star_transaction(charge_id)
    assert tx is not None
    assert tx.telegram_payment_charge_id == charge_id
    assert tx.stars_amount == 50
    assert tx.credits_added == 25


@pytest.mark.asyncio
async def test_process_successful_payment_duplicate_safety():
    from unittest.mock import AsyncMock, MagicMock
    from datetime import datetime
    from aiogram.types import Chat, Message, SuccessfulPayment, User as TelegramUser
    from platform_core.payments.handlers.fulfillment import process_successful_payment

    user_id = 555444333
    user = TelegramUser(id=user_id, is_bot=False, first_name="Payer")
    chat = Chat(id=user_id, type="private")

    payment = SuccessfulPayment(
        currency="XTR",
        total_amount=10,
        invoice_payload="pkg:credits_starter",
        telegram_payment_charge_id="tx_tg_stars_unique_test_001",
        provider_payment_charge_id="",
    )

    msg = MagicMock(spec=Message)
    msg.message_id = 200
    msg.date = datetime.now()
    msg.chat = chat
    msg.from_user = user
    msg.successful_payment = payment
    msg.answer = AsyncMock()

    # Initial balance
    bal_initial = await db.get_user_balance(user_id)
    initial_credits = bal_initial.credits_remaining

    # First fulfillment call
    await process_successful_payment(msg, bot_id="test_bot")
    bal_after = await db.get_user_balance(user_id)
    assert bal_after.credits_remaining > initial_credits
    credits_after_first = bal_after.credits_remaining

    # Second duplicate fulfillment call with identical message / charge_id
    await process_successful_payment(msg, bot_id="test_bot")
    bal_duplicate = await db.get_user_balance(user_id)

    # Balance must remain exactly identical (no double-crediting!)
    assert bal_duplicate.credits_remaining == credits_after_first

