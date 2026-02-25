"""
Prometheus metrics for the Billing Service.

Metrics are registered on the default registry and exposed via the
/metrics endpoint added by prometheus_fastapi_instrumentator in main.py.
"""
from prometheus_client import Counter, Histogram, Gauge

# --- Transaction lifecycle ---
transactions_created_total = Counter(
    'billing_transactions_created_total',
    'Total number of billing transactions created (new toll events received)',
)

transactions_duplicate_total = Counter(
    'billing_transactions_duplicate_total',
    'Total number of duplicate toll events skipped',
)

# --- Payment outcomes ---
payment_success_total = Counter(
    'billing_payment_success_total',
    'Total number of successful payment attempts',
)

payment_failure_total = Counter(
    'billing_payment_failure_total',
    'Total number of failed payment attempts',
    labelnames=['error_code'],
)

payment_duration_seconds = Histogram(
    'billing_payment_duration_seconds',
    'Time spent calling the payment gateway (seconds)',
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)

# --- Kafka consumer ---
kafka_messages_received_total = Counter(
    'billing_kafka_messages_received_total',
    'Total number of toll event messages received from Kafka',
)

kafka_messages_processed_total = Counter(
    'billing_kafka_messages_processed_total',
    'Total number of Kafka messages successfully processed',
)

kafka_messages_error_total = Counter(
    'billing_kafka_messages_error_total',
    'Total number of Kafka messages that could not be processed',
)
