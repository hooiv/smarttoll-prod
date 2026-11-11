"""Payment facade.

Callers (and the unit tests) use ``process_payment``. The function delegates to
the gateway selected by PAYMENT_GATEWAY so billing logic does not know whether
the charge is simulated or sent to Stripe test mode.
"""

import logging
from typing import Optional, Tuple

from app.gateways import build_gateway
from app.gateways.errors import PaymentGatewayError

log = logging.getLogger(__name__)

__all__ = ["PaymentGatewayError", "process_payment"]


async def process_payment(
    *,
    transaction_id: int,
    toll_event_id: str,
    vehicle_id: str,
    amount: float,
    currency: str,
) -> Tuple[str, Optional[str]]:
    """Charge ``amount`` and return ``(gateway_ref, None)``.

    Raises:
        PaymentGatewayError: the gateway refused or could not complete the charge.
    """
    gateway = build_gateway()
    gateway_ref = await gateway.charge(
        transaction_id=transaction_id,
        toll_event_id=toll_event_id,
        vehicle_id=vehicle_id,
        amount=amount,
        currency=currency,
    )
    return gateway_ref, None
