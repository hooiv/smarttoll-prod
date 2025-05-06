# kafka_client.py in billing_service
import logging
import json
import time
import threading
from typing import Optional, Dict, Any

from kafka import KafkaProducer, KafkaConsumer # Consumer also needed here
from kafka.errors import KafkaError, NoBrokersAvailable

from app.config import settings
# Import specific models if needed, or just handle dicts
# from app.models import PaymentResult

log = logging.getLogger(__name__)

_producer: Optional[KafkaProducer] = None
_consumer: Optional[KafkaConsumer] = None
_producer_lock = threading.Lock()
_consumer_lock = threading.Lock() # Lock for consumer init as well

# --- Kafka Producer ---
# (Identical initialization logic to toll_processor/app/kafka_client.py)
def _initialize_kafka_producer() -> Optional[KafkaProducer]:
    global _producer
    log.info(f"Attempting to initialize Kafka producer for brokers: {settings.KAFKA_BROKER}")
    try:
        _producer = KafkaProducer(
            bootstrap_servers=settings.KAFKA_BROKER,
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            acks='all',
            retries=5,
            retry_backoff_ms=200,
            request_timeout_ms=30000,
            linger_ms=10,
        )
        log.info("Kafka producer initialized successfully.")
        return _producer
    except NoBrokersAvailable as e:
        log.error(f"Kafka producer initialization failed: No brokers available at {settings.KAFKA_BROKER}. {e}")
        _producer = None
        raise
    except KafkaError as e:
        log.error(f"Kafka producer initialization failed: {e}")
        _producer = None
        raise
    except Exception as e:
        log.exception("Unexpected error initializing Kafka producer.")
        _producer = None
        raise

def get_kafka_producer(retry_attempts=5, retry_delay=5) -> Optional[KafkaProducer]:
    global _producer
    if _producer: return _producer
    with _producer_lock:
        if _producer: return _producer
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
                    raise
    return None

def send_message(topic: str, message: Dict[str, Any], key: Optional[bytes] = None) -> bool:
    producer = get_kafka_producer()
    if not producer:
        log.error(f"Cannot send message to topic '{topic}', producer is not available.")
        return False
    try:
        log.debug(f"Sending message to topic '{topic}': {message}")
        future = producer.send(topic, value=message, key=key)
        # Optional: future.get(timeout=...)
        return True
    except KafkaError as e:
        log.error(f"Failed to send message to Kafka topic '{topic}': {e}")
        return False
    except Exception as e:
        log.exception(f"Unexpected error sending message to topic '{topic}'.")
        return False

def close_kafka_producer():
    global _producer
    if _producer:
        with _producer_lock:
            if not _producer: return # Check again inside lock
            try:
                log.info("Flushing and closing Kafka producer...")
                _producer.flush(timeout=10)
                _producer.close(timeout=10)
                log.info("Kafka producer closed.")
                _producer = None
            except Exception:
                log.exception("Error closing Kafka producer.")

# --- Kafka Consumer ---
# (Similar initialization logic, but for the billing service consumer)
def _initialize_kafka_consumer() -> Optional[KafkaConsumer]:
    global _consumer
    log.info(f"Attempting to initialize Kafka consumer for brokers: {settings.KAFKA_BROKER}, topic: {settings.TOLL_EVENT_TOPIC}, group: {settings.BILLING_CONSUMER_GROUP_ID}")
    try:
        _consumer = KafkaConsumer(
            settings.TOLL_EVENT_TOPIC,
            bootstrap_servers=settings.KAFKA_BROKER,
            group_id=settings.BILLING_CONSUMER_GROUP_ID,
            value_deserializer=lambda v: json.loads(v.decode('utf-8', 'ignore')),
            auto_offset_reset='latest',
            enable_auto_commit=False, # Manual commits
            consumer_timeout_ms=-1, # Block indefinitely in poll (or set timeout)
            # max_poll_interval_ms=300000, # Consider heartbeat/poll interval
        )
        log.info("Kafka consumer initialized successfully.")
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
    global _consumer
    if _consumer: return _consumer
    with _consumer_lock:
        if _consumer: return _consumer
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
                    raise
    return None

def close_kafka_consumer():
    global _consumer
    if _consumer:
        with _consumer_lock:
            if not _consumer: return # Check again inside lock
            try:
                log.info("Closing Kafka consumer...")
                _consumer.close()
                log.info("Kafka consumer closed.")
                _consumer = None
            except Exception:
                log.exception("Error closing Kafka consumer.")
