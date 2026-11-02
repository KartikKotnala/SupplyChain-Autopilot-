"""Contract 4: InvoiceAuditResult
Defines the output of the Logistics & Three-Way Match Agent (CrewAI).
"""
from datetime import datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class DiscrepancyType(str, Enum):
    PRICE_MISMATCH = "PRICE_MISMATCH"
    QTY_MISMATCH = "QTY_MISMATCH"
    UNIT_MISMATCH = "UNIT_MISMATCH"
    MISSING_RECEIPT = "MISSING_RECEIPT"
    TAX_MISMATCH = "TAX_MISMATCH"
    UNKNOWN = "UNKNOWN"


class MatchStatus(str, Enum):
    MATCHED = "MATCHED"
    DISCREPANCY = "DISCREPANCY"
    UNMATCHED = "UNMATCHED"


class DiscrepancyDetail(BaseModel):
    discrepancy_type: DiscrepancyType
    field_name: str
    expected_value: str
    actual_value: str
    difference: Optional[float] = None
    description: str


class InvoiceAuditResult(BaseModel):
    """Result of deterministic 3-way matching across PO, GRN, and Invoice."""
    workflow_id: str
    po_id: str
    goods_receipt_ref: Optional[str] = None
    invoice_ref: str
    supplier_id: str
    
    # 3-Way document records
    po_qty: float = Field(..., ge=0.0)
    po_unit: str
    po_unit_price: float = Field(..., ge=0.0)
    
    received_qty: float = Field(..., ge=0.0)
    received_unit: str
    
    invoiced_qty: float = Field(..., ge=0.0)
    invoiced_unit: str
    invoiced_unit_price: float = Field(..., ge=0.0)
    
    # Outcome
    match_status: MatchStatus
    has_discrepancy: bool = Field(
        ...,
        description="True if any discrepancy was detected (positive class in confusion matrix)"
    )
    discrepancies: List[DiscrepancyDetail] = Field(default_factory=list)
    audit_notes: Optional[str] = None
    audited_at: datetime = Field(default_factory=datetime.utcnow)
