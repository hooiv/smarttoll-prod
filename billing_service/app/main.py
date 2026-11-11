import asyncio
import logging
import uuid
from contextlib import asynccontextmanager
from typing import Optional

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator
from starlette.middleware.base import BaseHTTPMiddleware

# Initialize Logging and Config first
from app.config import settings  # noqa F401
from app.logging_config import setup_logging  # noqa F401
setup_logging()

from app.api import router as api_router
from app.logging_config import request_id_var
from app import consumer, kafka_client, database, models  # noqa F401

log = logging.getLogger(__name__)

consumer_task: Optional[asyncio.Task] = None


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Attaches a unique X-Request-ID to every request/response for distributed tracing."""

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        token = request_id_var.set(request_id)
        try:
            response = await call_next(request)
        finally:
            request_id_var.reset(token)
        response.headers["X-Request-ID"] = request_id
        return response


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Manage application startup and shutdown via the ASGI lifespan protocol."""
    global consumer_task
    log.info("Billing Service starting up...")

    log.info("Creating database tables if migrations have not already...")
    models.Base.metadata.create_all(bind=database.engine)

    # Do not block the HTTP server on Kafka. Liveness comes up immediately;
    # readiness stays 503 until the consumer connects. The consumer retries
    # with backoff for as long as the process is alive.
    try:
        kafka_client.get_kafka_producer(retry_attempts=1)
    except Exception:
        log.warning("Kafka producer is not ready yet. Sends will retry on use.")

    log.info("Starting Kafka consumer task...")
    consumer_task = asyncio.create_task(consumer.consume_loop(database.SessionLocal))

    async def _log_when_ready() -> None:
        try:
            await asyncio.wait_for(consumer.consumer_ready.wait(), timeout=120.0)
            log.info("Consumer task reported ready.")
        except asyncio.TimeoutError:
            log.warning("Consumer not ready after 120s; the background loop is still retrying.")
        except Exception as e:
            log.exception(f"Unexpected error waiting for consumer_ready: {e}")

    asyncio.create_task(_log_when_ready())
    log.info("HTTP server starting. Readiness follows the Kafka consumer.")

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

# Attach a unique X-Request-ID to every request/response for distributed tracing
app.add_middleware(RequestIDMiddleware)

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
