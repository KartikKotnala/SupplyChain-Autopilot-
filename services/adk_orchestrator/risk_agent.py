"""Risk & Trade-Off Optimization Agent (Google ADK).
Evaluates supplier alternatives via procurement-calc-mcp and produces RiskDecision artifacts.
"""
from typing import List, Optional

from contracts.rfq_quotes import RFQAndQuotesList, SupplierQuote
from contracts.risk import RiskDecision, SupplierScoreBreakdown, WeightConfig
from services.procurement_calc_mcp.server import calculate_tradeoff_score
from services.backend.app.models.database import BlackboardEntry, get_session


def run_risk_optimization_agent(
    workflow_id: str,
    component_id: str,
    quotes_list: RFQAndQuotesList,
    buffer_days: int,
    downtime_cost_per_day: float,
    budget_limit: float,
    component_criticality: str = "HIGH",
    weights: Optional[WeightConfig] = None,
    trace_id: Optional[str] = None,
) -> RiskDecision:
    """Invokes deterministic calculation tool to rank candidates and check approval policies."""
    w = weights or WeightConfig(w_cost=0.45, w_lead_time=0.35, w_reliability=0.20)
    
    # Format quotes for calculator tool
    raw_quotes = [q.model_dump(mode="json") for q in quotes_list.quotes]

    calc_res = calculate_tradeoff_score(
        quotes=raw_quotes,
        required_qty=quotes_list.rfq.required_qty,
        buffer_days=buffer_days,
        downtime_cost_per_day=downtime_cost_per_day,
        budget_limit=budget_limit,
        component_criticality=component_criticality,
        w_cost=w.w_cost,
        w_lead_time=w.w_lead_time,
        w_reliability=w.w_reliability,
    )

    if not calc_res.get("has_feasible_supplier"):
        # No feasible supplier path
        scores = [
            SupplierScoreBreakdown(
                supplier_id=s["supplier_id"],
                supplier_name=s["supplier_name"],
                acquisition_cost=s["acquisition_cost"],
                estimated_downtime_cost=s["estimated_downtime_cost"],
                estimated_total_cost=s["estimated_total_cost"],
                norm_acquisition_cost=s["norm_acquisition_cost"],
                norm_lead_time=s["norm_lead_time"],
                norm_reliability_risk=s["norm_reliability_risk"],
                weighted_score=s["weighted_score"],
                rank=s["rank"],
                is_feasible=s["is_feasible"],
                disqualification_reason=s["disqualification_reason"],
            )
            for s in calc_res["scores"]
        ]
        decision = RiskDecision(
            workflow_id=workflow_id,
            component_id=component_id,
            selected_supplier_id="NONE",
            selected_supplier_name="None Qualified",
            selected_suppliers=[],
            weights=w,
            scores=scores,
            selected_acquisition_cost=0.0,
            selected_estimated_downtime_cost=0.0,
            selected_estimated_total_cost=0.0,
            approval_required=True,
            escalation_reasons=calc_res["escalation_reasons"],
            rationale=calc_res["rationale"],
        )
    else:
        scores = [
            SupplierScoreBreakdown(
                supplier_id=s["supplier_id"],
                supplier_name=s["supplier_name"],
                acquisition_cost=s["acquisition_cost"],
                estimated_downtime_cost=s["estimated_downtime_cost"],
                estimated_total_cost=s["estimated_total_cost"],
                norm_acquisition_cost=s["norm_acquisition_cost"],
                norm_lead_time=s["norm_lead_time"],
                norm_reliability_risk=s["norm_reliability_risk"],
                weighted_score=s["weighted_score"],
                rank=s["rank"],
                is_feasible=s["is_feasible"],
                disqualification_reason=s.get("disqualification_reason"),
            )
            for s in calc_res["scores"]
        ]

        decision = RiskDecision(
            workflow_id=workflow_id,
            component_id=component_id,
            selected_supplier_id=calc_res["selected_supplier_id"],
            selected_supplier_name=calc_res["selected_supplier_name"],
            selected_suppliers=[calc_res["selected_supplier_id"]],
            weights=w,
            scores=scores,
            selected_acquisition_cost=calc_res["selected_acquisition_cost"],
            selected_estimated_downtime_cost=calc_res["selected_estimated_downtime_cost"],
            selected_estimated_total_cost=calc_res["selected_estimated_total_cost"],
            approval_required=calc_res["approval_required"],
            escalation_reasons=calc_res["escalation_reasons"],
            rationale=calc_res["rationale"],
        )

    # Persist to Blackboard
    session = get_session()
    try:
        bb_entry = BlackboardEntry(
            workflow_id=workflow_id,
            artifact_type="RiskDecision",
            step_name="risk_tradeoff_optimization",
            producer_agent="ADK_RiskAgent",
            framework="ADK",
            payload=decision.model_dump(mode="json"),
            version=1,
            trace_id=trace_id,
        )
        session.add(bb_entry)
        session.commit()
    finally:
        session.close()

    return decision
