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
