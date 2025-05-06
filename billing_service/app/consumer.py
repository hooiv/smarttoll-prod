import asyncio
import logging
import json
from kafka.consumer.fetcher import ConsumerRecord
from sqlalchemy.orm import sessionmaker
from pydantic import ValidationError

from app.config import settings
from app import models, billing, kafka_client, database # Relative imports

log = logging.getLogger(__name__)

async def consume_loop(db_session_factory: sessionmaker, consumer_ready_event: asyncio.Event):
    """The main Kafka consumer loop run as an asyncio task."""
    consumer = None
    while consumer is None and not consumer_ready_event.is_set(): # Keep trying until ready or cancelled
        try:
            consumer = kafka_client.get_kafka_consumer() # Initialize/get consumer
            if consumer:
                consumer_ready_event.set() # Signal that consumer is ready
                log.info("Kafka consumer is ready.")
            else:
                await asyncio.sleep(5) # Wait before retrying init
        except Exception as e:
             log.error(f"Consumer initialization attempt failed: {e}. Retrying...")
             await asyncio.sleep(5)

    if not consumer:
        log.critical("Failed to initialize Kafka consumer after retries. Exiting consumer loop.")
        return # Exit if consumer could not be initialized

    log.info(f"Starting consumption from topic '{settings.TOLL_EVENT_TOPIC}'...")
    try:
        while True: # Main consumption loop
            try:
                # Use consume() which blocks until messages are available (better than polling with timeout in async)
                # Note: consume() might block for a long time. Need to handle shutdown gracefully.
                # A possible pattern is to use poll() with a short timeout in an async loop.
                # Let's stick to consume() for simplicity here, shutdown handled by task cancellation.
                log.debug("Waiting for messages...")
                for message in consumer: # This blocks until messages or timeout/error
                    log.debug(f"Received message: Offset={message.offset}, Partition={message.partition}, Key={message.key}")
                    await process_message(message, db_session_factory, consumer)

            except asyncio.CancelledError:
                 log.info("Consumer loop cancellation requested.")
                 break # Exit the loop cleanly on cancellation
            except Exception as e:
                 log.exception("Error in Kafka consume loop (outside message processing). Restarting consumption?")
                 # Potentially represents a deeper issue with the consumer/broker connection.
                 # Re-initializing consumer might be needed. For now, log and continue loop.
                 await asyncio.sleep(5) # Backoff before retrying consumption

    except Exception as e:
        log.critical(f"Fatal error in consumer task: {e}", exc_info=True)
    finally:
        if consumer:
            log.info("Closing Kafka consumer...")
            consumer.close() # Close the consumer connection
            log.info("Kafka consumer closed.")

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
