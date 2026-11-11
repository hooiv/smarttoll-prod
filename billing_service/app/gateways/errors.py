from typing import Optional


class PaymentGatewayError(Exception):
    """Failure returned by a payment gateway. error_code is stable for metrics."""

    def __init__(self, message: str, error_code: Optional[str] = None):
        self.message = message
        self.error_code = error_code or "UNKNOWN_ERROR"
        super().__init__(self.message)
