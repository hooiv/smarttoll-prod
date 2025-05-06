import pytest
import time
from unittest.mock import MagicMock, AsyncMock, patch
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

# Import the module/functions to test
from app import billing, models
from app.payment import PaymentGatewayError
from app.config import settings

# Use pytest-mock fixture 'mocker'
pytest_plugins = ("pytest_mock",)

# --- Test Data ---
SAMPLE_TOLL_EVENT = models.TollEvent(
    eventId="evt_abc123", vehicleId="VEH_XYZ", deviceId="DEV987",
    zoneId="ZoneC", entryTime=int(time.time()*1000 - 60000), exitTime=int(time.time()*1000),
    distanceKm=5.5, ratePerKm=0.25, tollAmount=1.38, currency="USD",
    processedTimestamp=int(time.time()*1000)
)

# --- Test Fixtures ---

@pytest.fixture
def mock_db_session(mocker) -> MagicMock:
    """Creates a mock SQLAlchemy session."""
    mock_session = MagicMock(spec=Session)
    # Mock common methods needed
    mock_session.query.return_value.filter.return_value.first.return_value = None  # Default: no existing tx
    mock_session.add = MagicMock()
    mock_session.commit = MagicMock()
    mock_session.rollback = MagicMock()
    mock_session.flush = MagicMock()
    mock_session.refresh = MagicMock()
    mock_session.execute.return_value.scalars.return_value.first.return_value = None  # For select() usage
    mock_session.get.return_value = None  # For db.get() usage

    return mock_session

@pytest.fixture
def mock_payment_gateway(mocker) -> AsyncMock:
    """Mocks the payment gateway function."""
    # Patch the function within the 'billing' module where it's called from
    mock_process_payment = mocker.patch("app.billing.payment.process_payment", new_callable=AsyncMock)
    # Default successful payment
    mock_process_payment.return_value = ("MOCK_GW_REF_SUCCESS", None)
    return mock_process_payment

@pytest.fixture
def mock_kafka_producer(mocker) -> MagicMock:
    """Mocks the Kafka producer send function."""
    mock_producer_instance = MagicMock()
    mock_producer_instance.send = MagicMock(return_value=True)  # Simulate successful send
    # Patch the getter function that returns the producer instance
    mocker.patch("app.billing.kafka_client.get_kafka_producer", return_value=mock_producer_instance)
    return mock_producer_instance

# --- Test Cases ---

@pytest.mark.asyncio  # Mark test as async
async def test_process_billing_event_success(mock_db_session, mock_payment_gateway, mock_kafka_producer):
    """Test successful processing of a new toll event."""
    success = await billing.process_toll_event_for_billing(SAMPLE_TOLL_EVENT, mock_db_session)

    assert success is True

    # 1. Check if existing transaction was checked
    mock_db_session.execute.assert_called_once()  # Check if select() was executed

    # 2. Check if new transaction was added and committed (PENDING)
    assert mock_db_session.add.call_count == 1
    added_tx: models.BillingTransaction = mock_db_session.add.call_args[0][0]
    assert added_tx.toll_event_id == SAMPLE_TOLL_EVENT.eventId
    assert added_tx.status == "PENDING"
    assert added_tx.amount == SAMPLE_TOLL_EVENT.tollAmount
    # Check commit was called after add (for PENDING status)
    # Check flush and refresh were called to get ID
    assert mock_db_session.flush.call_count == 1
    assert mock_db_session.commit.call_count == 3  # PENDING, PROCESSING, FINAL STATUS
    assert mock_db_session.refresh.call_count == 1


    # 3. Check if payment gateway was called
    mock_payment_gateway.assert_awaited_once()
    call_args, call_kwargs = mock_payment_gateway.call_args
    # Assert specific arguments passed to payment gateway
    assert call_kwargs['toll_event_id'] == SAMPLE_TOLL_EVENT.eventId
    assert call_kwargs['amount'] == SAMPLE_TOLL_EVENT.tollAmount

    # 4. Check if transaction status was updated (to PROCESSING then SUCCESS) and committed
    # We check the final state by inspecting the object passed to commit or queried later
    # Let's assume the session manages the object `new_tx` state changes
    assert added_tx.status == "SUCCESS"  # Final status after successful payment
    assert added_tx.payment_gateway_ref == "MOCK_GW_REF_SUCCESS"
    assert added_tx.error_message is None

    # 5. Check if payment result was published to Kafka
    assert mock_kafka_producer.send.call_count == 1
    args, kwargs = mock_kafka_producer.send.call_args
    assert args[0] == settings.PAYMENT_EVENT_TOPIC
    payload = args[1]
    assert payload['eventId'] == SAMPLE_TOLL_EVENT.eventId
    assert payload['status'] == "SUCCESS"
    assert payload['gatewayReference'] == "MOCK_GW_REF_SUCCESS"

@pytest.mark.asyncio
async def test_process_billing_event_duplicate_success(mock_db_session, mock_payment_gateway, mock_kafka_producer):
    """Test handling of a duplicate event that was already successful."""
    # Simulate finding an existing successful transaction
    existing_tx = models.BillingTransaction(id=99, toll_event_id=SAMPLE_TOLL_EVENT.eventId, status="SUCCESS")
    mock_db_session.execute.return_value.scalars.return_value.first.return_value = existing_tx

    success = await billing.process_toll_event_for_billing(SAMPLE_TOLL_EVENT, mock_db_session)

    assert success is True  # Handled gracefully
    # Ensure no new transaction added, no payment call, no kafka publish
    mock_db_session.add.assert_not_called()
    mock_payment_gateway.assert_not_awaited()
    mock_kafka_producer.send.assert_not_called()
    # Ensure commit wasn't called (beyond potentially the initial check if structure requires it)
    assert mock_db_session.commit.call_count == 0

@pytest.mark.asyncio
async def test_process_billing_event_duplicate_pending(mock_db_session, mock_payment_gateway, mock_kafka_producer):
    """Test handling of a duplicate event that is already pending."""
    # Simulate finding an existing successful transaction
    existing_tx = models.BillingTransaction(id=98, toll_event_id=SAMPLE_TOLL_EVENT.eventId, status="PENDING")
    mock_db_session.execute.return_value.scalars.return_value.first.return_value = existing_tx

    success = await billing.process_toll_event_for_billing(SAMPLE_TOLL_EVENT, mock_db_session)

    assert success is True  # Handled gracefully
    mock_db_session.add.assert_not_called()
    mock_payment_gateway.assert_not_awaited()
    mock_kafka_producer.send.assert_not_called()
    assert mock_db_session.commit.call_count == 0


@pytest.mark.asyncio
async def test_process_billing_event_payment_failure(mock_db_session, mock_payment_gateway, mock_kafka_producer):
    """Test processing when the payment gateway call fails."""
    # Configure mock payment gateway to fail
    mock_payment_gateway.side_effect = PaymentGatewayError("Card declined", error_code="CARD_DECLINED")
    # Simulate db.get finding the tx after creation for status update
    created_tx = models.BillingTransaction(id=1, toll_event_id=SAMPLE_TOLL_EVENT.eventId, status="PENDING")
    mock_db_session.get.return_value = created_tx  # Make db.get return the object

    success = await billing.process_toll_event_for_billing(SAMPLE_TOLL_EVENT, mock_db_session)

    assert success is True  # Processing completed, even though payment failed

    # Check tx added, flushed, committed (PENDING)
    assert mock_db_session.add.call_count == 1
    assert mock_db_session.flush.call_count == 1
    assert mock_db_session.commit.call_count == 3  # PENDING, PROCESSING, FAILED

    # Check payment gateway was called
    mock_payment_gateway.assert_awaited_once()

    # Check final status is FAILED and error message is recorded
    assert created_tx.status == "FAILED"  # Check the object state after commit
    assert created_tx.payment_gateway_ref is None
    assert "CARD_DECLINED: Card declined" in created_tx.error_message

    # Check Kafka event published with FAILED status
    assert mock_kafka_producer.send.call_count == 1
    args, kwargs = mock_kafka_producer.send.call_args
    payload = args[1]
    assert payload['status'] == "FAILED"
    assert "CARD_DECLINED" in payload['errorMessage']

@pytest.mark.asyncio
async def test_process_billing_event_db_error_on_create(mock_db_session, mock_payment_gateway, mock_kafka_producer):
    """Test handling when saving the initial PENDING transaction fails."""
    # Simulate DB error during the first commit
    mock_db_session.commit.side_effect = [SQLAlchemyError("Connection lost"), None, None]  # Fail first commit only

    success = await billing.process_toll_event_for_billing(SAMPLE_TOLL_EVENT, mock_db_session)

    assert success is False  # Processing failed due to DB error
    mock_db_session.add.assert_called_once()
    mock_db_session.rollback.assert_called_once()  # Ensure rollback was called
    mock_payment_gateway.assert_not_awaited()  # Payment should not be attempted
    mock_kafka_producer.send.assert_not_called()  # No event published

@pytest.mark.asyncio
async def test_process_billing_event_db_error_on_update(mock_db_session, mock_payment_gateway, mock_kafka_producer):
    """Test handling when updating the final status fails after successful payment."""
    # Simulate successful payment
    mock_payment_gateway.return_value = ("MOCK_GW_REF_SUCCESS", None)
    # Simulate DB error during the final commit
    mock_db_session.commit.side_effect = [None, None, SQLAlchemyError("Update failed")]  # Success PENDING, PROCESSING, Fail FINAL
    # Simulate db.get finding the tx
    created_tx = models.BillingTransaction(id=1, toll_event_id=SAMPLE_TOLL_EVENT.eventId, status="PROCESSING")
    mock_db_session.get.return_value = created_tx

    success = await billing.process_toll_event_for_billing(SAMPLE_TOLL_EVENT, mock_db_session)

    assert success is False  # Processing failed due to DB error during update

    mock_payment_gateway.assert_awaited_once()  # Payment was attempted
    # Check rollback was called after the failed commit
    assert mock_db_session.rollback.call_count == 1

    # Check Kafka event IS STILL PUBLISHED (usually desired, payment happened)
    assert mock_kafka_producer.send.call_count == 1
    args, kwargs = mock_kafka_producer.send.call_args
    payload = args[1]
    assert payload['status'] == "SUCCESS"  # Publish the actual payment outcome