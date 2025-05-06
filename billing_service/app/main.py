import asyncio
import logging
import signal
from fastapi import FastAPI
import uvicorn
from typing import Optional # Added for consumer_task type hint

# Initialize Logging and Config first
from app.config import settings # noqa F401
from app.logging_config import setup_logging # noqa F401
setup_logging() # Explicit call after potential env var load

from app.api import router as api_router
from app import consumer, kafka_client, database, models # Relative imports

log = logging.getLogger(__name__)

# --- Application State ---
app = FastAPI(
    title="SmartToll Billing Service",
    description="Handles toll event consumption, payment processing, and status tracking.",
    version="1.0.0"
)
consumer_task: Optional[asyncio.Task] = None
consumer_ready = asyncio.Event() # Event to signal when consumer is ready/connected


# --- Event Handlers ---
@app.on_event("startup")
async def startup_event():
    """Application startup logic."""
    global consumer_task
    log.info("Billing Service starting up...")

    # Initialize Kafka Producer first (needed by billing logic)
    # Corrected: Call the initialization function from the kafka_client module
    kafka_client.get_kafka_producer() # Use the getter which handles initialization

    # Optional: Run DB migrations here or as a separate step/job
    # log.info("Running database migrations...")
    # run_migrations() # Placeholder for Alembic command execution

    # Start the Kafka consumer in the background
    log.info("Starting Kafka consumer task...")
    # Pass the session factory, not a single session
    consumer_task = asyncio.create_task(consumer.consume_loop(database.SessionLocal, consumer_ready))

    # Optional: Wait briefly for consumer to signal readiness before accepting requests?
    try:
        await asyncio.wait_for(consumer_ready.wait(), timeout=30.0)
        log.info("Consumer task reported ready.")
    except asyncio.TimeoutError:
         log.warning("Consumer task did not report ready within timeout.")
         # Proceed anyway, but health checks might fail initially

    log.info("Startup complete. Service ready to process requests and events.")

@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown logic."""
    log.info("Billing Service shutting down...")

    # Gracefully stop the consumer task
    if consumer_task and not consumer_task.done():
        log.info("Cancelling Kafka consumer task...")
        consumer_task.cancel()
        try:
            # Wait for the task to finish cancellation
            await asyncio.wait_for(consumer_task, timeout=15.0)
            log.info("Consumer task successfully cancelled and finished.")
        except asyncio.CancelledError:
            log.info("Consumer task cancellation acknowledged.")
        except asyncio.TimeoutError:
            log.warning("Consumer task did not finish within shutdown timeout.")
        except Exception as e:
             log.exception(f"Error waiting for consumer task during shutdown: {e}")

    # Close Kafka producer
    kafka_client.close_kafka_producer()

    # Close Database connections (SQLAlchemy engine handles pool disposal usually)
    # if database.engine:
    #     database.engine.dispose()
    #     log.info("Database engine disposed.")

    log.info("Shutdown complete.")

# --- API Routes ---
app.include_router(api_router)

@app.get("/", tags=["Root"], summary="Root Endpoint")
async def root():
    """Provides a simple message indicating the service is running."""
    return {"message": "SmartToll Billing Service Operational"}


# --- Main Execution ---
# (Uvicorn is run via Docker CMD typically)
# Allow running directly for local dev testing:
if __name__ == "__main__":
     log.info(f"Starting Uvicorn development server on http://{settings.BIND_HOST}:{settings.BIND_PORT}")
     uvicorn.run(
         "app.main:app", # Point to the FastAPI app instance
         host=settings.BIND_HOST,
         port=settings.BIND_PORT,
         log_level=settings.LOG_LEVEL.lower(), # Sync uvicorn log level
         reload=True # Enable auto-reload for development ONLY!
     )
