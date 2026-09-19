import logging

from aiogram import Router
from aiogram.types import PreCheckoutQuery

logger = logging.getLogger(__name__)
pre_checkout_router = Router(name="pre_checkout_router")


@pre_checkout_router.pre_checkout_query()
async def process_pre_checkout(pre_checkout_query: PreCheckoutQuery):
    """
    Pre-checkout query handler to confirm payment availability.
    """
    logger.info(
        f"Received PreCheckoutQuery ID: {pre_checkout_query.id} for payload: {pre_checkout_query.invoice_payload}"
    )
    await pre_checkout_query.answer(ok=True)


__all__ = ["pre_checkout_router", "process_pre_checkout"]
