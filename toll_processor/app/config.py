import logging
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

# Determine if we are using Pydantic V1 or V2 style for BaseSettings
try:
    # Pydantic V2 style
    PydanticV2 = True
    SettingsConfigDictClass = SettingsConfigDict
except ImportError:
    # Pydantic V1 style
    PydanticV2 = False
    from pydantic import BaseConfig
    class SettingsConfigDictClass(BaseConfig):
        env_file = '.env'
        env_file_encoding = 'utf-8'
        case_sensitive = False
        extra = 'ignore'

class Settings(BaseSettings):
    """Application configuration settings loaded from environment variables."""

    # Kafka Configuration
    KAFKA_BROKER: str = Field(default="kafka:29092", description="Kafka broker address (internal)")
    GPS_TOPIC: str = Field(default="smarttoll.gps.raw.v1", description="Topic for raw GPS data")
    TOLL_EVENT_TOPIC: str = Field(default="smarttoll.toll.events.v1", description="Topic for calculated toll events")
    ERROR_TOPIC: str = Field(default="smarttoll.processor.errors.v1", description="Topic for processing errors")
    CONSUMER_GROUP_ID: str = Field(default="toll_processor_group_dev_1", description="Kafka consumer group ID")

    # Redis Configuration
    REDIS_HOST: str = Field(default="redis", description="Redis server host")
    REDIS_PORT: int = Field(default=6379, description="Redis server port")
    REDIS_DB: int = Field(default=0, description="Redis database number")
    VEHICLE_STATE_TTL_SECONDS: int = Field(default=6 * 3600, description="TTL for vehicle state in Redis (seconds)") # 6 hours

    # PostgreSQL Configuration
    POSTGRES_HOST: str = Field(default="postgres", description="PostgreSQL server host")
    POSTGRES_PORT: int = Field(default=5432, description="PostgreSQL server port")
    POSTGRES_DB: str = Field(default="smarttoll_dev", description="PostgreSQL database name")
    POSTGRES_USER: str = Field(default="smarttoll_user", description="PostgreSQL username")
    POSTGRES_PASSWORD: str = Field(default="changeme_in_prod_123!", description="PostgreSQL password") # Load from .env
    POSTGRES_POOL_MIN: int = Field(default=2, description="Min connections in PostgreSQL pool")
    POSTGRES_POOL_MAX: int = Field(default=10, description="Max connections in PostgreSQL pool")
    POSTGRES_CONNECT_TIMEOUT: int = Field(default=10, description="PostgreSQL connection timeout (seconds)")

    # Logging Configuration
    LOG_LEVEL: str = Field(default="INFO", description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)")

    # Processing Configuration
    DISTANCE_CALC_METHOD: str = Field(default="haversine", description="Method for distance calc ('haversine', 'postgis')") # Example setting

    # Pydantic Model Configuration
    if PydanticV2:
         model_config = SettingsConfigDictClass(
            env_file='.env',
            env_file_encoding='utf-8',
            case_sensitive=False,
            extra='ignore'
         )
    else: # Pydantic V1 compatibility
        class Config(SettingsConfigDictClass):
            pass


# Create a single instance of the settings to be imported by other modules
settings = Settings()

# Log loaded settings (excluding sensitive ones like password) at DEBUG level
logging.debug("Toll Processor Settings Loaded:")
# Create a dict representation suitable for logging, masking password
loggable_settings = settings.model_dump() if PydanticV2 else settings.dict()
loggable_settings['POSTGRES_PASSWORD'] = '********'
logging.debug(loggable_settings)
