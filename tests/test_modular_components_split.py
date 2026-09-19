from aiogram import BaseMiddleware, Router
from aiogram.fsm.state import StatesGroup
from pydantic import BaseModel

from platform_core.bot import (
    CreditCheckMiddleware,
    GenerationStateData,
    GenerationStates,
    I18nMiddleware,
    UserSyncMiddleware,
)
from platform_core.bot.middlewares import (
    CreditCheckMiddleware as PkgCreditCheck,
)
from platform_core.bot.middlewares import (
    I18nMiddleware as PkgI18n,
)
from platform_core.bot.middlewares import (
    UserSyncMiddleware as PkgUserSync,
)
from platform_core.bot.middlewares import (
    _get_user_from_event,
)
from platform_core.bot.middlewares.credit_check import (
    CreditCheckMiddleware as ModCreditCheck,
)
from platform_core.bot.middlewares.i18n import (
    I18nMiddleware as ModI18n,
)
from platform_core.bot.middlewares.user_sync import (
    UserSyncMiddleware as ModUserSync,
)
from platform_core.bot.states import (
    GenerationStateData as PkgStateData,
)
from platform_core.bot.states import (
    GenerationStates as PkgStates,
)
from platform_core.bot.states.data import (
    GenerationStateData as ModStateData,
)
from platform_core.bot.states.generation import (
    GenerationStates as ModStates,
)
from platform_core.payments.handlers import (
    buy_router,
    fulfillment_router,
    payments_router,
    pre_checkout_router,
    process_buy_stars_callback,
    process_pre_checkout,
    process_successful_payment,
    send_star_invoice,
)
from platform_core.payments.handlers.buy import (
    buy_router as mod_buy_router,
)
from platform_core.payments.handlers.buy import (
    process_buy_stars_callback as mod_process_buy_stars_callback,
)
from platform_core.payments.handlers.fulfillment import (
    fulfillment_router as mod_fulfillment_router,
)
from platform_core.payments.handlers.fulfillment import (
    process_successful_payment as mod_process_successful_payment,
)
from platform_core.payments.handlers.invoice import (
    send_star_invoice as mod_send_star_invoice,
)
from platform_core.payments.handlers.pre_checkout import (
    pre_checkout_router as mod_pre_checkout_router,
)
from platform_core.payments.handlers.pre_checkout import (
    process_pre_checkout as mod_process_pre_checkout,
)


def test_middlewares_split_and_exports():
    """Verify that all middlewares are exported and identity matches dedicated modules."""
    assert issubclass(CreditCheckMiddleware, BaseMiddleware)
    assert issubclass(I18nMiddleware, BaseMiddleware)
    assert issubclass(UserSyncMiddleware, BaseMiddleware)

    assert CreditCheckMiddleware is PkgCreditCheck is ModCreditCheck
    assert I18nMiddleware is PkgI18n is ModI18n
    assert UserSyncMiddleware is PkgUserSync is ModUserSync
    assert callable(_get_user_from_event)


def test_states_split_and_exports():
    """Verify that all FSM states and schemas are exported and identity matches dedicated modules."""
    assert issubclass(GenerationStates, StatesGroup)
    assert issubclass(GenerationStateData, BaseModel)

    assert GenerationStates is PkgStates is ModStates
    assert GenerationStateData is PkgStateData is ModStateData

    # Verify State definitions
    assert hasattr(GenerationStates, "selecting_preset")
    assert hasattr(GenerationStates, "waiting_for_photo")
    assert hasattr(GenerationStates, "entering_custom_prompt")
    assert hasattr(GenerationStates, "generating")

    # Verify State Data dictionary-like access
    data = GenerationStateData(selected_preset_id="cyberpunk", extra_data={"foo": "bar"})
    assert data["selected_preset_id"] == "cyberpunk"
    assert data["foo"] == "bar"
    assert data.get("nonexistent", "default") == "default"


def test_payments_handlers_split_and_router():
    """Verify that payments handlers are properly split and aggregated into payments_router."""
    assert isinstance(payments_router, Router)
    assert isinstance(buy_router, Router)
    assert isinstance(pre_checkout_router, Router)
    assert isinstance(fulfillment_router, Router)

    assert buy_router is mod_buy_router
    assert pre_checkout_router is mod_pre_checkout_router
    assert fulfillment_router is mod_fulfillment_router

    assert process_buy_stars_callback is mod_process_buy_stars_callback
    assert process_pre_checkout is mod_process_pre_checkout
    assert process_successful_payment is mod_process_successful_payment
    assert send_star_invoice is mod_send_star_invoice

    # Check that payments_router includes all sub-routers
    sub_names = {r.name for r in payments_router.sub_routers}
    assert {"buy_router", "pre_checkout_router", "fulfillment_router"}.issubset(sub_names)
