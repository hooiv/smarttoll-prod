import logging
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False,
        extra='ignore',
    )

    # Kafka Configuration
    KAFKA_BROKER: str = "kafka:29092"
    GPS_TOPIC: str = "smarttoll.gps.raw.v1"
    TOLL_EVENT_TOPIC: str = "smarttoll.toll.events.v1"
    ERROR_TOPIC: str = "smarttoll.processor.errors.v1"
    CONSUMER_GROUP_ID: str = "toll_processor_group_dev_1"

    # Redis Configuration
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    VEHICLE_STATE_TTL_SECONDS: int = 6 * 3600  # 6 hours

    # PostgreSQL Configuration
    POSTGRES_HOST: str = "postgres"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "smarttoll_dev"
    POSTGRES_USER: str = "smarttoll_user"
    POSTGRES_PASSWORD: str = "changeme_in_prod_123!"
    POSTGRES_POOL_MIN: int = 2
    POSTGRES_POOL_MAX: int = 10
    POSTGRES_CONNECT_TIMEOUT: int = 10

    # Logging Configuration
    LOG_LEVEL: str = "INFO"

    # Processing Configuration
    DISTANCE_CALC_METHOD: str = "haversine"


# Create a single instance of the settings to be imported by other modules
settings = Settings()

# Log loaded settings (excluding sensitive ones) at DEBUG level
logging.debug("Toll Processor Settings Loaded:")
loggable_settings = settings.model_dump()
loggable_settings['POSTGRES_PASSWORD'] = '********'
logging.debug(loggable_settings)
