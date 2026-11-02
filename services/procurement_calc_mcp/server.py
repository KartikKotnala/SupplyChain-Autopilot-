"""FastMCP Server 2: procurement-calc-mcp
Provides deterministic mathematical calculations for multi-criteria supplier scoring
and three-way invoice reconciliation. No LLM reasoning or hallucination.
"""
from typing import Any, Dict, List, Optional
from fastmcp import FastMCP

mcp = FastMCP("procurement-calc-mcp")


@mcp.tool()
def calculate_tradeoff_score(
    quotes: List[Dict[str, Any]],
    required_qty: float,
    buffer_days: int,
    downtime_cost_per_day: float,
    budget_limit: float,
    component_criticality: str = "HIGH",
    w_cost: float = 0.45,
    w_lead_time: float = 0.35,
    w_reliability: float = 0.20,
) -> Dict[str, Any]:
    """Deterministically score and rank supplier quotations using acquisition cost,
    estimated downtime implications, and supplier reliability risk.
    
    Args:
        quotes: List of vendor quote dictionaries.
        required_qty: Total units required.
        buffer_days: Days of current inventory remaining before stockout.
        downtime_cost_per_day: Daily factory downtime penalty cost.
        budget_limit: Component procurement budget threshold.
        component_criticality: Criticality rating (CRITICAL, HIGH, MEDIUM, LOW).
        w_cost: Cost weight (sums to 1.0 with w_lead_time and w_reliability).
        w_lead_time: Lead time weight.
        w_reliability: Reliability weight.
        
    Returns:
        Structured breakdown with rankings, selected supplier, costs, and approval triggers.
    """
    # Validate weights
    weight_sum = w_cost + w_lead_time + w_reliability
    if abs(weight_sum - 1.0) > 1e-4:
        # Auto-normalize if slight floating drift
        w_cost /= weight_sum
        w_lead_time /= weight_sum
        w_reliability /= weight_sum

    scored_candidates = []
    
    # Policy bounds for fixed normalization (avoids distortion in small quote sets)
    cost_ceiling = max(budget_limit * 1.5, 1000.0)
    lead_time_ceiling = 20.0  # Max expected lead time in days

    for q in quotes:
        sup_id = q.get("supplier_id", "UNKNOWN")
        sup_name = q.get("supplier_name", sup_id)
        unit_price = float(q.get("unit_price", 0.0))
        shipping = float(q.get("shipping_cost", 0.0))
        lead_time = int(q.get("lead_time_days", 1))
        reliability = float(q.get("reliability_score", 0.9))
        capacity = float(q.get("capacity", 999999.0))
        moq = float(q.get("moq", 1.0))
        tech_ok = bool(q.get("technical_compliance", True))

        # Check hard constraints
        is_feasible = True
        disqualify_reason = None
        if not tech_ok:
            is_feasible = False
            disqualify_reason = "Technical specifications non-compliant"
        elif capacity < required_qty:
            is_feasible = False
            disqualify_reason = f"Capacity ({capacity}) < required ({required_qty})"
        elif moq > required_qty:
            is_feasible = False
            disqualify_reason = f"MOQ ({moq}) > required ({required_qty})"

        # Cost calculations
        acq_cost = (unit_price * required_qty) + shipping
        delay_days = max(0, lead_time - buffer_days)
        downtime_cost = delay_days * downtime_cost_per_day
        total_est_cost = acq_cost + downtime_cost

        # Fixed-bound normalization (0.0 to 1.0, lower is better)
        norm_cost = min(1.0, max(0.0, acq_cost / cost_ceiling))
        norm_lead_time = min(1.0, max(0.0, lead_time / lead_time_ceiling))
        norm_reliability_risk = min(1.0, max(0.0, 1.0 - reliability))

        # Composite score (lower is better)
        composite_score = (
            (w_cost * norm_cost) +
            (w_lead_time * norm_lead_time) +
            (w_reliability * norm_reliability_risk)
        )

        scored_candidates.append({
            "supplier_id": sup_id,
            "supplier_name": sup_name,
            "unit_price": unit_price,
            "shipping_cost": shipping,
            "lead_time_days": lead_time,
            "reliability_score": reliability,
            "acquisition_cost": round(acq_cost, 2),
            "estimated_downtime_cost": round(downtime_cost, 2),
            "estimated_total_cost": round(total_est_cost, 2),
            "norm_acquisition_cost": round(norm_cost, 4),
            "norm_lead_time": round(norm_lead_time, 4),
            "norm_reliability_risk": round(norm_reliability_risk, 4),
            "weighted_score": round(composite_score, 4),
            "is_feasible": is_feasible,
            "disqualification_reason": disqualify_reason,
        })

    # Filter feasible candidates and sort by weighted score (ascending)
    feasible = [c for c in scored_candidates if c["is_feasible"]]
    infeasible = [c for c in scored_candidates if not c["is_feasible"]]

    feasible.sort(key=lambda x: x["weighted_score"])

    # Assign ranks
    for idx, c in enumerate(feasible, start=1):
        c["rank"] = idx
    for idx, c in enumerate(infeasible, start=len(feasible) + 1):
        c["rank"] = idx

    all_ranked = feasible + infeasible

    if not feasible:
        return {
            "has_feasible_supplier": False,
            "selected_supplier": None,
            "scores": all_ranked,
            "approval_required": True,
            "escalation_reasons": ["No supplier satisfied mandatory procurement constraints."],
            "rationale": "All evaluated supplier quotes violated hard constraints (capacity, MOQ, or specifications).",
        }

    winner = feasible[0]
    escalation_reasons = []

    # Approval governance checks:
    # 1. Budget check
    if winner["acquisition_cost"] > budget_limit:
        escalation_reasons.append(
            f"Acquisition cost (₹{winner['acquisition_cost']:,.2f}) exceeds budget limit (₹{budget_limit:,.2f})."
        )
    # 2. Criticality & delay check (both component criticality AND delivery breach)
    if winner["lead_time_days"] > buffer_days and component_criticality.upper() in ["CRITICAL", "HIGH"]:
        escalation_reasons.append(
            f"Delivery lead time ({winner['lead_time_days']} days) exceeds buffer ({buffer_days} days) for {component_criticality} component."
        )
    # 3. Single qualified supplier monopoly risk
    if len(feasible) == 1:
        escalation_reasons.append("Single qualified supplier available (monopoly risk).")
    # 4. Low reliability check
    if winner["reliability_score"] < 0.85:
        escalation_reasons.append(f"Supplier reliability ({winner['reliability_score']:.2f}) is below the 0.85 threshold.")

    approval_required = len(escalation_reasons) > 0

    rationale = (
        f"Selected {winner['supplier_name']} ({winner['supplier_id']}) with lowest composite score "
        f"{winner['weighted_score']:.4f} (Acquisition: ₹{winner['acquisition_cost']:,.2f}, "
        f"Lead Time: {winner['lead_time_days']} days, Reliability: {winner['reliability_score']:.0%})."
    )

    return {
        "has_feasible_supplier": True,
        "selected_supplier_id": winner["supplier_id"],
        "selected_supplier_name": winner["supplier_name"],
        "selected_acquisition_cost": winner["acquisition_cost"],
        "selected_estimated_downtime_cost": winner["estimated_downtime_cost"],
        "selected_estimated_total_cost": winner["estimated_total_cost"],
        "scores": all_ranked,
        "approval_required": approval_required,
        "escalation_reasons": escalation_reasons,
        "rationale": rationale,
    }


@mcp.tool()
def verify_three_way_match(
    po_id: str,
    po_qty: float,
    po_unit: str,
    po_unit_price: float,
    goods_receipt_ref: Optional[str],
    received_qty: Optional[float],
    received_unit: Optional[str],
    invoice_ref: str,
    invoiced_qty: float,
    invoiced_unit: str,
    invoiced_unit_price: float,
    price_tolerance: float = 0.01,
) -> Dict[str, Any]:
    """Perform deterministic three-way matching across Purchase Order, Goods Receipt Note,
    and Vendor Invoice. Detects quantity, price, unit, and missing receipt discrepancies.
    
    Args:
        po_id: Purchase Order identifier.
        po_qty: Ordered quantity on PO.
        po_unit: Measurement unit on PO.
        po_unit_price: Contracted unit price on PO.
        goods_receipt_ref: Goods Receipt Note (GRN) reference.
        received_qty: Actual received quantity at warehouse.
        received_unit: Measurement unit on GRN.
        invoice_ref: Vendor Invoice identifier.
        invoiced_qty: Billed quantity on invoice.
        invoiced_unit: Measurement unit on invoice.
        invoiced_unit_price: Billed unit price on invoice.
        price_tolerance: Permitted price rounding tolerance.
        
    Returns:
        Structured match outcome with discrepancy classifications.
    """
    discrepancies = []

    # 1. Missing Goods Receipt Note
    if not goods_receipt_ref or received_qty is None:
        discrepancies.append({
            "discrepancy_type": "MISSING_RECEIPT",
            "field_name": "goods_receipt_ref",
            "expected_value": "Valid GRN",
            "actual_value": str(goods_receipt_ref),
            "difference": None,
            "description": "Invoice cannot be reconciled without a confirmed Goods Receipt Note.",
        })
        received_qty = 0.0
        received_unit = po_unit

    # 2. Unit mismatch check
    units = {po_unit.lower().strip(), received_unit.lower().strip(), invoiced_unit.lower().strip()}
    if len(units) > 1:
        discrepancies.append({
            "discrepancy_type": "UNIT_MISMATCH",
            "field_name": "unit",
            "expected_value": po_unit,
            "actual_value": f"PO: {po_unit}, GRN: {received_unit}, Inv: {invoiced_unit}",
            "difference": None,
            "description": f"Discrepancy in measurement units across documents.",
        })

    # 3. Quantity mismatch check: PO Qty == Received Qty == Invoiced Qty
    if abs(invoiced_qty - received_qty) > 1e-4:
        discrepancies.append({
            "discrepancy_type": "QTY_MISMATCH",
            "field_name": "quantity",
            "expected_value": f"Received: {received_qty}",
            "actual_value": f"Invoiced: {invoiced_qty}",
            "difference": round(invoiced_qty - received_qty, 2),
            "description": f"Invoiced quantity ({invoiced_qty}) does not match warehouse received quantity ({received_qty}).",
        })
    elif abs(invoiced_qty - po_qty) > 1e-4:
        discrepancies.append({
            "discrepancy_type": "QTY_MISMATCH",
            "field_name": "quantity",
            "expected_value": f"PO: {po_qty}",
            "actual_value": f"Invoiced: {invoiced_qty}",
            "difference": round(invoiced_qty - po_qty, 2),
            "description": f"Invoiced quantity ({invoiced_qty}) differs from contracted PO quantity ({po_qty}).",
        })

    # 4. Price mismatch check: PO Price == Invoiced Price
    price_diff = round(invoiced_unit_price - po_unit_price, 2)
    if abs(price_diff) > price_tolerance:
        discrepancies.append({
            "discrepancy_type": "PRICE_MISMATCH",
            "field_name": "unit_price",
            "expected_value": f"₹{po_unit_price:,.2f}",
            "actual_value": f"₹{invoiced_unit_price:,.2f}",
            "difference": price_diff,
            "description": f"Invoiced unit price differs from contracted PO unit price by ₹{price_diff:,.2f}.",
        })

    has_discrepancy = len(discrepancies) > 0
    if not goods_receipt_ref:
        match_status = "UNMATCHED"
    elif has_discrepancy:
        match_status = "DISCREPANCY"
    else:
        match_status = "MATCHED"

    return {
        "po_id": po_id,
        "goods_receipt_ref": goods_receipt_ref,
        "invoice_ref": invoice_ref,
        "match_status": match_status,
        "has_discrepancy": has_discrepancy,
        "discrepancies": discrepancies,
        "po_qty": po_qty,
        "po_unit": po_unit,
        "po_unit_price": po_unit_price,
        "received_qty": received_qty,
        "received_unit": received_unit,
        "invoiced_qty": invoiced_qty,
        "invoiced_unit": invoiced_unit,
        "invoiced_unit_price": invoiced_unit_price,
    }


if __name__ == "__main__":
    mcp.run()
