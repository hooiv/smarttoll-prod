import logging
import time
from sqlalchemy.orm import Session
from sqlalchemy import select # Use select() for modern SQLAlchemy
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app import models, payment, kafka_client, metrics # Relative imports
from app.config import settings
from app.payment import PaymentGatewayError # Import custom exception

log = logging.getLogger(__name__)

async def process_toll_event_for_billing(event_data: models.TollEvent, db: Session):
    """
    Processes a toll event consumed from Kafka:
    1. Checks for duplicates.
    2. Creates a PENDING transaction record.
    3. Calls the payment gateway.
    4. Updates the transaction record status.
    5. Publishes the payment result.
    """
    log.info(f"Received Toll Event for processing: EventID={event_data.eventId}, Vehicle={event_data.vehicleId}")

    # --- 1. Idempotency Check ---
    # Check if this toll_event_id has already been processed successfully or is pending
    stmt = select(models.BillingTransaction).where(models.BillingTransaction.toll_event_id == event_data.eventId)
    existing_tx = db.execute(stmt).scalars().first()

    if existing_tx:
        if existing_tx.status == "SUCCESS":
            log.warning(f"Duplicate Toll Event ID {event_data.eventId} already processed successfully (TxID: {existing_tx.id}). Ignoring.")
            metrics.transactions_duplicate_total.inc()
            # Optionally republish payment result? Depends on downstream consumers.
            return True # Indicate successful handling (idempotency)
        elif existing_tx.status in ["PENDING", "PROCESSING", "RETRY"]:
             log.warning(f"Duplicate Toll Event ID {event_data.eventId} already exists with status {existing_tx.status} (TxID: {existing_tx.id}). Ignoring new request.")
             metrics.transactions_duplicate_total.inc()
             # Potentially check age of pending transaction and retry if needed? Complex.
             return True # Indicate handled for now
        # If FAILED, maybe allow retry? Depends on business rules. Let's assume we don't retry based on duplicate event alone here.

    # --- 2. Create Initial Transaction Record ---
    new_tx = models.BillingTransaction(
        vehicle_id=event_data.vehicleId,
        toll_event_id=event_data.eventId,
        amount=round(event_data.tollAmount, 2), # Ensure rounded
        currency=event_data.currency,
        status="PENDING",
        retry_count=0, # Initialize so increment works before first DB flush
    )
    db.add(new_tx)
    try:
        db.flush()          # Flush so the DB assigns the auto-increment id
        db.refresh(new_tx)  # Populate new_tx.id with the assigned value
        tx_id = new_tx.id
        db.commit()         # Commit the pending record
        metrics.transactions_created_total.inc()
        log.info(f"Created PENDING transaction record TxID={tx_id} for EventID={event_data.eventId}")
    except IntegrityError as e:
        db.rollback()
        log.error(f"Database integrity error (likely duplicate toll_event_id detected concurrently) for EventID={event_data.eventId}: {e}", exc_info=True)
        return True # Treat as handled duplicate
    except SQLAlchemyError as e:
        db.rollback()
        log.error(f"Database error creating transaction record for EventID={event_data.eventId}: {e}", exc_info=True)
        return False # Indicate failure to process

    # --- 3. Call Payment Gateway ---
    # Mark status as PROCESSING before calling GW
    payment_start_time = time.monotonic()
    gateway_ref = None
    payment_error_msg = None
    payment_success = False
    final_status = "FAILED" # Default to failed

    try:
        # Update status to PROCESSING first, increment attempt counter
        new_tx.status = "PROCESSING"
        new_tx.retry_count += 1
        db.commit()
        log.info(f"TxID={tx_id} status updated to PROCESSING before calling payment gateway.")

        # Call the (mock) payment gateway asynchronously
        gateway_ref, _ = await payment.process_payment(
            transaction_id=tx_id,
            toll_event_id=event_data.eventId,
            vehicle_id=event_data.vehicleId,
            amount=new_tx.amount,
            currency=new_tx.currency
        )
        # If process_payment returns without exception, it's a success
        final_status = "SUCCESS"
        metrics.payment_success_total.inc()
        log.info(f"Payment successful for TxID={tx_id}. Gateway Ref: {gateway_ref}")

    except PaymentGatewayError as pge:
        # Specific failure from the payment gateway
        log.warning(f"Payment failed for TxID={tx_id} due to gateway error: {pge.message} (Code: {pge.error_code})")
        payment_error_msg = f"{pge.error_code}: {pge.message}"
        metrics.payment_failure_total.labels(error_code=pge.error_code).inc()
        # Check if retryable? For now, mark as FAILED. Could set to RETRY based on error_code.
        final_status = "FAILED"
    except Exception as e:
        # Unexpected error during payment call
        log.exception(f"Unexpected error during payment processing for TxID={tx_id}.")
        payment_error_msg = f"Unexpected system error: {str(e)}"
        metrics.payment_failure_total.labels(error_code="SYSTEM_ERROR").inc()
        final_status = "FAILED" # Or maybe RETRY if transient?

    payment_duration = time.monotonic() - payment_start_time
    metrics.payment_duration_seconds.observe(payment_duration)
    log.info(f"Payment attempt for TxID={tx_id} finished in {payment_duration:.3f}s with status {final_status}")

    # --- 4. Update Transaction Status in DB ---
    # new_tx is already tracked by the session; update it directly.
    db_update_failed = False
    try:
        new_tx.status = final_status
        new_tx.payment_gateway_ref = gateway_ref
        new_tx.error_message = payment_error_msg

        db.commit()
        log.info(f"Updated transaction TxID={tx_id} final status to {final_status}")
    except SQLAlchemyError as e:
        db.rollback()
        log.error(f"Database error updating final transaction status for TxID={tx_id}: {e}", exc_info=True)
        # Payment state may mismatch DB state — publish result anyway then signal failure.
        db_update_failed = True

    # --- 5. Publish Payment Result Event ---
    # Always publish the payment outcome so downstream consumers stay consistent,
    # even when the DB update failed.
    payment_result = models.PaymentResult(
        eventId=event_data.eventId,
        transactionId=tx_id,
        vehicleId=event_data.vehicleId,
        status=final_status,
        gatewayReference=gateway_ref,
        errorMessage=payment_error_msg,
    )

    key = event_data.vehicleId.encode('utf-8')
    publish_ok = kafka_client.send_message(
        settings.PAYMENT_EVENT_TOPIC, payment_result.model_dump(), key=key
    )
    if publish_ok:
        log.info(
            f"Published PaymentResult for TxID={tx_id}, EventID={event_data.eventId} "
            f"to Kafka topic {settings.PAYMENT_EVENT_TOPIC}"
        )
    else:
        log.error(f"Failed to publish PaymentResult for TxID={tx_id}, EventID={event_data.eventId}")

    if db_update_failed:
        return False

    # Return True even if payment failed — the event *was processed*.
    # Return False only for system errors that prevent recording the outcome.
    return True
