import asyncio
import logging
from kafka import TopicPartition
from kafka.consumer.fetcher import ConsumerRecord
from sqlalchemy.orm import sessionmaker
from pydantic import ValidationError

from app.config import settings
from app import models, billing, kafka_client, database, metrics # Relative imports

log = logging.getLogger(__name__)

# Global event to signal when consumer is ready
consumer_ready = asyncio.Event()

# In-process retry budget for transient failures. Restarts redeliver from the
# committed offset; billing idempotency makes that safe.
_attempt_counts: dict[tuple, int] = {}


def _backoff_seconds(attempt: int) -> float:
    return min(15.0, float(2 ** min(attempt, 4)))


async def consume_loop(db_session_factory: sessionmaker):
    log.info("Consumer loop starting...")
    consumer_client = None
    try:
        attempt = 0
        while consumer_client is None:
            attempt += 1
            try:
                # One try per loop so this coroutine can sleep without holding a long sync retry.
                consumer_client = kafka_client.get_kafka_consumer(retry_attempts=1)
            except asyncio.CancelledError:
                raise
            except Exception:
                delay = _backoff_seconds(attempt)
                log.warning(
                    "Kafka consumer not ready (attempt %s). Retrying in %.0fs.",
                    attempt, delay,
                )
                await asyncio.sleep(delay)

        log.info("Kafka consumer is ready.")
        consumer_ready.set()

        log.info(f"Starting consumption from topic '{settings.TOLL_EVENT_TOPIC}'...")
        while True:
            try:
                # Use poll with a short timeout to avoid blocking the async event loop indefinitely
                msg_pack = consumer_client.poll(timeout_ms=200)
                for tp, messages in msg_pack.items():
                    for message in messages:
                        log.info(f"Received message - Topic: {message.topic}, Partition: {message.partition}, Offset: {message.offset}")
                        metrics.kafka_messages_received_total.inc()
                        await process_message(message, db_session_factory, consumer_client)
                await asyncio.sleep(0.05) # Yield control back to Uvicorn's main loop
            except asyncio.CancelledError:
                log.info("Consume loop (inner while True) cancelled.")
                break # Exit the while True loop
            except Exception as e_loop:
                log.exception(f"Error in Kafka consumer message processing loop: {e_loop}")
                # Depending on the error, you might want to break, continue, or implement a backoff
                await asyncio.sleep(settings.KAFKA_CONSUMER_RETRY_DELAY_S) # Wait before retrying

    except asyncio.CancelledError:
        log.info("Consumer_loop task was cancelled (outer try).")
    except Exception as e:
        # This catches errors during consumer_client initialization or other setup before the main loop
        log.exception(f"Unhandled exception in consume_loop (outside main while True): {e}")
    finally:
        log.info("consume_loop task finishing.")
        if consumer_client:
            try:
                log.info("Stopping Kafka consumer client...")
                consumer_client.close()
                log.info("Kafka consumer client stopped.")
            except Exception as e_stop:
                log.exception(f"Error stopping Kafka consumer client: {e_stop}")
        # Do not set ready_event in finally; it's set only on successful init.

async def process_message(message: ConsumerRecord, db_session_factory: sessionmaker, consumer):
    """Processes a single message received from Kafka."""
    try:
        event_data_dict = message.value # Already deserialized dict
        # Validate the incoming data structure
        event_data = models.TollEvent(**event_data_dict)

        # Get a new DB session for this message
        with database.get_db_session() as db:
            try:
                # Process the event using the billing logic
                success = await billing.process_toll_event_for_billing(event_data, db)

                # Commit Kafka offset ONLY if processing succeeded or was handled gracefully (e.g., duplicate)
                if success:
                    _attempt_counts.pop(_message_key(message), None)
                    try:
                        consumer.commit() # Commit offset for the partition this message came from
                        metrics.kafka_messages_processed_total.inc()
                        log.debug(f"Committed offset {message.offset} for event {event_data.eventId}")
                    except Exception as commit_exc:
                         log.error(f"Failed to commit Kafka offset {message.offset} after processing event {event_data.eventId}: {commit_exc}", exc_info=True)
                         # This is problematic - risk of reprocessing. Alerting needed.
                else:
                     metrics.kafka_messages_error_total.inc()
                     await _retry_or_dead_letter(
                         consumer, message, "ProcessingFailed",
                         event_id=event_data.eventId,
                     )

            except Exception:
                 log.exception(
                     "Unhandled exception processing event %s at offset %s.",
                     getattr(event_data, 'eventId', 'N/A'), message.offset,
                 )
                 metrics.kafka_messages_error_total.inc()
                 _dead_letter_and_commit(
                     consumer, message, "UnhandledProcessingError",
                     extra={"eventId": getattr(event_data, "eventId", None)},
                 )

    except ValidationError as e:
        log.warning(
            "Invalid TollEvent at offset %s. Error: %s. Message: %s",
            message.offset, e.errors(), message.value,
        )
        metrics.kafka_messages_error_total.inc()
        _dead_letter_and_commit(consumer, message, "ValidationError")
    except Exception:
        log.exception("Critical error handling message at offset %s.", message.offset)
        metrics.kafka_messages_error_total.inc()
        _dead_letter_and_commit(consumer, message, "CriticalError")


def _message_key(message: ConsumerRecord) -> tuple:
    return (message.topic, message.partition, message.offset)


async def _retry_or_dead_letter(consumer, message: ConsumerRecord, reason: str, event_id: str) -> None:
    """Retry a transient failure, then dead-letter it so one event cannot stall the partition."""
    key = _message_key(message)
    count = _attempt_counts.get(key, 0) + 1
    _attempt_counts[key] = count
    limit = settings.BILLING_MAX_PROCESS_ATTEMPTS
    if count >= limit:
        log.error(
            "Event %s at offset %s failed %s times. Publishing to DLQ and committing.",
            event_id, message.offset, count,
        )
        _dead_letter_and_commit(consumer, message, reason, extra={"eventId": event_id, "attempts": count})
        _attempt_counts.pop(key, None)
        return
    delay = _backoff_seconds(count)
    log.error(
        "Processing failed for event %s at offset %s (attempt %s/%s). Seeking back for retry in %.0fs.",
        event_id, message.offset, count, limit, delay,
    )
    try:
        consumer.seek(TopicPartition(message.topic, message.partition), message.offset)
    except Exception:
        log.exception("Failed to seek back to offset %s; the message will be retried after a restart.", message.offset)
    await asyncio.sleep(delay)


def _dead_letter_and_commit(consumer, message: ConsumerRecord, reason: str, extra: dict | None = None) -> None:
    try:
        kafka_client.publish_dlq(reason, message.value, message.offset, extra=extra)
    except Exception:
        log.exception("Failed to publish dead-letter record for offset %s", message.offset)
    try:
        consumer.commit()
        log.warning("Committed offset %s after %s so the partition can move on.", message.offset, reason)
    except Exception as commit_exc:
        log.error("Failed to commit Kafka offset %s after %s: %s", message.offset, reason, commit_exc, exc_info=True)
    _attempt_counts.pop(_message_key(message), None)
