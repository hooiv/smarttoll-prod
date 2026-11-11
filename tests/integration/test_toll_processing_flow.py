import pytest
import time
import json
import uuid
import urllib.request
from kafka import KafkaProducer, KafkaConsumer
from redis import Redis
import psycopg2
from psycopg2.extras import RealDictCursor

# Connection settings matching docker-compose.integration.yml
KAFKA_BROKER = "localhost:9093"
REDIS_HOST = "localhost"
REDIS_PORT = 6380
PG_HOST = "localhost"
PG_PORT = 5433
PG_DB = "test_smarttoll"
PG_USER = "test_user"
PG_PASS = "test_password"

# Must match SERVICE_API_KEY in docker-compose.integration.yml
BILLING_API_KEY = "test_api_key_integration"

GPS_TOPIC = "smarttoll.gps.raw.v1"
TOLL_TOPIC = "smarttoll.toll.events.v1"
PAYMENT_TOPIC = "smarttoll.payment.events.v1"

# Explicit version avoids slow Kafka broker-version probing on startup
_KAFKA_VERSION = (3, 3, 1)

def _wait_until(check, timeout_s=120, pause_s=2):
    """Poll a dependency until it accepts a connection or the deadline passes."""
    deadline = time.time() + timeout_s
    last_error = None
    while time.time() < deadline:
        try:
            check()
            return
        except Exception as exc:
            last_error = exc
            time.sleep(pause_s)
    raise RuntimeError(f"dependency not ready after {timeout_s}s: {last_error}")


@pytest.fixture(scope="module", autouse=True)
def wait_for_services():
    def _kafka():
        KafkaProducer(
            bootstrap_servers=KAFKA_BROKER, api_version=_KAFKA_VERSION, request_timeout_ms=5000,
        ).close()

    def _redis():
        Redis(host=REDIS_HOST, port=REDIS_PORT, socket_connect_timeout=5).ping()

    def _postgres():
        conn = psycopg2.connect(
            host=PG_HOST, port=PG_PORT, dbname=PG_DB, user=PG_USER, password=PG_PASS, connect_timeout=5,
        )
        conn.close()

    _wait_until(_kafka)
    _wait_until(_redis)
    _wait_until(_postgres)

@pytest.fixture(scope="module")
def kafka_producer():
    prod = KafkaProducer(
        bootstrap_servers=KAFKA_BROKER,
        api_version=_KAFKA_VERSION,
        value_serializer=lambda v: json.dumps(v).encode(),
        key_serializer=lambda k: k.encode()
    )
    yield prod
    prod.close()

@pytest.fixture(scope="module")
def toll_consumer():
    cons = KafkaConsumer(
        TOLL_TOPIC,
        bootstrap_servers=KAFKA_BROKER,
        api_version=_KAFKA_VERSION,
        group_id=f"test-toll-{uuid.uuid4().hex}",
        auto_offset_reset='earliest',
        consumer_timeout_ms=10000,
        value_deserializer=lambda v: json.loads(v.decode())
    )
    yield cons
    cons.close()

@pytest.fixture(scope="module")
def payment_consumer():
    cons = KafkaConsumer(
        PAYMENT_TOPIC,
        bootstrap_servers=KAFKA_BROKER,
        api_version=_KAFKA_VERSION,
        group_id=f"test-pay-{uuid.uuid4().hex}",
        auto_offset_reset='earliest',
        consumer_timeout_ms=15000,
        value_deserializer=lambda v: json.loads(v.decode())
    )
    yield cons
    cons.close()

@pytest.fixture(scope="function")
def db_conn():
    conn = psycopg2.connect(host=PG_HOST, port=PG_PORT, dbname=PG_DB, user=PG_USER, password=PG_PASS)
    conn.autocommit = False
    with conn.cursor() as cur:
        cur.execute("CREATE EXTENSION IF NOT EXISTS postgis;")
        # Ensure required tables exist for integration tests
        cur.execute("""
            CREATE TABLE IF NOT EXISTS billing_transactions (
                id SERIAL PRIMARY KEY,
                toll_event_id VARCHAR NOT NULL UNIQUE,
                vehicle_id VARCHAR NOT NULL,
                amount DOUBLE PRECISION NOT NULL,
                currency VARCHAR(3) NOT NULL,
                status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
                transaction_time TIMESTAMPTZ DEFAULT now() NOT NULL,
                last_updated TIMESTAMPTZ DEFAULT now(),
                payment_gateway_ref VARCHAR,
                payment_method_details VARCHAR,
                error_message VARCHAR,
                retry_count INTEGER NOT NULL DEFAULT 0
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS toll_zones (
                zone_id VARCHAR PRIMARY KEY,
                zone_name VARCHAR,
                rate_per_km DOUBLE PRECISION,
                geom geometry
            );
        """)
        cur.execute("TRUNCATE billing_transactions RESTART IDENTITY CASCADE;")
        cur.execute("DELETE FROM toll_zones;")
        cur.execute("ALTER TABLE toll_zones ADD COLUMN IF NOT EXISTS flat_fee_inr DOUBLE PRECISION;")
        cur.execute("INSERT INTO toll_zones(zone_id, zone_name, rate_per_km, flat_fee_inr, geom) VALUES (%s,%s,%s,%s, ST_GeomFromEWKT(%s))",
                    ('NH48-KHERKI','Kherki Daula',0,105,
                     'SRID=4326;POLYGON((76.988538 28.398242, 76.979908 28.389350, 76.975555 28.392620, 76.984184 28.401512, 76.988538 28.398242))'))
    conn.commit()
    yield conn
    conn.close()

@pytest.fixture(scope="function")
def redis_client():
    cli = Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)
    cli.flushdb()
    yield cli
    cli.flushdb()


def _next_where(consumer, predicate, limit=40):
    """Skip events from the always-on simulator and return the first match."""
    for _ in range(limit):
        message = next(consumer, None)
        if message is None:
            return None
        if predicate(message.value):
            return message
    return None


def test_full_flow(kafka_producer, toll_consumer, payment_consumer, db_conn, redis_client):
    vehicle_id = f"veh_{uuid.uuid4().hex[:6]}"
    device_id = "dev123"
    t0 = int(time.time() * 1000)
    # Inside the Kherki Daula capture polygon, then southwest of it on NH-48.
    enter = {"deviceId": device_id, "vehicleId": vehicle_id, "timestamp": t0, "latitude": 28.39543, "longitude": 76.98205, "speedKmph": 70}
    exit = {"deviceId": device_id, "vehicleId": vehicle_id, "timestamp": t0 + 10000, "latitude": 28.36174, "longitude": 76.93575, "speedKmph": 70}

    kafka_producer.send(GPS_TOPIC, key=vehicle_id, value=enter);
    kafka_producer.flush();
    time.sleep(1)
    kafka_producer.send(GPS_TOPIC, key=vehicle_id, value=exit);
    kafka_producer.flush();

    toll_msg = _next_where(toll_consumer, lambda event: event.get("vehicleId") == vehicle_id)
    assert toll_msg, "Toll event not received"
    te = toll_msg.value
    assert te['vehicleId'] == vehicle_id
    assert te['zoneId'] == 'NH48-KHERKI'

    payment_msg = _next_where(payment_consumer, lambda event: event.get("eventId") == te["eventId"])
    assert payment_msg, "Payment event not received"
    pe = payment_msg.value
    assert pe['eventId'] == te['eventId']
    assert pe['status'] in ["SUCCESS","FAILED"]

    # check DB
    with db_conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT * FROM billing_transactions WHERE toll_event_id = %s", (te['eventId'],))
        rec = cur.fetchone()
    assert rec['vehicle_id'] == vehicle_id
    assert rec['status'] == pe['status']

    # redis state cleared
    assert redis_client.get(f"vehicle_state:{vehicle_id}") is None

    # The operations console reads these same HTTP resources.
    ledger_request = urllib.request.Request(
        f"http://127.0.0.1:18001/api/v1/transactions?vehicle_id={vehicle_id}",
        headers={"X-API-KEY": BILLING_API_KEY},
    )
    with urllib.request.urlopen(ledger_request, timeout=10) as response:
        ledger = json.loads(response.read().decode())
    assert ledger["total"] >= 1
    assert ledger["items"][0]["vehicle_id"] == vehicle_id
    assert ledger["items"][0]["currency"] == "INR"
    assert ledger["items"][0]["toll_event_id"] == te["eventId"]

    summary_request = urllib.request.Request(
        "http://127.0.0.1:18001/api/v1/transactions/summary",
        headers={"X-API-KEY": BILLING_API_KEY},
    )
    with urllib.request.urlopen(summary_request, timeout=10) as response:
        summary = json.loads(response.read().decode())
    assert summary["total"] >= 1

    stream_request = urllib.request.Request(
        "http://127.0.0.1:18001/api/v1/stream",
        headers={"X-API-KEY": BILLING_API_KEY},
    )
    with urllib.request.urlopen(stream_request, timeout=10) as response:
        opened = response.readline().decode()
    assert "hello" in opened

    with urllib.request.urlopen("http://127.0.0.1:18080/zones", timeout=10) as response:
        zones = json.loads(response.read().decode())
    assert any(zone["zoneId"] == "NH48-KHERKI" for zone in zones["zones"])