"""CrewAI Agent implementations for Sourcing/RFQ and Logistics/Invoice Reconciliation.
These agents execute inside the CrewAI A2A microservice.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from contracts.rfq_quotes import RFQAndQuotesList, RFQPayload, SupplierQuote
from contracts.invoice import InvoiceAuditResult, MatchStatus, DiscrepancyDetail, DiscrepancyType
from services.erp_db_mcp.server import get_qualified_suppliers
from services.procurement_calc_mcp.server import verify_three_way_match
from services.crewai_service.quote_simulator import simulate_vendor_quotes
from services.backend.app.models.database import BlackboardEntry, get_session


def run_sourcing_and_rfq_crew(
    workflow_id: str,
    component_id: str,
    component_name: str,
    required_qty: float,
    buffer_days: int,
    trace_id: Optional[str] = None,
    seed: Optional[int] = None,
) -> RFQAndQuotesList:
    """Executes the CrewAI Supplier Discovery & RFQ flow.
    
    1. Fetches qualified suppliers via ERP database tool.
    2. Drafts formal RFQ payload.
    3. Simulates/collects vendor quotations.
    4. Persists RFQAndQuotesList artifact to PostgreSQL Blackboard.
    5. Returns typed Pydantic contract.
    """
    # 1. Tool Call: Get qualified suppliers
    qualified = get_qualified_suppliers(component_id=component_id, required_qty=required_qty)
    eligible_supplier_ids = [s["supplier_id"] for s in qualified]

    # 2. Draft RFQ
    rfq = RFQPayload(
        rfq_id=f"RFQ-{component_id}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
        workflow_id=workflow_id,
        component_id=component_id,
        component_name=component_name,
        required_qty=required_qty,
        required_by_buffer_days=buffer_days,
        hard_constraints={
            "max_lead_time_days": max(buffer_days + 7, 14),
            "min_reliability": 0.75,
            "min_capacity": required_qty,
        },
    )

    # 3. Simulate quotes
    quotes = simulate_vendor_quotes(
        qualified_suppliers=qualified,
        required_qty=required_qty,
        seed=seed,
        allow_variation=False,
    )

    result = RFQAndQuotesList(
        workflow_id=workflow_id,
        rfq=rfq,
        eligible_suppliers=eligible_supplier_ids,
        quotes=quotes,
        simulator_seed=seed,
    )

    # 4. Persist to Blackboard
    session = get_session()
    try:
        bb_entry = BlackboardEntry(
            workflow_id=workflow_id,
            artifact_type="RFQAndQuotesList",
            step_name="supplier_discovery_rfq",
            producer_agent="CrewAI_SourcingAgent",
            framework="CrewAI",
            payload=result.model_dump(mode="json"),
            version=1,
            trace_id=trace_id,
        )
        session.add(bb_entry)
        session.commit()
    finally:
        session.close()

    return result


def run_invoice_audit_crew(
    workflow_id: str,
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
    supplier_id: str,
    trace_id: Optional[str] = None,
) -> InvoiceAuditResult:
    """Executes the CrewAI Logistics & Three-Way Match Agent flow."""
    # Call deterministic calculator tool
    raw_match = verify_three_way_match(
        po_id=po_id,
        po_qty=po_qty,
        po_unit=po_unit,
        po_unit_price=po_unit_price,
        goods_receipt_ref=goods_receipt_ref,
        received_qty=received_qty,
        received_unit=received_unit,
        invoice_ref=invoice_ref,
        invoiced_qty=invoiced_qty,
        invoiced_unit=invoiced_unit,
        invoiced_unit_price=invoiced_unit_price,
    )

    discrepancies = [
        DiscrepancyDetail(
            discrepancy_type=DiscrepancyType(d["discrepancy_type"]),
            field_name=d["field_name"],
            expected_value=d["expected_value"],
            actual_value=d["actual_value"],
            difference=d["difference"],
            description=d["description"],
        )
        for d in raw_match["discrepancies"]
    ]

    result = InvoiceAuditResult(
        workflow_id=workflow_id,
        po_id=po_id,
        goods_receipt_ref=goods_receipt_ref,
        invoice_ref=invoice_ref,
        supplier_id=supplier_id,
        po_qty=po_qty,
        po_unit=po_unit,
        po_unit_price=po_unit_price,
        received_qty=raw_match["received_qty"],
        received_unit=raw_match["received_unit"],
        invoiced_qty=invoiced_qty,
        invoiced_unit=invoiced_unit,
        invoiced_unit_price=invoiced_unit_price,
        match_status=MatchStatus(raw_match["match_status"]),
        has_discrepancy=raw_match["has_discrepancy"],
        discrepancies=discrepancies,
        audit_notes="Reconciled via CrewAI Logistics & Invoice Audit Agent",
    )

    # Persist to Blackboard
    session = get_session()
    try:
        bb_entry = BlackboardEntry(
            workflow_id=workflow_id,
            artifact_type="InvoiceAuditResult",
            step_name="invoice_three_way_match",
            producer_agent="CrewAI_LogisticsInvoiceAgent",
            framework="CrewAI",
            payload=result.model_dump(mode="json"),
            version=1,
            trace_id=trace_id,
        )
        session.add(bb_entry)
        session.commit()
    finally:
        session.close()

    return result
