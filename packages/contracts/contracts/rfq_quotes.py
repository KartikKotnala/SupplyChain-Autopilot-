"""Contract 2: RFQAndQuotesList
Defines standardized RFQs drafted by CrewAI and structured quotes simulated/collected.
"""
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


class RFQPayload(BaseModel):
    """The formal Request for Quotation drafted by Supplier Discovery & RFQ Agent."""
    rfq_id: str = Field(..., description="Unique RFQ reference, e.g. RFQ-COMP001-20261102")
    workflow_id: str = Field(..., description="Associated workflow identifier")
    component_id: str = Field(..., description="Target component identifier")
    component_name: str = Field(..., description="Target component name")
    required_qty: float = Field(..., gt=0.0, description="Requested purchase quantity")
    required_by_buffer_days: int = Field(..., ge=0, description="Available buffer before stockout")
    hard_constraints: dict = Field(
        default_factory=dict,
        description="Mandatory constraints e.g. {'max_lead_time_days': 10, 'min_reliability': 0.85}"
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)


class SupplierQuote(BaseModel):
    """Structured vendor quotation response."""
    quote_id: str = Field(..., description="Unique quotation ID, e.g. QUOTE-SUP001-01")
    supplier_id: str = Field(..., description="Supplier identifier, e.g. SUP-001")
    supplier_name: str = Field(..., description="Legal vendor name")
    unit_price: float = Field(..., gt=0.0, description="Price per unit in local currency (e.g. INR)")
    quoted_quantity: float = Field(..., gt=0.0, description="Quantity vendor commits to deliver")
    lead_time_days: int = Field(..., ge=1, description="Delivery lead time in calendar days")
    shipping_cost: float = Field(default=0.0, ge=0.0, description="Quoted freight/shipping cost")
    capacity: float = Field(..., gt=0.0, description="Supplier monthly production capacity")
    moq: float = Field(default=1.0, gt=0.0, description="Minimum Order Quantity required by vendor")
    reliability_score: float = Field(..., ge=0.0, le=1.0, description="Historical supplier reliability rating (0 to 1)")
    technical_compliance: bool = Field(default=True, description="Whether quote matches technical specs")
    quote_valid: bool = Field(default=True, description="Whether quotation remains active/unexpired")


class RFQAndQuotesList(BaseModel):
    """Collection of quotes returned across A2A from CrewAI to ADK."""
    workflow_id: str = Field(..., description="Active workflow identifier")
    rfq: RFQPayload = Field(..., description="Associated RFQ record")
    eligible_suppliers: List[str] = Field(default_factory=list, description="IDs of suppliers passing qualifications")
    quotes: List[SupplierQuote] = Field(default_factory=list, description="List of validated supplier quotations")
    simulator_seed: Optional[int] = Field(None, description="Reproducibility seed used for simulation")
    generated_at: datetime = Field(default_factory=datetime.utcnow)
