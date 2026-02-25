import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Optional

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

# Initialize Logging and Config first
from app.config import settings  # noqa F401
from app.logging_config import setup_logging  # noqa F401
setup_logging()

from app.api import router as api_router
from app import consumer, kafka_client, database, models  # noqa F401

log = logging.getLogger(__name__)

consumer_task: Optional[asyncio.Task] = None


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Manage application startup and shutdown via the ASGI lifespan protocol."""
    global consumer_task
    log.info("Billing Service starting up...")

    log.info("Creating database tables...")
    models.Base.metadata.create_all(bind=database.engine)

    kafka_client.get_kafka_producer()

    log.info("Starting Kafka consumer task...")
    consumer_task = asyncio.create_task(consumer.consume_loop(database.SessionLocal))

    try:
        await asyncio.wait_for(consumer.consumer_ready.wait(), timeout=30.0)
        log.info("Consumer task reported ready.")
    except asyncio.TimeoutError:
        log.warning("Consumer task did not report ready within 30 s timeout.")
    except Exception as e:
        log.exception(f"Unexpected error waiting for consumer_ready: {e}")

    log.info("Startup complete. Service ready to process requests and events.")

    yield  # Application runs here

    # --- Shutdown ---
    log.info("Billing Service shutting down...")
    if consumer_task and not consumer_task.done():
        log.info("Cancelling Kafka consumer task...")
        consumer_task.cancel()
        try:
            await asyncio.wait_for(consumer_task, timeout=15.0)
        except asyncio.CancelledError:
            log.info("Consumer task cancellation acknowledged.")
        except asyncio.TimeoutError:
            log.warning("Consumer task did not finish within shutdown timeout.")
        except Exception as e:
            log.exception(f"Error waiting for consumer task during shutdown: {e}")

    kafka_client.close_kafka_producer()
    log.info("Shutdown complete.")


# --- Application ---
app = FastAPI(
    title="SmartToll Billing Service",
    description="Handles toll event consumption, payment processing, and status tracking.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow any origin by default (restrict via CORS_ORIGINS env var in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)

# Wire up Prometheus metrics at /metrics
Instrumentator().instrument(app).expose(app, endpoint="/metrics")

# --- API Routes ---
app.include_router(api_router)


@app.get("/", tags=["Root"], summary="Root Endpoint")
async def root():
    """Provides a simple message indicating the service is running."""
    return {"message": "SmartToll Billing Service Operational"}


if __name__ == "__main__":
    log.info(f"Starting Uvicorn development server on http://{settings.BIND_HOST}:{settings.BIND_PORT}")
    uvicorn.run(
        "app.main:app",
        host=settings.BIND_HOST,
        port=settings.BIND_PORT,
        log_level=settings.LOG_LEVEL.lower(),
        reload=True,
    )
