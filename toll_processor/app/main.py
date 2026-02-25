import logging
import signal
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, Future

from kafka.errors import KafkaError

# Initialize logging and settings first
from app.config import settings  # noqa F401
from app.logging_config import setup_logging
setup_logging()
from app import kafka_client, database, state, processing, health_server, metrics
from app.database import init_db_schema

log = logging.getLogger(__name__)

# --- Global State ---
running = True
consumer_thread = None
consumer_future = None

# --- Graceful Shutdown ---
def shutdown_handler(signum, frame):
    """Signal handler for SIGINT and SIGTERM."""
    global running
    if not running: # Avoid double shutdown calls
        return
    log.warning(f"Received signal {signal.Signals(signum).name}. Initiating graceful shutdown...")
    running = False
    # Note: Further cleanup happens in the main loop's finally block

def main_consumer_loop():
    """The main loop executed by the consumer thread."""
    global running
    log.info("Consumer thread started.")

    consumer = None
    try:
        consumer = kafka_client.get_kafka_consumer()
        if not consumer:
            log.critical("Failed to get Kafka consumer. Exiting thread.")
            running = False # Signal main thread to exit
            return

        log.info(f"Starting consumption from topic '{settings.GPS_TOPIC}'...")
        while running:
            try:
                # Poll for messages with a timeout
                message_pack = consumer.poll(timeout_ms=1000, max_records=100) # Adjust max_records based on processing time

                if not message_pack and running:
                    # No messages, loop continues to check running flag
                    log.debug("No messages received in poll interval.")
                    continue
                elif not running:
                    log.info("Shutdown signal received during poll, exiting loop.")
                    break

                if not kafka_client.consumer_ready.is_set():
                    kafka_client.consumer_ready.set()
                    log.info("Kafka consumer marked as READY (first batch received or poll succeeded)")
                
                for tp, messages in message_pack.items():
                    log.info(f"Processing batch of {len(messages)} messages from partition {tp.partition}")
                    commit_needed = False
                    last_processed_offset = -1

                    # --- Process Messages in Batch ---
                    for message in messages:
                        if not running:
                            log.info("Shutdown signal received during batch processing.")
                            break # Exit inner message loop

                        try:
                            # Process the message using the core logic function
                            metrics.messages_received_total.inc()
                            success = processing.process_gps_message(message.value, message.offset)
                            if success:
                                commit_needed = True
                                last_processed_offset = message.offset
                                metrics.messages_processed_success_total.inc()
                            else:
                                log.error(f"Processing function indicated failure for message at offset {message.offset}. Check logs.")
                                metrics.messages_processed_failure_total.inc()

                        except Exception as e:
                            # Catch unexpected errors during the call to process_gps_message itself
                            log.exception(f"Critical unexpected error processing message at offset {message.offset}.")
                            kafka_client.publish_error(
                                error_type="UnhandledProcessingError",
                                message=str(e),
                                exc=e,
                                original_msg=message.value, # Assuming value is dict-like after deserialization
                                context={"offset": message.offset}
                            )
                            # Decide if this is fatal or skippable. Let's assume skippable for now.
                            commit_needed = True # Allow committing past this potentially poisonous message
                            last_processed_offset = message.offset

                    # --- Manual Offset Commit (after processing batch for a partition) ---
                    if commit_needed and last_processed_offset >= 0:
                        try:
                            # Commit up to the offset *after* the last successfully processed message
                            # Note: Committing per partition isn't directly supported by kafka-python's commit() easily.
                            # consumer.commit() commits the offsets for all partitions fetched in the last poll.
                            # This is generally safe if processing is relatively fast and errors don't block.
                            # For more precise control, manual offset management per partition is needed.
                            consumer.commit()
                            log.info(f"Committed offsets for partitions processed in last poll (up to ~offset {last_processed_offset} for partition {tp.partition}).")
                        except KafkaError as e:
                             log.error(f"Failed to commit Kafka offsets: {e}", exc_info=True)
                             # This is serious - may lead to reprocessing. Consider shutdown/alerting.
                             # running = False # Optional: trigger shutdown on commit failure
                        except Exception as e:
                             log.exception("Unexpected error during Kafka commit.")
                             # running = False

                    if not running: break # Exit partition loop if shutdown requested

            except KafkaError as e:
                 log.error(f"Kafka error during poll/consume loop: {e}", exc_info=True)
                 # Depending on error, might need to re-initialize consumer or back off
                 time.sleep(5) # Basic backoff
            except Exception as e:
                 log.exception("Unhandled exception in consumer loop.")
                 # Consider if this should trigger shutdown
                 time.sleep(1) # Prevent tight loop on unexpected errors

    except Exception as e:
        log.critical(f"Consumer thread encountered a fatal error: {e}", exc_info=True)
        running = False # Signal main thread to exit
    finally:
        log.info("Consumer thread finishing.")
        # Cleanup is handled by the main thread's finally block


def run_service():
    """Initializes resources and starts the main consumer loop in a thread."""
    global running, consumer_thread, consumer_future
    # Setup signal handlers
    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    log.info("Starting SmartToll Toll Processor Service...")
    metrics.service_up.set(1)

    # Initialize external dependencies (retry logic is within the getters)
    try:
        kafka_client.get_kafka_producer() # Init producer early
        kafka_client.get_kafka_consumer() # Init consumer
        database.get_db_pool()            # Init DB pool
        init_db_schema()                  # Ensure schema/tables exist
        state.get_redis_client()          # Init Redis client
    except Exception as e:
        log.critical(f"Failed to initialize critical dependencies during startup: {e}", exc_info=True)
        sys.exit(1) # Exit if essential services can't be reached

    log.info("Dependencies initialized. Starting consumer thread...")
    health_server.start_health_server()

    # Use ThreadPoolExecutor to easily get exceptions from the thread
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="KafkaConsumerThread")
    consumer_future = executor.submit(main_consumer_loop)

    # Keep main thread alive, checking consumer status and running flag
    try:
        while running:
            if consumer_future and consumer_future.done():
                log.error("Consumer thread terminated unexpectedly.")
                try:
                    # Retrieve exception from the future, if any
                    exception = consumer_future.exception()
                    if exception:
                        log.critical(f"Consumer thread failed with exception: {exception}", exc_info=exception)
                except Exception as e:
                    log.error(f"Could not retrieve exception from consumer future: {e}")
                running = False # Trigger shutdown if consumer thread dies
                break
            time.sleep(1) # Check status every second

    except KeyboardInterrupt:
         log.warning("Keyboard interrupt received in main thread.")
         shutdown_handler(signal.SIGINT, None)
    finally:
         log.info("Main thread initiating final cleanup...")
         # Signal consumer thread to stop if it hasn't already
         running = False
         # Wait for consumer thread to finish (with timeout)
         if consumer_future:
              log.info("Waiting for consumer thread to complete...")
              try:
                  consumer_future.result(timeout=15) # Wait up to 15 seconds
                  log.info("Consumer thread completed.")
              except TimeoutError:
                  log.warning("Consumer thread did not complete within timeout.")
              except Exception as e:
                   log.error(f"Exception retrieving consumer future result during shutdown: {e}")

         executor.shutdown(wait=False) # Shutdown executor

         # Close resources
         health_server.stop_health_server()
         kafka_client.close_kafka_consumer()
         kafka_client.close_kafka_producer()
         database.close_db_pool()
         state.close_redis_client()
         metrics.service_up.set(0)
         log.info("SmartToll Toll Processor Service stopped.")

if __name__ == "__main__":
    run_service()
