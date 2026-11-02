"""Contract 3: RiskDecision
Defines the output of the Risk & Trade-Off Optimization Agent (Google ADK).
"""
from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel, Field, model_validator


class WeightConfig(BaseModel):
    w_cost: float = Field(0.45, ge=0.0, le=1.0, description="Weight for normalized acquisition cost")
    w_lead_time: float = Field(0.35, ge=0.0, le=1.0, description="Weight for normalized delivery lead time")
    w_reliability: float = Field(0.20, ge=0.0, le=1.0, description="Weight for reliability risk (1 - reliability)")

    @model_validator(mode="after")
    def validate_sum(self):
        total = self.w_cost + self.w_lead_time + self.w_reliability
        if abs(total - 1.0) > 1e-4:
            raise ValueError(f"Weights must sum to 1.0, got {total}")
        return self


class SupplierScoreBreakdown(BaseModel):
    supplier_id: str
    supplier_name: str
    acquisition_cost: float = Field(..., ge=0.0, description="UnitPrice * Qty + ShippingCost")
    estimated_downtime_cost: float = Field(..., ge=0.0, description="DowntimeCostPerDay * max(0, LeadTime - Buffer)")
    estimated_total_cost: float = Field(..., ge=0.0, description="AcquisitionCost + EstimatedDowntimeCost")
    
    # Normalized components (0.0 to 1.0, lower is better)
    norm_acquisition_cost: float = Field(..., ge=0.0, le=1.0)
    norm_lead_time: float = Field(..., ge=0.0, le=1.0)
    norm_reliability_risk: float = Field(..., ge=0.0, le=1.0)
    
    weighted_score: float = Field(..., ge=0.0, le=1.0, description="Weighted composite score; lower is better")
    rank: int = Field(..., ge=1, description="Ranking among qualified candidates (1 = best)")
    is_feasible: bool = Field(default=True, description="Whether candidate satisfies all hard constraints")
    disqualification_reason: Optional[str] = None


class RiskDecision(BaseModel):
    """Authoritative procurement decision artifact produced by ADK Risk Agent."""
    workflow_id: str
    component_id: str
    selected_supplier_id: str
    selected_supplier_name: str
    selected_suppliers: List[str] = Field(
        default_factory=list,
        description="List of selected supplier IDs (length 1 in v1.0, extensible for Phase 2 splits)"
    )
    weights: WeightConfig
    scores: List[SupplierScoreBreakdown] = Field(default_factory=list)
    
    selected_acquisition_cost: float = Field(..., ge=0.0)
    selected_estimated_downtime_cost: float = Field(..., ge=0.0)
    selected_estimated_total_cost: float = Field(..., ge=0.0)
    
    approval_required: bool = Field(default=False)
    escalation_reasons: List[str] = Field(default_factory=list)
    rationale: str = Field(..., description="Deterministic and explanatory rationale for the selection")
    calculated_at: datetime = Field(default_factory=datetime.utcnow)
