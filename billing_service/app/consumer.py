import asyncio
import logging
import json
from kafka.consumer.fetcher import ConsumerRecord
from sqlalchemy.orm import sessionmaker
from pydantic import ValidationError

from app.config import settings
from app import models, billing, kafka_client, database # Relative imports

log = logging.getLogger(__name__)

async def consume_loop(db_session_factory: sessionmaker, ready_event: asyncio.Event):
    log.info("Consumer loop starting...")
    consumer_client = None
    try:
        # Get initialized consumer
        consumer_client = kafka_client.get_kafka_consumer() # This will retry
        if not consumer_client:
            log.error("Failed to get Kafka consumer after multiple retries. Exiting consume_loop.")
            # DO NOT set ready_event here if consumer failed
            return

        log.info("Kafka consumer is ready.")
        ready_event.set()
        log.info(f"consumer_ready event SET in consumer.py. is_set: {ready_event.is_set()}") # New log

        log.info(f"Starting consumption from topic '{settings.TOLL_EVENT_TOPIC}'...")
        while True:
            try:
                log.debug("Waiting for messages...")
                for message in consumer_client:
                    log.info(f"Received message - Topic: {getattr(message, 'topic', None)}, Partition: {getattr(message, 'partition', None)}, Offset: {getattr(message, 'offset', None)}, Key: {getattr(message, 'key', None)}, Value: {getattr(message, 'value', None)}")
                    await asyncio.sleep(0.01)
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
                    try:
                        consumer.commit() # Commit offset for the partition this message came from
                        log.debug(f"Committed offset {message.offset} for event {event_data.eventId}")
                    except Exception as commit_exc:
                         log.error(f"Failed to commit Kafka offset {message.offset} after processing event {event_data.eventId}: {commit_exc}", exc_info=True)
                         # This is problematic - risk of reprocessing. Alerting needed.
                else:
                     log.error(f"Processing failed for event {event_data.eventId} at offset {message.offset}. Offset not committed.")
                     # Implement retry mechanism or dead-letter queue based on requirements

            except Exception as processing_exc:
                 # Catch errors within the billing logic processing itself
                 log.exception(f"Unhandled exception processing event {getattr(event_data,'eventId','N/A')} at offset {message.offset}.")
                 # Decide if offset should be committed (to skip) or not (to retry)
                 # Committing here to avoid poison pill messages blocking the partition
                 try:
                     consumer.commit()
                     log.warning(f"Committed offset {message.offset} after unhandled processing exception to avoid blocking.")
                 except Exception as commit_exc_on_fail:
                      log.error(f"Failed to commit Kafka offset {message.offset} after processing exception: {commit_exc_on_fail}", exc_info=True)

    except ValidationError as e:
        log.warning(f"Invalid TollEvent format received at offset {message.offset}. Error: {e.errors()}. Message: {message.value}")
        # Publish to error topic?
        # Commit offset to skip invalid message
        try:
            consumer.commit()
            log.debug(f"Committed offset {message.offset} for invalid message.")
        except Exception as commit_exc_on_invalid:
             log.error(f"Failed to commit Kafka offset {message.offset} for invalid message: {commit_exc_on_invalid}", exc_info=True)
    except Exception as outer_exc:
        # Catch errors like JSON decoding issues (if deserializer fails) or others
        log.exception(f"Critical error handling message at offset {message.offset}.")
        # Decide whether to commit or not - likely not to allow retry if transient.
