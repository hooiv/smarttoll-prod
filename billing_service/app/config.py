import logging
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, PostgresDsn, validator
from typing import Optional, Any

# Determine Pydantic version
try:
    PydanticV2 = True
    SettingsConfigDictClass = SettingsConfigDict
except ImportError:
    PydanticV2 = False
    from pydantic import BaseConfig
    class SettingsConfigDictClass(BaseConfig):
        env_file = '.env'
        env_file_encoding = 'utf-8'
        case_sensitive = False
        extra = 'ignore'

class Settings(BaseSettings):
    """Billing Service configuration settings."""

    # Service Binding
    BIND_HOST: str = Field(default="0.0.0.0", description="Host for the API server to bind to")
    BIND_PORT: int = Field(default=8000, description="Port for the API server to bind to")

    # Database (using URL format preferred by SQLAlchemy)
    # Construct the URL from individual components for flexibility
    POSTGRES_HOST: str = Field(default="postgres")
    POSTGRES_PORT: int = Field(default=5432)
    POSTGRES_DB: str = Field(default="smarttoll_dev")
    POSTGRES_USER: str = Field(default="smarttoll_user")
    POSTGRES_PASSWORD: str = Field(default="changeme_in_prod_123!") # Load from .env
    # Assembled Database URL (calculated property)
    DATABASE_URL: Optional[PostgresDsn] = None # Optional allows validator to set it

    @validator('DATABASE_URL', pre=True, always=True)
    def assemble_db_connection(cls, v: Optional[str], values: dict[str, Any]) -> Any:
        if isinstance(v, str):
            # If DATABASE_URL is explicitly set, use it
            return v
        # Otherwise, construct it from components
        return PostgresDsn.build(
            scheme="postgresql+psycopg2", # Driver
            username=values.get("POSTGRES_USER"),
            password=values.get("POSTGRES_PASSWORD"),
            host=values.get("POSTGRES_HOST"),
            port=str(values.get("POSTGRES_PORT")),
            path=f"/{values.get('POSTGRES_DB') or ''}",
        )

    # Kafka
    KAFKA_BROKER: str = Field(default="kafka:29092")
    TOLL_EVENT_TOPIC: str = Field(default="smarttoll.toll.events.v1")
    BILLING_CONSUMER_GROUP_ID: str = Field(default="billing_service_group_dev_1")
    PAYMENT_EVENT_TOPIC: str = Field(default="smarttoll.payment.events.v1")

    # Logging
    LOG_LEVEL: str = Field(default="INFO")

    # Payment Gateway (Mock settings)
    MOCK_PAYMENT_FAIL_RATE: float = Field(default=0.1, ge=0.0, le=1.0, description="Probability (0-1) of mock payment failure")

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


settings = Settings()

# Log loaded settings (excluding sensitive ones)
logging.debug("Billing Service Settings Loaded:")
loggable_settings = settings.model_dump() if PydanticV2 else settings.dict()
loggable_settings['POSTGRES_PASSWORD'] = '********'
if loggable_settings.get('DATABASE_URL'):
    # Basic attempt to mask password in URL string representation
    loggable_settings['DATABASE_URL'] = str(loggable_settings['DATABASE_URL']).replace(settings.POSTGRES_PASSWORD, '********')
logging.debug(loggable_settings)
