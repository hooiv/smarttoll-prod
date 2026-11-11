import json
import logging
import math
import os
import random
import signal
import sys
import time
import threading
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Optional
from urllib.parse import urlparse

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
DEVICE_ID = os.environ.get("SIM_DEVICE_ID", "OBU-HR26DK8481")
VEHICLE_ID = os.environ.get("SIM_VEHICLE_ID", "HR26DK8481")
SEND_INTERVAL_SECONDS = float(os.environ.get("SIM_SEND_INTERVAL_SECONDS", 5))

# NH-48 driving trace from Mahipalpur (Delhi) past Kherki Daula to the
# Shahjahanpur plaza near Neemrana. Thinned from an OSRM trace so the car
# stays on the highway. The last point is beyond the Shahjahanpur booth so
# the crossing is an entry and an exit, which is what produces a charge.
NH48_ROUTE = [
    (28.54265, 77.11848),
    (28.53396, 77.10874),
    (28.52277, 77.09909),
    (28.50933, 77.09438),
    (28.49810, 77.08879),
    (28.48150, 77.07287),
    (28.47123, 77.06071),
    (28.46172, 77.05145),
    (28.44917, 77.03944),
    (28.44740, 77.02628),
    (28.43943, 77.01323),
    (28.42412, 77.00036),
    (28.41029, 76.99275),
    (28.40004, 76.98636),
    (28.39543, 76.98205),
    (28.38955, 76.97618),
    (28.38176, 76.96683),
    (28.37434, 76.95234),
    (28.36229, 76.94083),
    (28.34896, 76.93890),
    (28.33676, 76.93678),
    (28.33720, 76.92443),
    (28.33009, 76.91461),
    (28.32347, 76.90033),
    (28.31166, 76.88581),
    (28.30226, 76.87440),
    (28.30174, 76.86122),
    (28.28699, 76.85877),
    (28.27736, 76.84691),
    (28.27005, 76.83424),
    (28.25951, 76.82652),
    (28.24839, 76.81755),
    (28.23721, 76.80925),
    (28.22590, 76.80093),
    (28.21525, 76.79507),
    (28.20599, 76.78677),
    (28.20422, 76.77447),
    (28.20550, 76.75719),
    (28.19966, 76.74587),
    (28.19171, 76.73014),
    (28.18286, 76.71752),
    (28.16900, 76.69788),
    (28.15714, 76.68110),
    (28.14675, 76.66649),
    (28.13754, 76.65371),
    (28.12674, 76.63860),
    (28.11893, 76.62758),
    (28.11118, 76.61571),
    (28.10274, 76.60398),
    (28.09461, 76.59155),
    (28.08579, 76.57842),
    (28.07804, 76.56709),
    (28.07963, 76.54981),
    (28.06296, 76.54447),
    (28.05548, 76.53329),
    (28.04641, 76.51968),
    (28.03944, 76.50922),
    (28.03186, 76.49819),
    (28.02266, 76.48484),
    (28.01291, 76.46982),
    (28.00506, 76.45795),
    (28.00383, 76.43861),
    (27.99968, 76.43067),
    (27.98928, 76.41663),
]
NUM_STEPS = int(os.environ.get("SIM_NUM_STEPS", 160))
current_step = 0


def _segment_lengths(route):
    lengths = []
    for (lat1, lon1), (lat2, lon2) in zip(route, route[1:]):
        # Equirectangular metres, enough to space samples along the trace.
        mean_lat = math.radians((lat1 + lat2) / 2)
        dx = math.radians(lon2 - lon1) * math.cos(mean_lat) * 6371000
        dy = math.radians(lat2 - lat1) * 6371000
        lengths.append(math.hypot(dx, dy))
    return lengths


_SEGMENT_LENGTHS = _segment_lengths(NH48_ROUTE)
_ROUTE_LENGTH = sum(_SEGMENT_LENGTHS) or 1.0


def point_along_route(fraction: float):
    """Return lat, lon, heading for a fraction in [0, 1] along NH48_ROUTE."""
    target = max(0.0, min(1.0, fraction)) * _ROUTE_LENGTH
    walked = 0.0
    for (lat1, lon1), (lat2, lon2), length in zip(NH48_ROUTE, NH48_ROUTE[1:], _SEGMENT_LENGTHS):
        if walked + length >= target or length == 0:
            t = 0 if length == 0 else (target - walked) / length
            lat = lat1 + (lat2 - lat1) * t
            lon = lon1 + (lon2 - lon1) * t
            heading = (math.degrees(math.atan2(lon2 - lon1, lat2 - lat1)) + 360) % 360
            return lat, lon, heading
        walked += length
    lat, lon = NH48_ROUTE[-1]
    return lat, lon, 220.0

# --- Global State ---
running = True
producer: Optional[KafkaProducer] = None
producer_lock = threading.Lock() # Lock for producer initialization
producer_connected = threading.Event()
HEALTH_PORT = int(os.environ.get("SIM_HEALTH_PORT", "8082"))


class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/health/live":
            self._send(200, {"status": "live"})
        elif path == "/health/ready":
            ready = producer_connected.is_set()
            self._send(200 if ready else 503, {"status": "ready" if ready else "not ready"})
        else:
            self._send(404, {"status": "not found"})

    def _send(self, code, data):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        return


def start_health_server():
    def _serve():
        try:
            httpd = HTTPServer(("0.0.0.0", HEALTH_PORT), _HealthHandler)
            logger.info("Simulator health server listening on port %s", HEALTH_PORT)
            httpd.serve_forever()
        except Exception:
            logger.exception("Simulator health server failed")
    threading.Thread(target=_serve, name="sim-health", daemon=True).start()

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
            linger_ms=5, # Slight batching
            api_version=(3, 3, 1) # Explicit version avoids slow broker-probing on startup
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
    except Exception:
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

    logger.info("OBU Simulator starting.")
    logger.info(f"  Device ID:  {DEVICE_ID}")
    logger.info(f"  Vehicle ID: {VEHICLE_ID}")
    logger.info(f"  Target Topic: {GPS_TOPIC}")
    logger.info(f"  Target Broker: {KAFKA_BROKER}")
    logger.info(f"  Send Interval: {SEND_INTERVAL_SECONDS}s")
    start_health_server()

    prod = None
    attempt = 0
    while running and prod is None:
        attempt += 1
        try:
            prod = get_kafka_producer(retry_attempts=1)
        except Exception:
            delay = min(15, 2 ** min(attempt, 4))
            logger.warning("Kafka not ready (attempt %s). Retrying in %ss.", attempt, delay)
            time.sleep(delay)
            prod = None
    if not running or prod is None:
        logger.warning("Simulator stopping before Kafka became ready.")
        return
    producer_connected.set()

    logger.info("Starting GPS simulation loop...")
    while running:
        # --- Calculate Simulated Position ---
        fraction = current_step / float(NUM_STEPS) if NUM_STEPS > 0 else 0
        lat, lon, heading = point_along_route(fraction)
        # A few metres of GPS noise, not enough to leave the carriageway.
        lat += random.uniform(-0.00003, 0.00003)
        lon += random.uniform(-0.00003, 0.00003)

        # --- Create GPS Payload ---
        # Match the Pydantic model expected by the consumer (toll_processor)
        payload = {
            "deviceId": DEVICE_ID,
            "vehicleId": VEHICLE_ID,
            "traceId": str(uuid.uuid4()),
            "timestamp": int(time.time() * 1000), # Epoch milliseconds UTC
            "latitude": round(lat, 6),
            "longitude": round(lon, 6),
            "speedKmph": round(random.uniform(50, 80), 1),
            "heading": round((heading + random.uniform(-4, 4)) % 360, 1),
            "altitudeMeters": round(random.uniform(15, 25), 1),
            "gpsQuality": random.randint(5, 12) # Simulate varying satellite count
        }

        # --- Send to Kafka ---
        try:
            # Use vehicleId as key to ensure messages for same vehicle go to same partition (good practice)
            message_key = VEHICLE_ID.encode('utf-8')
            logger.debug(f"Sending GPS: {payload}")
            prod.send(GPS_TOPIC, value=payload, key=message_key)
            # Add future.add_callback / future.add_errback here for async delivery confirmation if needed

        except KafkaError as e:
            logger.error(f"Kafka send failed: {e}")
            # Simple backoff/retry could be added here, or rely on producer retries
            time.sleep(1)  # Small sleep on error
        except Exception:
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

