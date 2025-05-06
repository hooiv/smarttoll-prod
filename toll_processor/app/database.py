import logging
import time
import threading
from contextlib import contextmanager

import psycopg2
from psycopg2 import pool as psycopg2_pool
from psycopg2 import OperationalError as Psycopg2OpError
from psycopg2.extras import RealDictCursor # Use dict cursors for easier access

from app.config import settings

log = logging.getLogger(__name__)

# Thread-local storage for connection pool might be needed in complex threaded apps,
# but for typical consumer patterns, a shared pool is usually fine if managed carefully.
_db_pool = None
_pool_lock = threading.Lock() # Lock for safe initialization

def _initialize_db_pool():
    """Initializes the PostgreSQL connection pool."""
    global _db_pool
    log.info("Attempting to initialize PostgreSQL connection pool...")
    try:
        _db_pool = psycopg2_pool.SimpleConnectionPool(
            settings.POSTGRES_POOL_MIN,
            settings.POSTGRES_POOL_MAX,
            user=settings.POSTGRES_USER,
            password=settings.POSTGRES_PASSWORD,
            host=settings.POSTGRES_HOST,
            port=settings.POSTGRES_PORT,
            database=settings.POSTGRES_DB,
            connect_timeout=settings.POSTGRES_CONNECT_TIMEOUT,
            cursor_factory=RealDictCursor # Use dictionary cursor
        )
        # Test connection
        conn = _db_pool.getconn()
        log.info(f"PostgreSQL connection pool initialized for host '{settings.POSTGRES_HOST}'. Connections: min={settings.POSTGRES_POOL_MIN}, max={settings.POSTGRES_POOL_MAX}")
        _db_pool.putconn(conn)
        return _db_pool
    except Psycopg2OpError as e:
        log.error(f"PostgreSQL pool initialization failed: {e}")
        _db_pool = None # Ensure pool is None if failed
        raise # Re-raise to signal failure
    except Exception as e:
        log.exception("Unexpected error initializing PostgreSQL pool.")
        _db_pool = None
        raise

def get_db_pool(retry_attempts=5, retry_delay=5):
    """Gets the connection pool, initializing it if necessary with retries."""
    global _db_pool
    if _db_pool:
        return _db_pool

    with _pool_lock:
        # Double-check if another thread initialized it while waiting for the lock
        if _db_pool:
            return _db_pool

        for attempt in range(retry_attempts):
            try:
                log.info(f"Initializing DB Pool (Attempt {attempt + 1}/{retry_attempts})")
                return _initialize_db_pool()
            except Exception:
                if attempt < retry_attempts - 1:
                    log.warning(f"DB Pool initialization failed. Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                else:
                    log.critical("DB Pool initialization failed after multiple attempts.")
                    raise # Re-raise the last exception
        # Should not be reached if attempts > 0, but satisfy linters
        raise ConnectionError("Failed to initialize database pool after multiple attempts.")


@contextmanager
def get_db_connection():
    """Provides a database connection from the pool using a context manager."""
    pool = get_db_pool() # Ensures pool is initialized
    conn = None
    try:
        conn = pool.getconn()
        yield conn
    except Exception:
        # Log exceptions that occur *during* the 'yield' block (user code)
        log.exception("Error during database operation within context manager.")
        # Rollback might be needed here depending on autocommit settings, but SimpleConnectionPool usually doesn't manage transactions itself.
        # If conn was acquired, it should be returned to the pool even if user code failed.
        raise # Re-raise the exception
    finally:
        if conn:
            pool.putconn(conn)


def get_current_toll_zone(latitude: float, longitude: float) -> dict | None:
    """
    Checks PostGIS if the point is inside any known toll zone.

    Args:
        latitude: GPS latitude.
        longitude: GPS longitude.

    Returns:
        A dictionary containing zone_id and rate_per_km if found, otherwise None.
    """
    query = """
        SELECT zone_id, rate_per_km
        FROM toll_zones -- Make sure this table exists and is populated
        WHERE ST_Contains(geom, ST_SetSRID(ST_MakePoint(%s, %s), 4326)) -- Longitude, Latitude order for ST_MakePoint
        LIMIT 1;
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                # Pass longitude first, then latitude to ST_MakePoint
                cursor.execute(query, (longitude, latitude))
                result = cursor.fetchone() # Returns a dict or None
                if result:
                    # Ensure rate is float
                    result['rate_per_km'] = float(result['rate_per_km'])
                log.debug(f"Geofence check for ({latitude}, {longitude}): {'Found zone ' + result['zone_id'] if result else 'No zone found'}")
                return result
    except Psycopg2OpError as db_err:
        # Handle specific DB errors like connection issues potentially differently
        log.error(f"Database operational error during geofence check: {db_err}", exc_info=True)
        # Depending on policy, maybe return None or raise a specific exception
        return None # Fail safe - assume outside zone if DB error occurs
    except Exception as e:
        log.exception(f"Unexpected error during geofence check for ({latitude}, {longitude}).")
        return None # Fail safe

def close_db_pool():
    """Closes all connections in the pool."""
    global _db_pool
    if _db_pool:
        with _pool_lock:
            try:
                _db_pool.closeall()
                log.info("PostgreSQL connection pool closed.")
                _db_pool = None
            except Exception:
                log.exception("Error closing PostgreSQL connection pool.")

def init_db_schema():
    """
    Initializes the required database schema for toll_processor, ensuring PostGIS and toll_zones table exist.
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Ensure PostGIS extension
            cur.execute("CREATE EXTENSION IF NOT EXISTS postgis;")
            # Create toll_zones table if missing
            cur.execute("""
                CREATE TABLE IF NOT EXISTS toll_zones (
                    zone_id VARCHAR PRIMARY KEY,
                    zone_name TEXT NOT NULL,
                    rate_per_km NUMERIC NOT NULL,
                    geom geometry(POLYGON,4326) NOT NULL
                );
            """)
        # Commit DDL changes so they persist
        conn.commit()
