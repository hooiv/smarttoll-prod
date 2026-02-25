import json
import logging
import os
import random
import signal
import sys
import time
import threading
from typing import Optional

from dotenv import load_dotenv
from kafka import KafkaProducer
from kafka.errors import KafkaError, NoBrokersAvailable

# --- Setup ---
# Load .env file variables into environment
# This is useful if running locally without docker-compose's env_file feature
load_dotenv(dotenv_path='../.env') # Look for .env in the parent directory

# Configure basic logging
log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("OBUSimulator")

# --- Configuration ---
# Get config from environment variables, with defaults
KAFKA_BROKER = os.environ.get("KAFKA_BROKER", "kafka:29092") # Use internal listener by default
GPS_TOPIC = os.environ.get("GPS_TOPIC", "smarttoll.gps.raw.v1")
DEVICE_ID = os.environ.get("SIM_DEVICE_ID", "OBU_SIM_DEFAULT")
VEHICLE_ID = os.environ.get("SIM_VEHICLE_ID", "VEH_SIM_DEFAULT")
SEND_INTERVAL_SECONDS = float(os.environ.get("SIM_SEND_INTERVAL_SECONDS", 5))

# --- Simulation Parameters ---
# Simulate driving along a line, passing through a defined geofence zone (approx)
# Zone is roughly between lon -74.008 to -74.002 and lat 40.705 to 40.715
START_LAT, START_LON = 40.7000, -74.0100
END_LAT, END_LON     = 40.7200, -74.0000
NUM_STEPS = int(os.environ.get("SIM_NUM_STEPS", 40)) # More steps for finer simulation through the zone
current_step = 0

# --- Global State ---
running = True
producer: Optional[KafkaProducer] = None
producer_lock = threading.Lock() # Lock for producer initialization

# --- Kafka Producer Logic ---
def _initialize_kafka_producer() -> Optional[KafkaProducer]:
    """Initializes the Kafka producer instance."""
    global producer
    logger.info(f"Attempting to initialize Kafka producer for broker: {KAFKA_BROKER}")
    try:
        # Add security settings here if Kafka requires authentication/TLS
        producer = KafkaProducer(
            bootstrap_servers=KAFKA_BROKER,
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            acks=1, # Fire-and-forget is often okay for high-volume sensor data
            retries=3,
            retry_backoff_ms=100,
            linger_ms=5 # Slight batching
        )
        logger.info("Kafka producer initialized successfully.")
        return producer
    except NoBrokersAvailable as e:
        logger.error(f"Kafka producer init failed: No brokers available at {KAFKA_BROKER}. {e}")
        producer = None
        raise
    except KafkaError as e:
        logger.error(f"Kafka producer init failed: {e}")
        producer = None
        raise
    except Exception as e:
        logger.exception("Unexpected error initializing Kafka producer.")
        producer = None
        raise

def get_kafka_producer(retry_attempts=5, retry_delay=5) -> Optional[KafkaProducer]:
    """Gets the singleton Kafka producer, initializing if necessary with retries."""
    global producer
    if producer: return producer
    with producer_lock:
        if producer: return producer # Double check inside lock
        for attempt in range(retry_attempts):
            try:
                logger.info(f"Initializing Kafka Producer (Attempt {attempt + 1}/{retry_attempts})")
                return _initialize_kafka_producer()
            except Exception:
                if attempt < retry_attempts - 1:
                    logger.warning(f"Kafka Producer initialization failed. Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                else:
                    logger.critical("Kafka Producer initialization failed after multiple attempts.")
                    raise # Critical if producer cannot be initialized
    return None

def close_kafka_producer():
    """Flushes and closes the Kafka producer."""
    global producer
    if producer:
        with producer_lock:
            if not producer: return # Check again inside lock
            try:
                logger.info("Flushing and closing Kafka producer...")
                producer.flush(timeout=10)
                producer.close(timeout=10)
                logger.info("Kafka producer closed.")
                producer = None
            except Exception:
                logger.exception("Error closing Kafka producer.")

# --- Graceful Shutdown ---
def shutdown_handler(signum, frame):
    """Signal handler to stop the simulation loop."""
    global running
    if not running: return
    logger.warning(f"Received signal {signal.Signals(signum).name}. Stopping simulator...")
    running = False

# --- Main Simulation Function ---
def run_simulation():
    global current_step, running
    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    logger.info(f"OBU Simulator starting.")
    logger.info(f"  Device ID:  {DEVICE_ID}")
    logger.info(f"  Vehicle ID: {VEHICLE_ID}")
    logger.info(f"  Target Topic: {GPS_TOPIC}")
    logger.info(f"  Target Broker: {KAFKA_BROKER}")
    logger.info(f"  Send Interval: {SEND_INTERVAL_SECONDS}s")

    prod = get_kafka_producer() # Initialize producer, retries handled internally
    if not prod:
        logger.critical("Failed to initialize Kafka producer. Cannot run simulation.")
        sys.exit(1)

    logger.info("Starting GPS simulation loop...")
    while running:
        # --- Calculate Simulated Position ---
        fraction = current_step / float(NUM_STEPS) if NUM_STEPS > 0 else 0
        lat = START_LAT + (END_LAT - START_LAT) * fraction
        lon = START_LON + (END_LON - START_LON) * fraction
        # Add slight random variation to make it less perfect
        lat += random.uniform(-0.00005, 0.00005)
        lon += random.uniform(-0.00005, 0.00005)

        # --- Create GPS Payload ---
        # Match the Pydantic model expected by the consumer (toll_processor)
        payload = {
            "deviceId": DEVICE_ID,
            "vehicleId": VEHICLE_ID,
            "timestamp": int(time.time() * 1000), # Epoch milliseconds UTC
            "latitude": round(lat, 6),
            "longitude": round(lon, 6),
            "speedKmph": round(random.uniform(30, 75), 1), # Vary speed slightly
            "heading": round(random.uniform(85, 95), 1), # Simulate mostly straight path ENE
            "altitudeMeters": round(random.uniform(15, 25), 1),
            "gpsQuality": random.randint(5, 12) # Simulate varying satellite count
        }

        # --- Send to Kafka ---
        try:
            # Use vehicleId as key to ensure messages for same vehicle go to same partition (good practice)
            message_key = VEHICLE_ID.encode('utf-8')
            logger.debug(f"Sending GPS: {payload}")
            # Send is asynchronous by default
            future = prod.send(GPS_TOPIC, value=payload, key=message_key)

            # Optional: Add callbacks for success/failure logging (non-blocking)
            # future.add_callback(on_send_success)
            # future.add_errback(on_send_error)

        except KafkaError as e:
            logger.error(f"Kafka send failed: {e}")
            # Simple backoff/retry could be added here, or rely on producer retries
            time.sleep(1) # Small sleep on error
        except Exception as e:
            logger.exception("Unexpected error sending message.")
            time.sleep(1)

        # --- Wait and Update Step ---
        try:
            # Sleep for the specified interval, but wake up early if shutdown requested
            sleep_end_time = time.monotonic() + SEND_INTERVAL_SECONDS
            while running and time.monotonic() < sleep_end_time:
                time.sleep(0.1)
        except KeyboardInterrupt:
            # Allow Ctrl+C to interrupt sleep and trigger shutdown
            shutdown_handler(signal.SIGINT, None)

        current_step = (current_step + 1) % (NUM_STEPS + 1) # Loop simulation path

    logger.info("Simulation loop finished.")

# --- Main Execution ---
if __name__ == "__main__":
    try:
        run_simulation()
    except Exception as e:
        logger.critical(f"Simulator crashed with unhandled exception: {e}", exc_info=True)
    finally:
        close_kafka_producer() # Ensure producer is closed on exit
        logger.info("OBU Simulator stopped.")
        sys.exit(0)

