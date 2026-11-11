import logging
import time
import threading
from contextlib import contextmanager

from psycopg2 import pool as psycopg2_pool
from psycopg2 import OperationalError as Psycopg2OpError
from psycopg2.extras import RealDictCursor  # Use dict cursors for easier access

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
    except Exception:
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
        SELECT zone_id, rate_per_km, flat_fee_inr
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
                    result['rate_per_km'] = float(result['rate_per_km'])
                    if result.get('flat_fee_inr') is not None:
                        result['flat_fee_inr'] = float(result['flat_fee_inr'])
                log.debug(f"Geofence check for ({latitude}, {longitude}): {'Found zone ' + result['zone_id'] if result else 'No zone found'}")
                return result
    except Psycopg2OpError as db_err:
        # Handle specific DB errors like connection issues potentially differently
        log.error(f"Database operational error during geofence check: {db_err}", exc_info=True)
        # Depending on policy, maybe return None or raise a specific exception
        return None # Fail safe - assume outside zone if DB error occurs
    except Exception:
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
    Also seeds default toll zones matching the OBU simulator route if the table is empty.
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
            # Plaza crossings bill a flat INR amount. NULL means distance * rate_per_km.
            cur.execute("ALTER TABLE toll_zones ADD COLUMN IF NOT EXISTS flat_fee_inr NUMERIC;")
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_toll_zones_geom
                ON toll_zones USING GIST(geom);
            """)
            # Drop the old NYC sample if a previous boot seeded it.
            cur.execute("DELETE FROM toll_zones WHERE zone_id = 'Zone1';")
            # Polygons are ~1.3 km along NH-48 and ~440 m across, centred on the
            # simulator trace so a car following the highway actually crosses them.
            #   NH48-IGI     Mahipalpur / IGI plaza, 28.5439 N, 77.1154 E
            #   NH48-SIRHAUL Delhi–Gurugram border near Sirhaul
            #   NH48-KHERKI  Kherki Daula plaza, 28.3956 N, 76.9818 E
            cur.execute("""
                INSERT INTO toll_zones (zone_id, zone_name, rate_per_km, flat_fee_inr, geom)
                VALUES
                (
                    'NH48-IGI',
                    'IGI Airport plaza, NH-48 Mahipalpur',
                    0,
                    20,
                    ST_SetSRID(ST_GeomFromText('POLYGON((77.122471 28.545479, 77.118577 28.538143, 77.114495 28.539815, 77.118389 28.547151, 77.122471 28.545479))'), 4326)
                ),
                (
                    'NH48-SIRHAUL',
                    'Sirhaul border segment, NH-48',
                    0,
                    45,
                    ST_SetSRID(ST_GeomFromText('POLYGON((77.090740 28.503925, 77.094722 28.496626, 77.090662 28.494915, 77.086680 28.502214, 77.090740 28.503925))'), 4326)
                ),
                (
                    'NH48-KHERKI',
                    'Kherki Daula toll plaza, NH-48',
                    0,
                    85,
                    ST_SetSRID(ST_GeomFromText('POLYGON((76.986716 28.397279, 76.980836 28.391054, 76.977376 28.393583, 76.983256 28.399808, 76.986716 28.397279))'), 4326)
                )
                ON CONFLICT (zone_id) DO UPDATE
                SET zone_name = EXCLUDED.zone_name,
                    rate_per_km = EXCLUDED.rate_per_km,
                    flat_fee_inr = EXCLUDED.flat_fee_inr,
                    geom = EXCLUDED.geom;
            """)
        # Commit DDL + seed data so they persist
        conn.commit()
    log.info("Database schema initialised and default toll zones seeded.")
