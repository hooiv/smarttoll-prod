from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Index
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship # If relating models later
from pydantic import BaseModel, Field
from typing import Optional
import uuid
import datetime
import time # Add near top

from app.database import Base # Import Base from database setup

# ===================
# SQLAlchemy ORM Models (Database Tables)
# ===================
class BillingTransaction(Base):
    __tablename__ = "billing_transactions"

    # Core Fields
    id = Column(Integer, primary_key=True, index=True)
    toll_event_id = Column(String, unique=True, index=True, nullable=False, comment="Unique ID from the originating TollEvent")
    vehicle_id = Column(String, index=True, nullable=False, comment="Vehicle identifier")
    amount = Column(Float, nullable=False, comment="Toll amount charged") # Use Numeric/Decimal for financial precision in prod
    currency = Column(String(3), nullable=False, comment="ISO currency code (e.g., USD)")

    # Status and Timestamps
    status = Column(String(20), default="PENDING", nullable=False, index=True, comment="PENDING, PROCESSING, SUCCESS, FAILED, RETRY")
    transaction_time = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="Timestamp when record was created")
    last_updated = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now(), comment="Timestamp of last update")

    # Payment Gateway Details
    payment_gateway_ref = Column(String, nullable=True, index=True, comment="Reference ID from the payment provider")
    payment_method_details = Column(String, nullable=True, comment="Masked details of payment method used, if applicable")
    error_message = Column(String, nullable=True, comment="Error message if transaction failed")
    retry_count = Column(Integer, default=0, nullable=False, comment="Number of payment attempts")

    # Add table args for multi-column indexes if needed
    # __table_args__ = (Index('ix_billing_transactions_vehicle_status', 'vehicle_id', 'status'),)

    def __repr__(self):
        return f"<BillingTransaction(id={self.id}, event='{self.toll_event_id}', vehicle='{self.vehicle_id}', status='{self.status}')>"


# ===================
# Pydantic Models (API request/response, Kafka messages)
# ===================

# Represents the incoming Toll Event from Kafka
class TollEvent(BaseModel):
    eventId: str
    vehicleId: str
    deviceId: str
    zoneId: str
    entryTime: int # Epoch ms
    exitTime: int # Epoch ms
    distanceKm: float
    ratePerKm: float
    tollAmount: float
    currency: str = "USD"
    processedTimestamp: int # Epoch ms from toll_processor

# Represents the Payment Result published back to Kafka
class PaymentResult(BaseModel):
    eventId: str = Field(..., description="Corresponds to TollEvent.eventId that triggered this payment")
    transactionId: int = Field(..., description="Corresponds to BillingTransaction.id")
    vehicleId: str
    status: str # SUCCESS, FAILED
    gatewayReference: Optional[str] = None
    errorMessage: Optional[str] = None
    processedTime: int = Field(default_factory=lambda: int(time.time() * 1000), description="Epoch ms when payment result was determined") # V1
    # processedTime: int = Field(default_factory=lambda: int(datetime.datetime.now(datetime.timezone.utc).timestamp() * 1000), description="Epoch ms when payment result was determined") # V2

# Represents the response for the API endpoint checking transaction status
class TransactionStatusResponse(BaseModel):
    id: int
    toll_event_id: str
    vehicle_id: str
    amount: float
    currency: str
    status: str
    transaction_time: datetime.datetime # Keep as datetime for API response
    last_updated: Optional[datetime.datetime] = None
    payment_gateway_ref: Optional[str] = None
    error_message: Optional[str] = None

    class Config:
        orm_mode = True # Enable reading data from ORM models


# import datetime # Add near top (already present)
