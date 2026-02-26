from sqlalchemy import Column, Integer, String, Numeric, DateTime, Index
from sqlalchemy.sql import func
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
import uuid
import datetime
import time

from app.database import Base


# ===================
# SQLAlchemy ORM Models (Database Tables)
# ===================
class BillingTransaction(Base):
    __tablename__ = "billing_transactions"

    # Core Fields
    id = Column(Integer, primary_key=True, index=True)
    toll_event_id = Column(String, unique=True, index=True, nullable=False,
                           comment="Unique ID from the originating TollEvent")
    vehicle_id = Column(String, index=True, nullable=False, comment="Vehicle identifier")
    amount = Column(Numeric(10, 2), nullable=False, comment="Toll amount charged")
    currency = Column(String(3), nullable=False, comment="ISO currency code (e.g., USD)")

    # Status and Timestamps
    status = Column(String(20), default="PENDING", nullable=False, index=True,
                    comment="PENDING, PROCESSING, SUCCESS, FAILED, RETRY")
    transaction_time = Column(DateTime(timezone=True), server_default=func.now(), nullable=False,
                              comment="Timestamp when record was created")
    last_updated = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now(),
                          comment="Timestamp of last update")

    # Payment Gateway Details
    payment_gateway_ref = Column(String, nullable=True, index=True,
                                 comment="Reference ID from the payment provider")
    payment_method_details = Column(String, nullable=True,
                                    comment="Masked details of payment method used, if applicable")
    error_message = Column(String, nullable=True, comment="Error message if transaction failed")
    retry_count = Column(Integer, default=0, nullable=False, comment="Number of payment attempts")

    __table_args__ = (
        Index('ix_billing_transactions_vehicle_status', 'vehicle_id', 'status'),
    )

    def __repr__(self):
        return (
            f"<BillingTransaction(id={self.id}, event='{self.toll_event_id}', "
            f"vehicle='{self.vehicle_id}', status='{self.status}')>"
        )


# ===================
# Pydantic Models (API request/response, Kafka messages)
# ===================

class TollEvent(BaseModel):
    eventId: str
    vehicleId: str
    deviceId: str
    zoneId: str
    entryTime: int
    exitTime: int
    distanceKm: float
    ratePerKm: float
    tollAmount: float
    currency: str = "USD"
    processedTimestamp: int


class PaymentResult(BaseModel):
    eventId: str = Field(..., description="Corresponds to TollEvent.eventId that triggered this payment")
    transactionId: Optional[int] = Field(None, description="Corresponds to BillingTransaction.id")
    vehicleId: str
    status: str
    gatewayReference: Optional[str] = None
    errorMessage: Optional[str] = None
    processedTime: int = Field(
        default_factory=lambda: int(time.time() * 1000),
        description="Epoch ms when payment result was determined",
    )


class TransactionStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    toll_event_id: str
    vehicle_id: str
    amount: float
    currency: str
    status: str
    retry_count: int
    transaction_time: datetime.datetime
    last_updated: Optional[datetime.datetime] = None
    payment_gateway_ref: Optional[str] = None
    error_message: Optional[str] = None


class TransactionListResponse(BaseModel):
    items: list[TransactionStatusResponse]
    total: int
    page: int
    page_size: int
