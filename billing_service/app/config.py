import logging
from typing import Optional
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Billing Service configuration settings."""

    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False,
        extra='ignore',
    )

    # Service Binding
    BIND_HOST: str = "0.0.0.0"
    BIND_PORT: int = 8000

    # Database
    POSTGRES_HOST: str = "postgres"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "smarttoll_dev"
    POSTGRES_USER: str = "smarttoll_user"
    POSTGRES_PASSWORD: str = "changeme_in_prod_123!"
    DATABASE_URL: Optional[str] = None

    # Database connection pool
    POSTGRES_POOL_SIZE: int = 5
    POSTGRES_MAX_OVERFLOW: int = 10
    POSTGRES_POOL_TIMEOUT: int = 30

    @model_validator(mode='after')
    def assemble_db_url(self) -> 'Settings':
        if not self.DATABASE_URL:
            self.DATABASE_URL = (
                f"postgresql+psycopg2://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
                f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
            )
        return self

    # Kafka
    KAFKA_BROKER: str = "kafka:29092"
    TOLL_EVENT_TOPIC: str = "smarttoll.toll.events.v1"
    BILLING_CONSUMER_GROUP_ID: str = "billing_service_group_dev_1"
    PAYMENT_EVENT_TOPIC: str = "smarttoll.payment.events.v1"
    BILLING_DLQ_TOPIC: str = "smarttoll.billing.dlq.v1"
    # Transient processing failures are retried this many times, then dead-lettered.
    BILLING_MAX_PROCESS_ATTEMPTS: int = 5
    KAFKA_CONSUMER_RETRY_DELAY_S: float = 5.0

    # Logging
    LOG_LEVEL: str = "INFO"

    # CORS — comma-separated list of allowed origins, e.g. "https://ui.example.com,http://localhost:3000"
    # Default "*" (allow all) is safe behind an API key; restrict in production.
    CORS_ORIGINS: list[str] = ["*"]

    # Payment gateway. "mock" needs no network. "stripe" is test-mode only.
    PAYMENT_GATEWAY: str = "mock"
    STRIPE_API_KEY: Optional[str] = None
    # Both rates default to 0 so a local run is deterministic.
    # Set MOCK_PAYMENT_FAIL_RATE=0.1 to demonstrate declines.
    MOCK_PAYMENT_FAIL_RATE: float = 0.0
    MOCK_PAYMENT_TIMEOUT_RATE: float = 0.0

    # API Security
    SERVICE_API_KEY: Optional[str] = None

    # Service metadata
    SERVICE_VERSION: str = "1.0.0"

    @model_validator(mode='after')
    def validate_gateway(self) -> 'Settings':
        gateway = self.PAYMENT_GATEWAY.strip().lower()
        self.PAYMENT_GATEWAY = gateway
        if gateway not in {"mock", "stripe"}:
            raise ValueError("PAYMENT_GATEWAY must be 'mock' or 'stripe'")
        for name in ("MOCK_PAYMENT_FAIL_RATE", "MOCK_PAYMENT_TIMEOUT_RATE"):
            value = getattr(self, name)
            if value < 0.0 or value > 1.0:
                raise ValueError(f"{name} must be between 0 and 1")
        if gateway == "stripe":
            key = self.STRIPE_API_KEY or ""
            if not key.startswith(("sk_test_", "rk_test_")):
                raise ValueError(
                    "PAYMENT_GATEWAY=stripe requires a Stripe test key "
                    "(STRIPE_API_KEY starting with sk_test_ or rk_test_)"
                )
        if self.BILLING_MAX_PROCESS_ATTEMPTS < 1:
            raise ValueError("BILLING_MAX_PROCESS_ATTEMPTS must be at least 1")
        return self


settings = Settings()

# Warn immediately at import time so the misconfiguration shows up in startup logs
if not settings.SERVICE_API_KEY:
    logging.warning(
        "SERVICE_API_KEY is not set. All requests to authenticated endpoints "
        "will receive HTTP 503 until the variable is configured and the service restarted."
    )

# Log loaded settings (excluding sensitive ones)
logging.debug("Billing Service Settings Loaded:")
loggable_settings = settings.model_dump()
loggable_settings['POSTGRES_PASSWORD'] = '********'
loggable_settings['STRIPE_API_KEY'] = '********' if settings.STRIPE_API_KEY else None
loggable_settings['SERVICE_API_KEY'] = '********' if settings.SERVICE_API_KEY else None
if loggable_settings.get('DATABASE_URL'):
    loggable_settings['DATABASE_URL'] = str(loggable_settings['DATABASE_URL']).replace(
        settings.POSTGRES_PASSWORD, '********'
    )
logging.debug(loggable_settings)
