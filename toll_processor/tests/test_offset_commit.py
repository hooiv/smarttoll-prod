"""The processor commits one GPS record at a time, after it is finished."""

from types import SimpleNamespace
from unittest.mock import MagicMock

from kafka import OffsetAndMetadata, TopicPartition

from app import main

TOPIC = "smarttoll.gps.raw.v1"
PARTITION = 1


def record(offset):
    return SimpleNamespace(topic=TOPIC, partition=PARTITION, offset=offset, value={"vehicleId": "HR26"})


def next_offset(offset):
    return {TopicPartition(TOPIC, PARTITION): OffsetAndMetadata(offset + 1, "")}


def assert_specific_commits(mock_consumer, offsets):
    assert mock_consumer.commit.call_count == len(offsets)
    for call, offset in zip(mock_consumer.commit.call_args_list, offsets):
        assert call.args == (next_offset(offset),)
        assert call.kwargs == {}


def test_each_successful_record_is_committed_on_its_own(mocker):
    mocker.patch("app.main.processing.process_gps_message", return_value=True)
    mock_consumer = MagicMock()
    pack = {TopicPartition(TOPIC, PARTITION): [record(1), record(2)]}

    main.process_polled_records(mock_consumer, pack)

    assert_specific_commits(mock_consumer, [1, 2])
    mock_consumer.seek.assert_not_called()


def test_failure_does_not_commit_and_does_not_skip_ahead(mocker):
    process = mocker.patch("app.main.processing.process_gps_message", side_effect=[True, False, True])
    mock_consumer = MagicMock()
    pack = {TopicPartition(TOPIC, PARTITION): [record(5), record(6), record(7)]}

    main.process_polled_records(mock_consumer, pack)

    assert process.call_count == 2
    assert_specific_commits(mock_consumer, [5])
    mock_consumer.seek.assert_called_once_with(TopicPartition(TOPIC, PARTITION), 6)


def test_unexpected_error_commits_only_after_error_topic_accepts_it(mocker):
    mocker.patch("app.main.processing.process_gps_message", side_effect=RuntimeError("boom"))
    publish = mocker.patch("app.main.kafka_client.publish_error", return_value=True)
    mock_consumer = MagicMock()

    main.process_polled_records(mock_consumer, {TopicPartition(TOPIC, PARTITION): [record(9)]})

    publish.assert_called_once()
    assert publish.call_args.kwargs["error_type"] == "UnhandledProcessingError"
    assert_specific_commits(mock_consumer, [9])
    mock_consumer.seek.assert_not_called()


def test_error_topic_failure_leaves_the_offset_uncommitted(mocker):
    mocker.patch("app.main.processing.process_gps_message", side_effect=RuntimeError("boom"))
    mocker.patch("app.main.kafka_client.publish_error", return_value=False)
    mock_consumer = MagicMock()

    main.process_polled_records(mock_consumer, {TopicPartition(TOPIC, PARTITION): [record(9), record(10)]})

    mock_consumer.commit.assert_not_called()
    mock_consumer.seek.assert_called_once_with(TopicPartition(TOPIC, PARTITION), 9)


def test_commit_failure_seeks_back(mocker):
    mocker.patch("app.main.processing.process_gps_message", return_value=True)
    mock_consumer = MagicMock()
    mock_consumer.commit.side_effect = RuntimeError("coordinator")

    advanced = main._handle_gps_record(mock_consumer, record(3))

    assert advanced is False
    assert_specific_commits(mock_consumer, [3])
    mock_consumer.seek.assert_called_once_with(TopicPartition(TOPIC, PARTITION), 3)
