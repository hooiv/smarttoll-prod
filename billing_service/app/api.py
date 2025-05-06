import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select

from app import database, models # Relative imports

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["Billing"]) # Add prefix and tags

@router.get("/health")
async def health_check():
    """Basic health check endpoint."""
    # TODO: Add deeper checks (DB connection, Kafka connection?) if needed
    log.debug("Health check endpoint called")
    return {"status": "ok", "service": "Billing Service"}

@router.get(
    "/transactions/status/{toll_event_id}",
    response_model=models.TransactionStatusResponse, # Use Pydantic model for response
    summary="Get Billing Transaction Status by Toll Event ID",
    description="Retrieves the current status and details of a billing transaction based on the original Toll Event ID."
)
async def get_transaction_status_by_event(
    toll_event_id: str,
    db: Session = Depends(database.get_db) # Use FastAPI dependency injection for DB session
):
    """Retrieves billing transaction status using the Toll Event ID."""
    log.info(f"Request received for transaction status with Toll Event ID: {toll_event_id}")
    stmt = select(models.BillingTransaction).where(models.BillingTransaction.toll_event_id == toll_event_id)
    tx = db.execute(stmt).scalars().first()

    if not tx:
        log.warning(f"Transaction not found for Toll Event ID: {toll_event_id}")
        raise HTTPException(status_code=404, detail=f"Transaction for Toll Event ID '{toll_event_id}' not found.")

    log.info(f"Found transaction TxID={tx.id} with status '{tx.status}' for Toll Event ID: {toll_event_id}")
    # Pydantic model `TransactionStatusResponse` with orm_mode=True handles conversion
    return tx

# Example: Endpoint to get status by internal DB transaction ID
@router.get(
    "/transactions/{transaction_id}",
    response_model=models.TransactionStatusResponse,
    summary="Get Billing Transaction Status by Internal ID"
)
async def get_transaction_status_by_id(
    transaction_id: int,
    db: Session = Depends(database.get_db)
):
    """Retrieves billing transaction status using the internal database ID."""
    log.info(f"Request received for transaction status with Internal ID: {transaction_id}")
    # Use db.get() for primary key lookup if session manages the object lifecycle correctly
    # tx = db.get(models.BillingTransaction, transaction_id) # Might require specific session config or loading
    # Using select is generally safer across different session states:
    stmt = select(models.BillingTransaction).where(models.BillingTransaction.id == transaction_id)
    tx = db.execute(stmt).scalars().first()

    if not tx:
        log.warning(f"Transaction not found for Internal ID: {transaction_id}")
        raise HTTPException(status_code=404, detail=f"Transaction with ID '{transaction_id}' not found.")

    log.info(f"Found transaction TxID={tx.id} with status '{tx.status}'")
    return tx
