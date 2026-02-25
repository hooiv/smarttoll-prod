"""
Prometheus metrics for the Toll Processor service.

All metrics are registered on the default registry and exposed via the
health_server module which starts a separate HTTP server on METRICS_PORT.
"""
from prometheus_client import Counter, Histogram, Gauge

# --- GPS message ingestion ---
messages_received_total = Counter(
    'toll_processor_messages_received_total',
    'Total number of GPS messages received from Kafka',
)

messages_processed_success_total = Counter(
    'toll_processor_messages_processed_success_total',
    'Total number of GPS messages successfully processed',
)

messages_processed_failure_total = Counter(
    'toll_processor_messages_processed_failure_total',
    'Total number of GPS messages that failed processing',
)

gps_processing_duration_seconds = Histogram(
    'toll_processor_gps_processing_duration_seconds',
    'Time spent processing a single GPS message (seconds)',
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5),
)

# --- Toll zone events ---
zone_entries_total = Counter(
    'toll_processor_zone_entries_total',
    'Total number of toll zone entry events detected',
    labelnames=['zone_id'],
)

toll_events_published_total = Counter(
    'toll_processor_toll_events_published_total',
    'Total number of toll events successfully published to Kafka',
    labelnames=['zone_id'],
)

toll_amount_usd = Histogram(
    'toll_processor_toll_amount_usd',
    'Distribution of calculated toll amounts (USD)',
    labelnames=['zone_id'],
    buckets=(0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 50.0),
)

# --- Service health ---
service_up = Gauge(
    'toll_processor_service_up',
    '1 when the service is running, 0 when it is stopping',
)
