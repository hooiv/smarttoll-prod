# Identical to toll_processor/app/logging_config.py - could potentially be a shared library
import logging
import sys
from pythonjsonlogger import jsonlogger
from app.config import settings # Relative import

def setup_logging():
    """Configures structured JSON logging."""
    logger = logging.getLogger() # Get root logger
    log_level = settings.LOG_LEVEL.upper()
    logger.setLevel(log_level)

    if logger.hasHandlers():
        logger.handlers.clear()

    logHandler = logging.StreamHandler(sys.stdout)
    formatter = jsonlogger.JsonFormatter(
        '%(asctime)s %(name)s %(levelname)s %(message)s %(pathname)s %(lineno)d %(process)d %(threadName)s'
    )
    logHandler.setFormatter(formatter)
    logger.addHandler(logHandler)

    # Silence noisy libraries
    logging.getLogger("kafka").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO if log_level == "DEBUG" else logging.WARNING) # Show SQL in DEBUG
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING) # Reduce access log noise unless DEBUG

    logger.info(f"Logging configured with level: {log_level}")
    return logger

setup_logging()
log = logging.getLogger(__name__)
