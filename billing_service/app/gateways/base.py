from typing import Protocol


class PaymentGateway(Protocol):
    """Charge a toll. Implementations must be safe to call once per toll event id."""

    async def charge(
        self,
        *,
        transaction_id: int,
        toll_event_id: str,
        vehicle_id: str,
        amount: float,
        currency: str,
    ) -> str:
        """Return a gateway reference on success. Raise PaymentGatewayError otherwise."""
