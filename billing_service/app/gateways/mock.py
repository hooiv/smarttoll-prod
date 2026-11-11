import asyncio
import logging
import random
import uuid

from app.gateways.errors import PaymentGatewayError

log = logging.getLogger(__name__)


class MockPaymentGateway:
    """In-process stand-in for a card processor.

    Outcomes are fully determined by the configured rates. A fail rate of 0 and
    a timeout rate of 0 always succeed, so a local demo is reproducible.
    """

    def __init__(self, fail_rate: float = 0.0, timeout_rate: float = 0.0) -> None:
        self.fail_rate = fail_rate
        self.timeout_rate = timeout_rate

    async def charge(
        self,
        *,
        transaction_id: int,
        toll_event_id: str,
        vehicle_id: str,
        amount: float,
        currency: str,
    ) -> str:
        log.info(
            "[Mock GW] Initiating payment for TxID=%s, Event=%s, Vehicle=%s, Amount=%.2f %s",
            transaction_id, toll_event_id, vehicle_id, amount, currency,
        )
        await asyncio.sleep(random.uniform(0.02, 0.08))

        if self.timeout_rate > 0 and random.random() < self.timeout_rate:
            log.warning("[Mock GW] Simulated timeout for TxID=%s", transaction_id)
            raise PaymentGatewayError("Simulated network timeout", error_code="GW_TIMEOUT")

        if self.fail_rate > 0 and random.random() < self.fail_rate:
            reasons = [
                ("Insufficient funds", "INSUFFICIENT_FUNDS"),
                ("Card declined", "CARD_DECLINED"),
                ("Account frozen", "ACCOUNT_FROZEN"),
                ("Invalid card details", "INVALID_CARD"),
                ("Expired card", "EXPIRED_CARD"),
            ]
            error_msg, error_code = random.choice(reasons)
            log.warning(
                "[Mock GW] Payment FAILED for TxID=%s. Reason: %s (%s)",
                transaction_id, error_msg, error_code,
            )
            raise PaymentGatewayError(error_msg, error_code=error_code)

        gateway_ref = f"MOCKGW_{uuid.uuid4().hex[:16].upper()}"
        log.info("[Mock GW] Payment SUCCESS for TxID=%s. Gateway Ref: %s", transaction_id, gateway_ref)
        return gateway_ref
