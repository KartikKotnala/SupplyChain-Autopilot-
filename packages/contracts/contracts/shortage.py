"""Contract 1: ShortageAlert
Defines the output of the Inventory Monitoring Agent and input to Supplier Discovery.
"""
from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, field_validator, model_validator


class UrgencyLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ShortageAlert(BaseModel):
    """Structured artifact raised when projected inventory hits or breaches safety stock."""
    component_id: str = Field(..., description="Unique component identifier, e.g. COMP-001")
    component_name: str = Field(..., description="Human readable component name, e.g. Compressor")
    on_hand_qty: float = Field(..., ge=0.0, description="Physical stock in warehouse")
    reserved_qty: float = Field(default=0.0, ge=0.0, description="Stock already committed to active production")
    available_qty: float = Field(..., description="Usable stock: on_hand_qty - reserved_qty")
    daily_burn_rate: float = Field(..., gt=0.0, description="Expected daily consumption rate")
    buffer_days: int = Field(..., ge=0, description="Days of stock remaining before stockout")
    safety_stock: float = Field(..., ge=0.0, description="Configured safety stock threshold")
    target_stock: float = Field(..., ge=0.0, description="Target replenishment inventory level")
    required_qty: float = Field(..., gt=0.0, description="Recommended replenishment quantity")
    urgency: UrgencyLevel = Field(..., description="Assessed urgency level")
    shortage_reason: str = Field(..., description="Explanation of deficit cause")
    detected_at: datetime = Field(default_factory=datetime.utcnow, description="Timestamp of detection")

    @model_validator(mode="after")
    def validate_inventory_math(self):
        calculated_available = max(0.0, self.on_hand_qty - self.reserved_qty)
        if abs(self.available_qty - calculated_available) > 1e-4:
            raise ValueError(
                f"available_qty ({self.available_qty}) must equal on_hand_qty ({self.on_hand_qty}) "
                f"- reserved_qty ({self.reserved_qty}) = {calculated_available}"
            )
        return self
