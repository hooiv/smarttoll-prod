import logging
from enum import Enum
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query, status as http_status
from sqlalchemy.orm import Session
from sqlalchemy import select, func, text

from app import database, models, consumer
from app.security import verify_api_key

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["Billing"])


class TransactionStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    RETRY = "RETRY"


# ---------------------------------------------------------------------------
# Dependency: check that core dependencies are healthy
# ---------------------------------------------------------------------------
async def check_dependencies():
    try:
        with database.get_db_session() as db:
            db.execute(text("SELECT 1"))
    except Exception:
        raise HTTPException(
            status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection failed",
        )
    if not consumer.consumer_ready.is_set():
        raise HTTPException(
            status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Kafka consumer not ready",
        )


# ---------------------------------------------------------------------------
# Health endpoints (no auth required)
# ---------------------------------------------------------------------------
@router.get("/health/live", status_code=http_status.HTTP_200_OK, tags=["Health"])
async def liveness_check():
    return {"status": "live"}


@router.get("/health/ready", status_code=http_status.HTTP_200_OK, tags=["Health"])
async def readiness_check(_: None = Depends(check_dependencies)):
    return {"status": "ready"}


@router.get("/version", tags=["Health"], summary="Service Version")
async def version():
    """Returns the current service version."""
    from app.config import settings as _settings
    return {"service": "billing_service", "version": _settings.SERVICE_VERSION}


# ---------------------------------------------------------------------------
# Transaction endpoints (API key required)
# ---------------------------------------------------------------------------
@router.get(
    "/transactions",
    response_model=models.TransactionListResponse,
    summary="List Billing Transactions",
    description="Returns a paginated list of billing transactions, optionally filtered by vehicle or status.",
    dependencies=[Depends(verify_api_key)],
)
async def list_transactions(
    vehicle_id: Annotated[str | None, Query(min_length=1, description="Filter by vehicle ID")] = None,
    status: TransactionStatus | None = Query(None, description="Filter by status"),
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    page_size: int = Query(20, ge=1, le=100, description="Number of items per page"),
    db: Session = Depends(database.get_db),
):
    """Returns a paginated list of transactions with optional filters."""
    stmt = select(models.BillingTransaction)
    count_stmt = select(func.count()).select_from(models.BillingTransaction)

    if vehicle_id:
        stmt = stmt.where(models.BillingTransaction.vehicle_id == vehicle_id)
        count_stmt = count_stmt.where(models.BillingTransaction.vehicle_id == vehicle_id)
    if status:
        stmt = stmt.where(models.BillingTransaction.status == status.value)
        count_stmt = count_stmt.where(models.BillingTransaction.status == status.value)

    total = db.execute(count_stmt).scalar_one()
    offset = (page - 1) * page_size
    items = db.execute(
        stmt.order_by(models.BillingTransaction.transaction_time.desc())
           .offset(offset)
           .limit(page_size)
    ).scalars().all()

    return models.TransactionListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/transactions/status/{toll_event_id}",
    response_model=models.TransactionStatusResponse,
    summary="Get Billing Transaction Status by Toll Event ID",
    description="Retrieves the current status and details of a billing transaction "
                "based on the original Toll Event ID.",
    dependencies=[Depends(verify_api_key)],
)
async def get_transaction_status_by_event(
    toll_event_id: str,
    db: Session = Depends(database.get_db),
):
    """Retrieves billing transaction status using the Toll Event ID."""
    log.info(f"Request received for transaction status with Toll Event ID: {toll_event_id}")
    stmt = select(models.BillingTransaction).where(
        models.BillingTransaction.toll_event_id == toll_event_id
    )
    tx = db.execute(stmt).scalars().first()
    if not tx:
        raise HTTPException(
            status_code=404,
            detail=f"Transaction for Toll Event ID '{toll_event_id}' not found.",
        )
    return tx


@router.get(
    "/transactions/{transaction_id}",
    response_model=models.TransactionStatusResponse,
    summary="Get Billing Transaction Status by Internal ID",
    dependencies=[Depends(verify_api_key)],
)
async def get_transaction_status_by_id(
    transaction_id: int,
    db: Session = Depends(database.get_db),
):
    """Retrieves billing transaction status using the internal database ID."""
    stmt = select(models.BillingTransaction).where(
        models.BillingTransaction.id == transaction_id
    )
    tx = db.execute(stmt).scalars().first()
    if not tx:
        raise HTTPException(
            status_code=404,
            detail=f"Transaction with ID '{transaction_id}' not found.",
        )
    return tx
