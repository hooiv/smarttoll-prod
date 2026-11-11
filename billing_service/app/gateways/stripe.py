"""Stripe test-mode adapter.

Off unless PAYMENT_GATEWAY=stripe. Accepts test secret keys only (sk_test_ / rk_test_).
Charges use the documented test PaymentMethod pm_card_visa and send the toll event id
as the Stripe Idempotency-Key so a redelivery cannot create a second PaymentIntent.
"""

import asyncio
import json
import logging
import urllib.error
import urllib.parse
import urllib.request

from app.gateways.errors import PaymentGatewayError

log = logging.getLogger(__name__)

_STRIPE_URL = "https://api.stripe.com/v1/payment_intents"
_SUCCESS_STATUSES = {"succeeded", "processing", "requires_capture"}


class StripeTestPaymentGateway:
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    async def charge(
        self,
        *,
        transaction_id: int,
        toll_event_id: str,
        vehicle_id: str,
        amount: float,
        currency: str,
    ) -> str:
        if not self.api_key.startswith(("sk_test_", "rk_test_")):
            raise PaymentGatewayError(
                "Stripe adapter accepts test keys only",
                error_code="CONFIG",
            )
        log.info(
            "[Stripe test] Creating PaymentIntent for TxID=%s Event=%s Vehicle=%s Amount=%.2f %s",
            transaction_id, toll_event_id, vehicle_id, amount, currency,
        )
        try:
            payload = await asyncio.to_thread(
                self._create_intent,
                toll_event_id=toll_event_id,
                vehicle_id=vehicle_id,
                amount=amount,
                currency=currency,
            )
        except PaymentGatewayError:
            raise
        except Exception as exc:
            raise PaymentGatewayError(f"Stripe request failed: {exc}", error_code="GW_TIMEOUT") from exc

        status = payload.get("status")
        intent_id = payload.get("id")
        if status not in _SUCCESS_STATUSES or not intent_id:
            message = (payload.get("error") or {}).get("message") or f"unexpected status {status}"
            raise PaymentGatewayError(message, error_code="CARD_DECLINED")
        log.info("[Stripe test] PaymentIntent %s status=%s", intent_id, status)
        return intent_id

    def _create_intent(self, *, toll_event_id: str, vehicle_id: str, amount: float, currency: str) -> dict:
        minor = int(round(amount * 100))
        # Stripe minimums: 50 cents (USD) or ₹50 (INR). The real toll is still in metadata.
        minimum = 5000 if currency.upper() == "INR" else 50
        cents = minor if minor >= minimum else minimum
        body = urllib.parse.urlencode({
            "amount": str(cents),
            "currency": currency.lower(),
            "payment_method": "pm_card_visa",
            "confirm": "true",
            "off_session": "true",
            "description": f"SmartToll {toll_event_id}",
            "metadata[toll_event_id]": toll_event_id,
            "metadata[vehicle_id]": vehicle_id,
            "metadata[requested_amount]": f"{amount:.2f}",
        }).encode()
        request = urllib.request.Request(
            _STRIPE_URL,
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/x-www-form-urlencoded",
                "Idempotency-Key": toll_event_id,
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                return json.loads(response.read().decode())
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode(errors="replace")
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                parsed = {}
            message = (parsed.get("error") or {}).get("message") or raw or str(exc)
            code = (parsed.get("error") or {}).get("code") or "CARD_DECLINED"
            raise PaymentGatewayError(message, error_code=str(code).upper()) from exc
