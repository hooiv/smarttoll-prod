import pytest
from pydantic import ValidationError

from app.config import Settings
from app.gateways.mock import MockPaymentGateway
from app.gateways.stripe import StripeTestPaymentGateway
from app.payment import PaymentGatewayError


@pytest.mark.asyncio
async def test_mock_gateway_always_succeeds_when_rates_are_zero():
    gateway = MockPaymentGateway(fail_rate=0.0, timeout_rate=0.0)
    refs = [
        await gateway.charge(
            transaction_id=i, toll_event_id=f"evt-{i}", vehicle_id="V", amount=0.18, currency="USD",
        )
        for i in range(25)
    ]
    assert len(refs) == 25
    assert all(ref.startswith("MOCKGW_") for ref in refs)


def test_settings_reject_fail_rate_above_one(monkeypatch):
    monkeypatch.setenv("MOCK_PAYMENT_FAIL_RATE", "1.5")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_stripe_gateway_requires_a_test_key(monkeypatch):
    monkeypatch.setenv("PAYMENT_GATEWAY", "stripe")
    monkeypatch.setenv("STRIPE_API_KEY", "sk_live_not_allowed")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


@pytest.mark.asyncio
async def test_stripe_adapter_rejects_live_keys_even_if_constructed():
    gateway = StripeTestPaymentGateway("sk_live_not_allowed")
    with pytest.raises(PaymentGatewayError) as caught:
        await gateway.charge(
            transaction_id=1, toll_event_id="evt", vehicle_id="V", amount=1.0, currency="USD",
        )
    assert caught.value.error_code == "CONFIG"


@pytest.mark.asyncio
async def test_stripe_adapter_returns_payment_intent_id(monkeypatch):
    class _Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return b'{"id":"pi_test_123","status":"succeeded"}'

    monkeypatch.setattr("app.gateways.stripe.urllib.request.urlopen", lambda *args, **kwargs: _Response())
    gateway = StripeTestPaymentGateway("sk_test_dummy")
    ref = await gateway.charge(
        transaction_id=1, toll_event_id="evt-1", vehicle_id="V", amount=0.18, currency="USD",
    )
    assert ref == "pi_test_123"
