"""Offset commits must name the record that was finished.

commit() with no offsets would mark every record from the last poll as
consumed. These tests reject that, and they reject a commit that happens
before the dead-letter copy is accepted.
"""

from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from kafka import OffsetAndMetadata, TopicPartition

from app import consumer

TOPIC = "smarttoll.toll.events.v1"
PARTITION = 3

PAYLOAD = {
    "eventId": "evt-kherki-1",
    "vehicleId": "HR26DK8481",
    "deviceId": "OBU-HR26DK8481",
    "zoneId": "NH48-KHERKI",
    "entryTime": 1,
    "exitTime": 2,
    "distanceKm": 0.4,
    "ratePerKm": 0.0,
    "tollAmount": 105.0,
    "currency": "INR",
    "processedTimestamp": 3,
}


def record(offset, value=None):
    return SimpleNamespace(
        topic=TOPIC,
        partition=PARTITION,
        offset=offset,
        value=PAYLOAD if value is None else value,
    )


def next_offset(offset):
    return {TopicPartition(TOPIC, PARTITION): OffsetAndMetadata(offset + 1, "")}


def assert_specific_commits(mock_consumer, offsets):
    assert mock_consumer.commit.call_count == len(offsets)
    for call, offset in zip(mock_consumer.commit.call_args_list, offsets):
        assert call.args == (next_offset(offset),)
        assert call.kwargs == {}


@pytest.fixture(autouse=True)
def clear_attempts():
    consumer._attempt_counts.clear()
    yield
    consumer._attempt_counts.clear()


@pytest.fixture
def db_session(mocker):
    @contextmanager
    def _session():
        yield MagicMock()

    mocker.patch("app.consumer.database.get_db_session", _session)


@pytest.fixture
def process_billing(mocker):
    return mocker.patch(
        "app.consumer.billing.process_toll_event_for_billing",
        new_callable=AsyncMock,
        return_value=True,
    )


@pytest.fixture
def publish_dlq(mocker):
    return mocker.patch("app.consumer.kafka_client.publish_dlq", return_value=True)


async def test_success_commits_only_that_record(db_session, process_billing):
    mock_consumer = MagicMock()
    done = await consumer.process_message(record(10), None, mock_consumer)

    assert done is True
    assert_specific_commits(mock_consumer, [10])
    mock_consumer.seek.assert_not_called()


async def test_batch_commits_each_record_and_stops_when_one_is_not_ready(
    db_session, process_billing, mocker,
):
    process_billing.side_effect = [True, False]
    mocker.patch("app.consumer.asyncio.sleep", new_callable=AsyncMock)
    mocker.patch("app.consumer.settings.BILLING_MAX_PROCESS_ATTEMPTS", 5)
    mock_consumer = MagicMock()
    pack = {TopicPartition(TOPIC, PARTITION): [record(4), record(5), record(6)]}

    await consumer.handle_polled_records(mock_consumer, pack, None)

    assert process_billing.await_count == 2
    assert_specific_commits(mock_consumer, [4])
    mock_consumer.seek.assert_called_once_with(TopicPartition(TOPIC, PARTITION), 5)


async def test_retry_does_not_commit(db_session, process_billing, mocker):
    process_billing.return_value = False
    mocker.patch("app.consumer.asyncio.sleep", new_callable=AsyncMock)
    mocker.patch("app.consumer.settings.BILLING_MAX_PROCESS_ATTEMPTS", 5)
    mock_consumer = MagicMock()

    done = await consumer.process_message(record(7), None, mock_consumer)

    assert done is False
    mock_consumer.commit.assert_not_called()
    mock_consumer.seek.assert_called_once_with(TopicPartition(TOPIC, PARTITION), 7)


async def test_dead_letter_commits_only_after_publish(db_session, process_billing, publish_dlq, mocker):
    mocker.patch("app.consumer.settings.BILLING_MAX_PROCESS_ATTEMPTS", 5)
    process_billing.return_value = False
    consumer._attempt_counts[(TOPIC, PARTITION, 8)] = 4
    mock_consumer = MagicMock()

    done = await consumer.process_message(record(8), None, mock_consumer)

    assert done is True
    publish_dlq.assert_called_once()
    assert_specific_commits(mock_consumer, [8])
    mock_consumer.seek.assert_not_called()


async def test_dead_letter_publish_failure_does_not_commit(db_session, process_billing, publish_dlq, mocker):
    mocker.patch("app.consumer.settings.BILLING_MAX_PROCESS_ATTEMPTS", 5)
    process_billing.return_value = False
    publish_dlq.return_value = False
    consumer._attempt_counts[(TOPIC, PARTITION, 9)] = 4
    mock_consumer = MagicMock()

    done = await consumer.process_message(record(9), None, mock_consumer)

    assert done is False
    mock_consumer.commit.assert_not_called()
    mock_consumer.seek.assert_called_once_with(TopicPartition(TOPIC, PARTITION), 9)


async def test_invalid_event_commits_only_after_dead_letter(publish_dlq):
    mock_consumer = MagicMock()

    done = await consumer.process_message(record(11, value={"eventId": "bad"}), None, mock_consumer)

    assert done is True
    publish_dlq.assert_called_once()
    assert publish_dlq.call_args.args[0] == "ValidationError"
    assert_specific_commits(mock_consumer, [11])


async def test_commit_failure_seeks_back_and_does_not_advance(db_session, process_billing):
    mock_consumer = MagicMock()
    mock_consumer.commit.side_effect = RuntimeError("coordinator")

    done = await consumer.process_message(record(12), None, mock_consumer)

    assert done is False
    assert_specific_commits(mock_consumer, [12])
    mock_consumer.seek.assert_called_once_with(TopicPartition(TOPIC, PARTITION), 12)
