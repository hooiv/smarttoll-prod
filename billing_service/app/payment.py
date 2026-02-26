import asyncio
import random
import logging
import uuid
from typing import Tuple, Optional

from app.config import settings

log = logging.getLogger(__name__)

# --- Mock Payment Gateway Interface ---

class PaymentGatewayError(Exception):
    """Custom exception for payment gateway failures."""
    def __init__(self, message: str, error_code: Optional[str] = None):
        self.message = message
        self.error_code = error_code or "UNKNOWN_ERROR"
        super().__init__(self.message)

async def process_payment(
    *, # Force keyword arguments
    transaction_id: int, # Internal DB transaction ID
    toll_event_id: str, # Event ID for idempotency check (if GW supports it)
    vehicle_id: str,
    amount: float,
    currency: str
) -> Tuple[str, Optional[str]]:
    """
    Simulates calling an external payment gateway asynchronously.

    Args:
        transaction_id: Our internal reference.
        toll_event_id: The original event ID.
        vehicle_id: Identifier for the customer/vehicle account.
        amount: Amount to charge.
        currency: Currency code.

    Returns:
        A tuple containing:
        - gateway_ref (str): The unique reference ID from the gateway on success.
        - error_message (Optional[str]): An error message string on failure.

    Raises:
        PaymentGatewayError: If the payment fails.
    """
    log.info(f"[Mock GW] Initiating payment for TxID={transaction_id}, Event={toll_event_id}, Vehicle={vehicle_id}, Amount={amount:.2f} {currency}")

    # Simulate network delay and processing time
    await asyncio.sleep(random.uniform(0.05, 0.3))

    # Simulate potential transient errors (e.g., network timeout before getting response)
    if random.random() < 0.03: # 3% chance of transient failure
        log.warning(f"[Mock GW] Simulated transient network error for TxID={transaction_id}")
        raise PaymentGatewayError("Simulated network timeout", error_code="GW_TIMEOUT")

    # Simulate success/failure based on configured rate
    is_success = random.random() > settings.MOCK_PAYMENT_FAIL_RATE

    if is_success:
        gateway_ref = f"MOCKGW_{uuid.uuid4().hex[:16].upper()}"
        log.info(f"[Mock GW] Payment SUCCESS for TxID={transaction_id}. Gateway Ref: {gateway_ref}")
        return gateway_ref, None
    else:
        # Simulate different failure reasons
        possible_errors = [
            ("Insufficient funds", "INSUFFICIENT_FUNDS"),
            ("Card declined", "CARD_DECLINED"),
            ("Account frozen", "ACCOUNT_FROZEN"),
            ("Invalid card details", "INVALID_CARD"),
            ("Expired card", "EXPIRED_CARD"),
        ]
        error_msg, error_code = random.choice(possible_errors)
        log.warning(f"[Mock GW] Payment FAILED for TxID={transaction_id}. Reason: {error_msg} (Code: {error_code})")
        raise PaymentGatewayError(error_msg, error_code=error_code)
