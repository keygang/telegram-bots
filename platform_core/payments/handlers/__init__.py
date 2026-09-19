from aiogram import Router

from .buy import buy_router, process_buy_stars_callback
from .fulfillment import fulfillment_router, process_successful_payment
from .invoice import send_star_invoice
from .pre_checkout import pre_checkout_router, process_pre_checkout

payments_router = Router(name="payments_router")
payments_router.include_router(buy_router)
payments_router.include_router(pre_checkout_router)
payments_router.include_router(fulfillment_router)

__all__ = [
    "buy_router",
    "fulfillment_router",
    "payments_router",
    "pre_checkout_router",
    "process_buy_stars_callback",
    "process_pre_checkout",
    "process_successful_payment",
    "send_star_invoice",
]
