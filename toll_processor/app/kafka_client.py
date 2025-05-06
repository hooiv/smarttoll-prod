import logging
import json
import time
import threading
from typing import Optional, Any, Dict

from kafka import KafkaConsumer, KafkaProducer
from kafka.errors import KafkaError, NoBrokersAvailable

from app.config import settings
from app.models import ErrorMessage # Import error model

log = logging.getLogger(__name__)

_producer: Optional[KafkaProducer] = None
_consumer: Optional[KafkaConsumer] = None
_producer_lock = threading.Lock()
_consumer_lock = threading.Lock()

# --- Kafka Producer ---

def _initialize_kafka_producer() -> Optional[KafkaProducer]:
    """Initializes the Kafka producer instance."""
    global _producer
    log.info(f"Attempting to initialize Kafka producer for brokers: {settings.KAFKA_BROKER}")
    try:
        # Add security protocol settings here if needed based on Kafka setup
        # Example:
        # security_protocol="SASL_SSL",
        # sasl_mechanism="PLAIN",
        # sasl_plain_username="user",
        # sasl_plain_password="password",
        # ssl_cafile='/path/to/ca.crt' # Example for TLS
        _producer = KafkaProducer(
            bootstrap_servers=settings.KAFKA_BROKER,
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            acks='all', # Wait for all in-sync replicas to acknowledge
            retries=5,  # Retry on transient errors
            retry_backoff_ms=200, # Wait longer between retries
            request_timeout_ms=30000, # Timeout for producer requests
            linger_ms=10, # Batch messages slightly for better throughput
            # api_version_auto_timeout_ms=10000 # May help with broker version detection issues
        )
        log.info("Kafka producer initialized successfully.")
        return _producer
    except NoBrokersAvailable as e:
        log.error(f"Kafka producer initialization failed: No brokers available at {settings.KAFKA_BROKER}. {e}")
        _producer = None
        raise # Re-raise critical error
    except KafkaError as e:
        log.error(f"Kafka producer initialization failed: {e}")
        _producer = None
        raise
    except Exception as e:
        log.exception("Unexpected error initializing Kafka producer.")
        _producer = None
        raise

def get_kafka_producer(retry_attempts=5, retry_delay=5) -> Optional[KafkaProducer]:
    """Gets the singleton Kafka producer, initializing if necessary with retries."""
    global _producer
    if _producer:
        return _producer

    with _producer_lock:
        # Double-check after acquiring lock
        if _producer:
            return _producer

        for attempt in range(retry_attempts):
            try:
                log.info(f"Initializing Kafka Producer (Attempt {attempt + 1}/{retry_attempts})")
                return _initialize_kafka_producer()
            except Exception:
                if attempt < retry_attempts - 1:
                    log.warning(f"Kafka Producer initialization failed. Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                else:
                    log.critical("Kafka Producer initialization failed after multiple attempts.")
                    raise # Re-raise the last exception
    return None # Should not be reached

def send_message(topic: str, message: Dict[str, Any], key: Optional[bytes] = None) -> bool:
    """Sends a message to the specified Kafka topic."""
    producer = get_kafka_producer()
    if not producer:
        log.error(f"Cannot send message to topic '{topic}', producer is not available.")
        return False

    try:
        log.debug(f"Sending message to topic '{topic}': {message}")
        future = producer.send(topic, value=message, key=key)
        # Optional: Wait for confirmation (blocks, reduces throughput)
        # record_metadata = future.get(timeout=10)
        # log.debug(f"Message sent to {record_metadata.topic} partition {record_metadata.partition} offset {record_metadata.offset}")
        # producer.flush() # Flush periodically in main loop or on shutdown instead
        return True
    except KafkaError as e:
        log.error(f"Failed to send message to Kafka topic '{topic}': {e}")
        # Consider metrics/alerting here
        return False
    except Exception as e:
        log.exception(f"Unexpected error sending message to topic '{topic}'.")
        return False

def publish_error(error_type: str, message: str, exc: Optional[Exception] = None, original_msg: Optional[dict] = None, context: Optional[dict] = None):
    """Helper to publish structured errors to the designated error topic."""
    import traceback
    error_payload = ErrorMessage(
        error_type=error_type,
        message=message,
        traceback=traceback.format_exc() if exc else None,
        original_message=original_msg,
        context=context
    )
    # success = send_message(settings.ERROR_TOPIC, error_payload.dict()) # Pydantic V1
    success = send_message(settings.ERROR_TOPIC, error_payload.model_dump()) # Pydantic V2
    if not success:
        log.error("CRITICAL: Failed to publish error message to Kafka error topic!")

def close_kafka_producer():
    """Flushes and closes the Kafka producer."""
    global _producer
    if _producer:
        with _producer_lock:
            try:
                log.info("Flushing and closing Kafka producer...")
                _producer.flush(timeout=10) # Wait up to 10s for buffer to clear
                _producer.close(timeout=10)
                log.info("Kafka producer closed.")
                _producer = None
            except Exception:
                log.exception("Error closing Kafka producer.")


# --- Kafka Consumer ---

def _initialize_kafka_consumer() -> Optional[KafkaConsumer]:
    """Initializes the Kafka consumer instance."""
    global _consumer
    log.info(f"Attempting to initialize Kafka consumer for brokers: {settings.KAFKA_BROKER}, topic: {settings.GPS_TOPIC}, group: {settings.CONSUMER_GROUP_ID}")
    try:
        # Add security protocol settings here if needed (match producer)
        _consumer = KafkaConsumer(
            settings.GPS_TOPIC,
            bootstrap_servers=settings.KAFKA_BROKER,
            group_id=settings.CONSUMER_GROUP_ID,
            value_deserializer=lambda v: json.loads(v.decode('utf-8', 'ignore')), # Handle potential decode errors gracefully
            auto_offset_reset='latest', # Process new messages. Use 'earliest' to process from beginning.
            enable_auto_commit=False, # CRITICAL: Use manual commits
            consumer_timeout_ms=1000, # Timeout for poll() to allow checking shutdown flag
            # fetch_max_wait_ms=500, # How long poll waits if no data
            # max_poll_records=100, # Max records per poll
            # max_poll_interval_ms=300000, # Max time between polls before considered dead (5 mins)
            # security_protocol="SASL_SSL", # Example
            # ... other security settings
        )
        log.info("Kafka consumer initialized successfully.")
        # Log assigned partitions (optional, may take a moment after init)
        # partitions = _consumer.partitions_for_topic(settings.GPS_TOPIC)
        # log.info(f"Partitions assigned for topic {settings.GPS_TOPIC}: {partitions}")
        return _consumer
    except NoBrokersAvailable as e:
        log.error(f"Kafka consumer initialization failed: No brokers available at {settings.KAFKA_BROKER}. {e}")
        _consumer = None
        raise
    except KafkaError as e:
        log.error(f"Kafka consumer initialization failed: {e}")
        _consumer = None
        raise
    except Exception as e:
        log.exception("Unexpected error initializing Kafka consumer.")
        _consumer = None
        raise

def get_kafka_consumer(retry_attempts=5, retry_delay=5) -> Optional[KafkaConsumer]:
    """Gets the singleton Kafka consumer, initializing if necessary with retries."""
    global _consumer
    if _consumer:
        return _consumer # Assume consumer is usable if initialized (rebalancing handled by kafka-python)

    with _consumer_lock:
        # Double-check after acquiring lock
        if _consumer:
            return _consumer

        for attempt in range(retry_attempts):
            try:
                log.info(f"Initializing Kafka Consumer (Attempt {attempt + 1}/{retry_attempts})")
                return _initialize_kafka_consumer()
            except Exception:
                if attempt < retry_attempts - 1:
                    log.warning(f"Kafka Consumer initialization failed. Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                else:
                    log.critical("Kafka Consumer initialization failed after multiple attempts.")
                    raise # Re-raise the last exception
    return None # Should not be reached

def close_kafka_consumer():
    """Closes the Kafka consumer."""
    global _consumer
    if _consumer:
        with _consumer_lock:
            try:
                log.info("Closing Kafka consumer...")
                _consumer.close()
                log.info("Kafka consumer closed.")
                _consumer = None
            except Exception:
                log.exception("Error closing Kafka consumer.")
