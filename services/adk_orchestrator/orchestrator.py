"""Google ADK Master Orchestrator.
Coordinates the end-to-end procurement workflow across ADK agents, CrewAI A2A service,
PostgreSQL Blackboard, and deterministic FastMCP calculation tools.
"""
from datetime import datetime
from typing import Any, Dict, Optional
import uuid

from contracts.shortage import ShortageAlert
from contracts.rfq_quotes import RFQAndQuotesList
from contracts.risk import RiskDecision, WeightConfig
from contracts.invoice import InvoiceAuditResult
from contracts.final_output import FinalWorkflowOutput

from services.erp_db_mcp.server import get_component_inventory
from services.adk_orchestrator.callbacks import ADKAgentCallback, MCPToolCallback
from services.adk_orchestrator.inventory_agent import run_inventory_monitoring_agent
from services.adk_orchestrator.risk_agent import run_risk_optimization_agent
from services.crewai_service.agents import run_sourcing_and_rfq_crew, run_invoice_audit_crew
from services.backend.app.models.database import (
    ProcurementWorkflow,
    OrderAndInvoice,
    BlackboardEntry,
    get_session,
)


def execute_procurement_workflow(
    component_id: str,
    workflow_id: Optional[str] = None,
    architecture: str = "HYBRID",
    weights: Optional[WeightConfig] = None,
    seed: Optional[int] = 42,
    trace_id: Optional[str] = None,
) -> FinalWorkflowOutput:
    """Executes the autonomous procurement workflow for a target component."""
    wf_id = workflow_id or f"wf-{uuid.uuid4().hex[:8]}"
    t_id = trace_id or f"trace-{uuid.uuid4().hex[:12]}"
    session = get_session()

    try:
        # 1. Deduplication / Idempotency Check
        existing_active = session.query(ProcurementWorkflow).filter(
            ProcurementWorkflow.component_id == component_id,
            ProcurementWorkflow.status.in_(["RUNNING", "PENDING_HITL"]),
        ).first()

        if existing_active:
            raise ValueError(
                f"Active procurement workflow '{existing_active.workflow_id}' already exists "
                f"for component '{component_id}' in state '{existing_active.status}'."
            )

        # 2. Stage 1: Inventory Analysis (ADK Inventory Agent)
        inv_cb = ADKAgentCallback("ADK_InventoryAgent", wf_id, t_id)
        inv_cb.before_agent_callback({"component_id": component_id})
        try:
            shortage = run_inventory_monitoring_agent(
                component_id=component_id,
                workflow_id=wf_id,
                trace_id=t_id,
            )
            inv_cb.after_agent_callback({"has_shortage": shortage is not None})
        except Exception as e:
            inv_cb.on_error_callback(e)
            raise

        if not shortage:
            # Healthy inventory - no procurement required
            inv = get_component_inventory(component_id)
            dummy_alert = ShortageAlert(
                component_id=component_id,
                component_name=inv.get("name", component_id),
                on_hand_qty=inv.get("on_hand_qty", 0.0),
                reserved_qty=inv.get("reserved_qty", 0.0),
                available_qty=inv.get("available_qty", 0.0),
                daily_burn_rate=inv.get("daily_burn_rate", 1.0),
                buffer_days=inv.get("buffer_days", 999),
                safety_stock=inv.get("safety_stock", 0.0),
                target_stock=inv.get("target_stock", 0.0),
                required_qty=1.0,
                urgency="LOW",
                shortage_reason="Inventory healthy: Usable stock exceeds safety threshold.",
            )
            return FinalWorkflowOutput(
                workflow_id=wf_id,
                status="NO_SHORTAGE",
                shortage_summary=dummy_alert,
                trace_id=t_id,
            )

        # Record initial workflow in database (Single Source of Truth)
        wf_record = ProcurementWorkflow(
            workflow_id=wf_id,
            component_id=component_id,
            required_qty=shortage.required_qty,
            buffer_days=shortage.buffer_days,
            status="RUNNING",
            approval_required=False,
        )
        session.add(wf_record)
        session.commit()

        # 3. Stage 2: Sourcing & RFQ (Delegated to CrewAI)
        rfq_quotes = run_sourcing_and_rfq_crew(
            workflow_id=wf_id,
            component_id=component_id,
            component_name=shortage.component_name,
            required_qty=shortage.required_qty,
            buffer_days=shortage.buffer_days,
            trace_id=t_id,
            seed=seed,
        )

        # 4. Stage 3: Risk & Trade-Off Optimization (ADK Risk Agent)
        risk_cb = ADKAgentCallback("ADK_RiskAgent", wf_id, t_id)
        risk_cb.before_agent_callback({"quotes_count": len(rfq_quotes.quotes)})
        try:
            inv_data = get_component_inventory(component_id)
            downtime_cost = inv_data.get("downtime_cost_per_day", 10000.0)
            budget_limit = inv_data.get("budget_limit", 50000.0)
            criticality = inv_data.get("criticality", "HIGH")

            risk_decision = run_risk_optimization_agent(
                workflow_id=wf_id,
                component_id=component_id,
                quotes_list=rfq_quotes,
                buffer_days=shortage.buffer_days,
                downtime_cost_per_day=downtime_cost,
                budget_limit=budget_limit,
                component_criticality=criticality,
                weights=weights,
                trace_id=t_id,
            )
            risk_cb.after_agent_callback({
                "selected_supplier": risk_decision.selected_supplier_id,
                "approval_required": risk_decision.approval_required,
            })
        except Exception as e:
            risk_cb.on_error_callback(e)
            raise

        # Update workflow record with decision metrics
        wf_record.selected_supplier_id = risk_decision.selected_supplier_id
        wf_record.estimated_total_cost = risk_decision.selected_estimated_total_cost
        wf_record.approval_required = risk_decision.approval_required
        session.commit()

        # 5. Stage 4: Feasibility & Human Approval Gate
        if risk_decision.selected_supplier_id == "NONE":
            wf_record.status = "NO_FEASIBLE_SUPPLIER"
            wf_record.escalation_reason = "; ".join(risk_decision.escalation_reasons)
            session.commit()

            output = FinalWorkflowOutput(
                workflow_id=wf_id,
                status="NO_FEASIBLE_SUPPLIER",
                shortage_summary=shortage,
                rfq_summary=rfq_quotes,
                risk_decision=risk_decision,
                escalation_reason=wf_record.escalation_reason,
                trace_id=t_id,
            )
            wf_record.final_report_md = output.to_markdown()
            session.commit()
            return output

        if risk_decision.approval_required:
            # Pause workflow for Human-in-the-Loop decision
            wf_record.status = "PENDING_HITL"
            wf_record.approval_status = "PENDING"
            wf_record.escalation_reason = "; ".join(risk_decision.escalation_reasons)
            session.commit()

            output = FinalWorkflowOutput(
                workflow_id=wf_id,
                status="PENDING_HITL",
                shortage_summary=shortage,
                rfq_summary=rfq_quotes,
                risk_decision=risk_decision,
                escalation_reason=wf_record.escalation_reason,
                trace_id=t_id,
            )
            wf_record.final_report_md = output.to_markdown()
            session.commit()
            return output

        # 6. Automatic Approval -> Proceed directly to PO & Reconciliation
        wf_record.approval_status = "AUTO_APPROVED"
        session.commit()

        return complete_approved_workflow(
            workflow_id=wf_id,
            actor="SYSTEM_AUTO_POLICY",
            decision="APPROVED",
            comments="Automatically approved under configured risk and budget policy.",
            shortage=shortage,
            rfq_quotes=rfq_quotes,
            risk_decision=risk_decision,
            trace_id=t_id,
        )

    finally:
        session.close()


def complete_approved_workflow(
    workflow_id: str,
    actor: str = "Manager",
    decision: str = "APPROVED",
    comments: str = "",
    shortage: Optional[ShortageAlert] = None,
    rfq_quotes: Optional[RFQAndQuotesList] = None,
    risk_decision: Optional[RiskDecision] = None,
    trace_id: Optional[str] = None,
) -> FinalWorkflowOutput:
    """Resumes and completes an approved procurement workflow:
    1. Records manager decision.
    2. Issues Purchase Order.
    3. Simulates delivery goods receipt.
    4. Triggers 3-way invoice reconciliation via CrewAI.
    """
    session = get_session()
    try:
        wf = session.query(ProcurementWorkflow).filter_by(workflow_id=workflow_id).first()
        if not wf:
            raise ValueError(f"Workflow '{workflow_id}' not found.")

        # If rejected, finalize without creating PO
        if decision.upper() == "REJECTED":
            wf.status = "REJECTED"
            wf.approval_status = "REJECTED"
            wf.approval_actor = actor
            wf.approval_timestamp = datetime.utcnow()
            session.commit()

            return FinalWorkflowOutput(
                workflow_id=workflow_id,
                status="REJECTED",
                shortage_summary=shortage,
                rfq_summary=rfq_quotes,
                risk_decision=risk_decision,
                approval_decision={
                    "decision": "REJECTED",
                    "actor": actor,
                    "comments": comments,
                    "timestamp": datetime.utcnow().isoformat(),
                },
                escalation_reason=f"Rejected by {actor}: {comments}",
                trace_id=trace_id,
            )

        # Approved -> Update workflow status
        wf.status = "APPROVED"
        wf.approval_status = "APPROVED"
        wf.approval_actor = actor
        wf.approval_timestamp = datetime.utcnow()
        session.commit()

        # Retrieve Blackboard artifacts if not provided in-memory
        if not shortage:
            bb_shortage = session.query(BlackboardEntry).filter_by(
                workflow_id=workflow_id, artifact_type="ShortageAlert"
            ).first()
            if bb_shortage:
                shortage = ShortageAlert(**bb_shortage.payload)

        if not rfq_quotes:
            bb_rfq = session.query(BlackboardEntry).filter_by(
                workflow_id=workflow_id, artifact_type="RFQAndQuotesList"
            ).first()
            if bb_rfq:
                rfq_quotes = RFQAndQuotesList(**bb_rfq.payload)

        if not risk_decision:
            bb_risk = session.query(BlackboardEntry).filter_by(
                workflow_id=workflow_id, artifact_type="RiskDecision"
            ).first()
            if bb_risk:
                risk_decision = RiskDecision(**bb_risk.payload)

        # 7. Create Purchase Order (Strictly Post-Approval)
        po_id = f"PO-{datetime.utcnow().strftime('%Y%m%d')}-{workflow_id[:6].upper()}"
        winner_supplier_id = wf.selected_supplier_id
        
        # Find winner quote for price
        selected_quote = next(
            (q for q in rfq_quotes.quotes if q.supplier_id == winner_supplier_id), None
        ) if rfq_quotes else None
        
        unit_price = selected_quote.unit_price if selected_quote else 800.0

        # Simulate Logistics Goods Receipt & Vendor Invoice
        grn_ref = f"GRN-{po_id[3:]}"
        inv_ref = f"INV-{winner_supplier_id}-{po_id[3:]}"

        # Run 3-Way Invoice Audit via CrewAI
        invoice_audit = run_invoice_audit_crew(
            workflow_id=workflow_id,
            po_id=po_id,
            po_qty=wf.required_qty,
            po_unit="units",
            po_unit_price=unit_price,
            goods_receipt_ref=grn_ref,
            received_qty=wf.required_qty,
            received_unit="units",
            invoice_ref=inv_ref,
            invoiced_qty=wf.required_qty,
            invoiced_unit="units",
            invoiced_unit_price=unit_price,
            supplier_id=winner_supplier_id,
            trace_id=trace_id,
        )

        # Persist PO & Invoice record to orders_and_invoices table
        order_rec = OrderAndInvoice(
            po_id=po_id,
            workflow_id=workflow_id,
            supplier_id=winner_supplier_id,
            po_qty=wf.required_qty,
            po_unit="units",
            po_unit_price=unit_price,
            goods_receipt_ref=grn_ref,
            received_qty=wf.required_qty,
            received_unit="units",
            invoice_ref=inv_ref,
            invoiced_qty=wf.required_qty,
            invoiced_unit="units",
            invoiced_unit_price=unit_price,
            match_status=invoice_audit.match_status.value,
            discrepancies_jsonb=[d.model_dump(mode="json") for d in invoice_audit.discrepancies],
        )
        session.add(order_rec)

        # Mark workflow final status
        final_status = "COMPLETED" if not invoice_audit.has_discrepancy else "DISCREPANCY_FLAGGED"
        wf.status = final_status
        session.commit()

        final_output = FinalWorkflowOutput(
            workflow_id=workflow_id,
            status=final_status,
            shortage_summary=shortage,
            rfq_summary=rfq_quotes,
            risk_decision=risk_decision,
            approval_decision={
                "decision": decision,
                "actor": actor,
                "comments": comments,
                "timestamp": wf.approval_timestamp.isoformat() if wf.approval_timestamp else None,
            },
            po_reference=po_id,
            invoice_audit=invoice_audit,
            trace_id=trace_id,
        )

        wf.final_report_md = final_output.to_markdown()
        session.commit()
        return final_output

    finally:
        session.close()
