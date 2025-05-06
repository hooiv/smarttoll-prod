import logging
import json
import time
import redis
from redis.exceptions import ConnectionError as RedisConnectionError, TimeoutError as RedisTimeoutError
from typing import Optional

from app.config import settings
from app.models import VehicleState

log = logging.getLogger(__name__)

_redis_client = None

def _initialize_redis_client():
    """Initializes the Redis client connection."""
    global _redis_client
    log.info("Attempting to initialize Redis client...")
    try:
        _redis_client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            decode_responses=True, # Decode responses to strings
            socket_connect_timeout=5,
            socket_keepalive=True,
            health_check_interval=30 # Check connection periodically
        )
        _redis_client.ping() # Verify connection
        log.info(f"Redis client initialized for host '{settings.REDIS_HOST}'.")
        return _redis_client
    except RedisConnectionError as e:
        log.error(f"Redis connection failed: {e}")
        _redis_client = None
        raise
    except Exception as e:
        log.exception("Unexpected error initializing Redis client.")
        _redis_client = None
        raise

def get_redis_client(retry_attempts=5, retry_delay=5):
    """Gets the Redis client, initializing it if necessary with retries."""
    global _redis_client
    if _redis_client:
        try:
            # Quick check if connection is likely still valid
            if _redis_client.ping():
                 return _redis_client
            else:
                 log.warning("Redis ping failed, attempting re-initialization.")
                 _redis_client = None # Force re-initialization
        except (RedisConnectionError, RedisTimeoutError):
             log.warning("Redis ping failed with connection/timeout error, attempting re-initialization.")
             _redis_client = None # Force re-initialization
        except Exception:
             log.exception("Unexpected error during Redis ping, attempting re-initialization.")
             _redis_client = None # Force re-initialization


    # Attempt initialization with retries if client is None
    if _redis_client is None:
        for attempt in range(retry_attempts):
            try:
                return _initialize_redis_client()
            except Exception:
                if attempt < retry_attempts - 1:
                    log.warning(f"Redis client initialization failed. Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                else:
                    log.critical("Redis client initialization failed after multiple attempts.")
                    raise # Re-raise the last exception
    return None # Should not be reached

def get_vehicle_state(vehicle_id: str) -> Optional[VehicleState]:
    """Retrieves and deserializes vehicle state from Redis."""
    redis_key = f"vehicle_state:{vehicle_id}"
    try:
        client = get_redis_client()
        if not client: return None # Could not get client

        state_json = client.get(redis_key)
        if state_json:
            state_dict = json.loads(state_json)
            # Validate data using Pydantic model
            state = VehicleState(**state_dict)
            log.debug(f"Retrieved state for vehicle {vehicle_id}: {state.model_dump_json(indent=2)}") # Pydantic V2
            # log.debug(f"Retrieved state for vehicle {vehicle_id}: {state.json(indent=2)}") # Pydantic V1
            return state
        else:
            log.debug(f"No state found in Redis for vehicle {vehicle_id} (key: {redis_key})")
            return None
    except (RedisConnectionError, RedisTimeoutError) as e:
        log.error(f"Redis connection/timeout error getting state for {vehicle_id}: {e}")
        return None # Treat connection errors as state not found for safety
    except json.JSONDecodeError as e:
         log.error(f"Failed to decode JSON state for {vehicle_id} from Redis key {redis_key}: {e}. Data: '{state_json or ''}'")
         # Consider deleting the corrupted key
         try:
             if client: client.delete(redis_key)
         except Exception as del_e:
              log.error(f"Failed to delete corrupted key {redis_key}: {del_e}")
         return None
    except Exception as e:
        # Catch Pydantic validation errors or other issues
        log.exception(f"Error getting/parsing state for {vehicle_id} from Redis key {redis_key}.")
        return None

def update_vehicle_state(vehicle_id: str, state: Optional[VehicleState]):
    """Serializes and updates vehicle state in Redis with TTL."""
    redis_key = f"vehicle_state:{vehicle_id}"
    try:
        client = get_redis_client()
        if not client:
            log.error(f"Cannot update state for {vehicle_id}, Redis client unavailable.")
            return False # Indicate failure

        if state:
            # state_json = state.json() # Pydantic V1
            state_json = state.model_dump_json() # Pydantic V2
            success = client.set(redis_key, state_json, ex=settings.VEHICLE_STATE_TTL_SECONDS)
            if success:
                 log.debug(f"Updated state for vehicle {vehicle_id} with TTL {settings.VEHICLE_STATE_TTL_SECONDS}s.")
            else:
                 log.warning(f"Redis SET command may not have succeeded for {vehicle_id} (returned non-OK).")
            return success # Return Redis command success status
        else:
            # Delete the key if state is None
            deleted_count = client.delete(redis_key)
            log.debug(f"Deleted state for vehicle {vehicle_id} (key: {redis_key}). Count: {deleted_count}")
            return deleted_count > 0 # Return True if key was deleted

    except (RedisConnectionError, RedisTimeoutError) as e:
        log.error(f"Redis connection/timeout error updating state for {vehicle_id}: {e}")
        return False
    except Exception as e:
        log.exception(f"Error updating state for {vehicle_id} in Redis.")
        return False

def close_redis_client():
    """Closes the Redis client connection."""
    global _redis_client
    if _redis_client:
        try:
            _redis_client.close() # Available in redis-py 4.x+
            log.info("Redis client connection closed.")
            _redis_client = None
        except Exception:
            log.exception("Error closing Redis client connection.")
