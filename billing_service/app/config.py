import logging
from typing import Optional, Any
from pydantic import field_validator, model_validator
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
    KAFKA_CONSUMER_RETRY_DELAY_S: float = 5.0

    # Logging
    LOG_LEVEL: str = "INFO"

    # CORS — comma-separated list of allowed origins, e.g. "https://ui.example.com,http://localhost:3000"
    # Default "*" (allow all) is safe behind an API key; restrict in production.
    CORS_ORIGINS: list[str] = ["*"]

    # Payment Gateway (Mock settings)
    MOCK_PAYMENT_FAIL_RATE: float = 0.1

    # API Security
    SERVICE_API_KEY: Optional[str] = None


settings = Settings()

# Log loaded settings (excluding sensitive ones)
logging.debug("Billing Service Settings Loaded:")
loggable_settings = settings.model_dump()
loggable_settings['POSTGRES_PASSWORD'] = '********'
if loggable_settings.get('DATABASE_URL'):
    loggable_settings['DATABASE_URL'] = str(loggable_settings['DATABASE_URL']).replace(
        settings.POSTGRES_PASSWORD, '********'
    )
logging.debug(loggable_settings)
