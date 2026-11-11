"""Payment gateway implementations.

`PAYMENT_GATEWAY=mock` is the default and needs no network.
`PAYMENT_GATEWAY=stripe` uses Stripe test mode and stays off unless configured.
"""

from app.gateways.base import PaymentGateway
from app.gateways.mock import MockPaymentGateway

__all__ = ["PaymentGateway", "MockPaymentGateway", "build_gateway"]


def build_gateway() -> PaymentGateway:
    """Return the gateway selected by settings. Stripe is imported lazily."""
    from app.config import settings

    kind = settings.PAYMENT_GATEWAY
    if kind == "mock":
        return MockPaymentGateway(
            fail_rate=settings.MOCK_PAYMENT_FAIL_RATE,
            timeout_rate=settings.MOCK_PAYMENT_TIMEOUT_RATE,
        )
    if kind == "stripe":
        from app.gateways.stripe import StripeTestPaymentGateway
        return StripeTestPaymentGateway(api_key=settings.STRIPE_API_KEY or "")
    raise RuntimeError(f"Unsupported PAYMENT_GATEWAY '{kind}'")
