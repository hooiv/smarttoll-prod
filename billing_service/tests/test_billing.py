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
    """Creates a mock SQLAlchemy session.

    The flush side-effect simulates the database assigning an auto-increment
    primary key to the most-recently-added object, mirroring real ORM behaviour.
    """
    mock_session = MagicMock(spec=Session)
    mock_session.add = MagicMock()
    mock_session.commit = MagicMock()
    mock_session.rollback = MagicMock()
    mock_session.execute.return_value.scalars.return_value.first.return_value = None

    def _flush_assigns_id():
        """Simulate DB assigning id=1 to the last added object on flush."""
        if mock_session.add.call_args_list:
            obj = mock_session.add.call_args_list[-1][0][0]
            if getattr(obj, 'id', None) is None:
                obj.id = 1

    mock_session.flush = MagicMock(side_effect=_flush_assigns_id)
    mock_session.refresh = MagicMock()  # refresh is a no-op in tests (id already set by flush)

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

    # 1. Duplicate check was performed
    mock_db_session.execute.assert_called_once()

    # 2. Transaction was created: add / flush / refresh / commit cycle
    assert mock_db_session.add.call_count == 1
    added_tx: models.BillingTransaction = mock_db_session.add.call_args[0][0]
    assert added_tx.toll_event_id == SAMPLE_TOLL_EVENT.eventId
    assert added_tx.amount == SAMPLE_TOLL_EVENT.tollAmount
    assert mock_db_session.flush.call_count == 1
    assert mock_db_session.refresh.call_count == 1
    assert mock_db_session.commit.call_count == 3  # PENDING → PROCESSING → SUCCESS

    # 3. Payment gateway was called with correct arguments
    mock_payment_gateway.assert_awaited_once()
    _, call_kwargs = mock_payment_gateway.call_args
    assert call_kwargs['toll_event_id'] == SAMPLE_TOLL_EVENT.eventId
    assert call_kwargs['amount'] == SAMPLE_TOLL_EVENT.tollAmount

    # 4. Transaction object updated to final SUCCESS state
    assert added_tx.status == "SUCCESS"
    assert added_tx.payment_gateway_ref == "MOCK_GW_REF_SUCCESS"
    assert added_tx.error_message is None

    # 5. PaymentResult published to Kafka (value passed as keyword argument)
    assert mock_kafka_producer.send.call_count == 1
    _, send_kwargs = mock_kafka_producer.send.call_args
    assert mock_kafka_producer.send.call_args[0][0] == settings.PAYMENT_EVENT_TOPIC
    payload = send_kwargs['value']
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
    mock_payment_gateway.side_effect = PaymentGatewayError("Card declined", error_code="CARD_DECLINED")

    success = await billing.process_toll_event_for_billing(SAMPLE_TOLL_EVENT, mock_db_session)

    assert success is True  # Processing completed, even though payment failed

    # Transaction created, flushed, refreshed, and committed 3× (PENDING, PROCESSING, FAILED)
    assert mock_db_session.add.call_count == 1
    assert mock_db_session.flush.call_count == 1
    assert mock_db_session.refresh.call_count == 1
    assert mock_db_session.commit.call_count == 3

    mock_payment_gateway.assert_awaited_once()

    # The added transaction object itself reflects the final FAILED state
    added_tx: models.BillingTransaction = mock_db_session.add.call_args[0][0]
    assert added_tx.status == "FAILED"
    assert added_tx.payment_gateway_ref is None
    assert "CARD_DECLINED: Card declined" in added_tx.error_message

    # Kafka event published with FAILED status
    assert mock_kafka_producer.send.call_count == 1
    _, send_kwargs = mock_kafka_producer.send.call_args
    payload = send_kwargs['value']
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
    """Test handling when updating the final status fails after successful payment.

    Even when the DB commit fails the payment result MUST still be published to Kafka
    so downstream consumers stay consistent with the actual payment outcome.
    """
    mock_payment_gateway.return_value = ("MOCK_GW_REF_SUCCESS", None)
    # First two commits succeed (PENDING, PROCESSING); third (final status) raises
    mock_db_session.commit.side_effect = [None, None, SQLAlchemyError("Update failed")]

    success = await billing.process_toll_event_for_billing(SAMPLE_TOLL_EVENT, mock_db_session)

    assert success is False  # DB error → failure signal

    mock_payment_gateway.assert_awaited_once()
    assert mock_db_session.rollback.call_count == 1

    # Kafka event IS published despite DB failure (payment already happened)
    assert mock_kafka_producer.send.call_count == 1
    _, send_kwargs = mock_kafka_producer.send.call_args
    payload = send_kwargs['value']
    assert payload['status'] == "SUCCESS"  # Reflects actual payment outcome