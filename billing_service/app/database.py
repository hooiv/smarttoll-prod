import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from contextlib import contextmanager

from app.config import settings

log = logging.getLogger(__name__)

# --- SQLAlchemy Setup ---
try:
    log.info(f"Initializing database engine for URL: {str(settings.DATABASE_URL).replace(settings.POSTGRES_PASSWORD, '********')}")
    # Use pool_recycle to prevent stale connections after long idle times
    # `pool_pre_ping=True` checks connection validity before use
    engine = create_engine(
        str(settings.DATABASE_URL), # Convert DSN type to string
        pool_pre_ping=True,
        pool_recycle=3600, # Recycle connections older than 1 hour
        pool_size=settings.POSTGRES_POOL_SIZE,
        max_overflow=settings.POSTGRES_MAX_OVERFLOW,
        pool_timeout=settings.POSTGRES_POOL_TIMEOUT,
        echo=settings.LOG_LEVEL == "DEBUG" # Log SQL statements only in DEBUG mode
    )

    # Sessionmaker configured for creating sessions
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # Base class for declarative class definitions
    Base = declarative_base()

    # Optional: Test connection on startup (engine connects lazily)
    # with engine.connect() as connection:
    #     log.info("Database connection successful.")

    log.info("SQLAlchemy engine and sessionmaker configured.")

except Exception as e:
    log.critical(f"Failed to initialize SQLAlchemy engine: {e}", exc_info=True)
    raise # Critical failure if DB cannot be configured


@contextmanager
def get_db_session():
    """Provides a transactional scope around a series of operations."""
    session = SessionLocal()
    log.debug(f"DB Session {id(session)} created.")
    try:
        yield session
        # Optional: Commit here if operations within the 'with' block should be automatically committed
        # session.commit()
    except Exception as e:
        log.error(f"DB Session {id(session)} caught exception, rolling back: {e}", exc_info=True)
        session.rollback()
        raise # Re-raise the exception after rollback
    finally:
        log.debug(f"DB Session {id(session)} closed.")
        session.close()

# Dependency for FastAPI routes
def get_db():
    """FastAPI dependency that provides a session and ensures it's closed."""
    with get_db_session() as session:
        yield session
