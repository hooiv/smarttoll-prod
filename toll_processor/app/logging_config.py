import logging
import sys
from pythonjsonlogger import jsonlogger
from app.config import settings # Use relative import

def setup_logging():
    """Configures structured JSON logging."""
    logger = logging.getLogger() # Get root logger
    log_level = settings.LOG_LEVEL.upper()
    logger.setLevel(log_level)

    # Remove existing handlers to prevent duplicates if re-initialized
    if logger.hasHandlers():
        logger.handlers.clear()

    # Create a handler that writes to stdout
    logHandler = logging.StreamHandler(sys.stdout)

    # Use JSON formatter
    formatter = jsonlogger.JsonFormatter(
        '%(asctime)s %(name)s %(levelname)s %(message)s %(pathname)s %(lineno)d %(process)d %(threadName)s'
    )
    logHandler.setFormatter(formatter)

    # Add the handler to the root logger
    logger.addHandler(logHandler)

    # Silence overly verbose libraries
    logging.getLogger("kafka").setLevel(logging.WARNING)
    logging.getLogger("kafka.conn").setLevel(logging.WARNING)
    logging.getLogger("redis").setLevel(logging.WARNING)
    logging.getLogger("psycopg2").setLevel(logging.WARNING)

    logger.info(f"Logging configured with level: {log_level}")
    return logger

# Call setup function immediately when module is imported
setup_logging()
# Get logger instance for use in other modules
log = logging.getLogger(__name__)
