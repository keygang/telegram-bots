from typing import ClassVar

from platform_core.events.base import BaseEvent


class PaymentEvent(BaseEvent):
    """
    Event recorded when a user completes a Telegram Stars monetization transaction.
    """

    event_name: ClassVar[str] = "payment_completed"

    stars_amount: int
    credits_added: int
    charge_id: str
    provider_charge_id: str | None = None
    currency: str = "XTR"
    invoice_payload: str | None = None
