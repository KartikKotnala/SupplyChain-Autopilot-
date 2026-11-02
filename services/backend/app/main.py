"""FastAPI Application Backend for SupplyChain Autopilot.
Exposes REST APIs for inventory monitoring, workflow execution, HITL approval,
what-if trade-off simulation, three-way invoice matching, and benchmark analysis.
"""
import os
import sys
from typing import Any, Dict, List, Optional
from datetime import datetime

from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Ensure project root is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))

from services.backend.app.models.database import (
    ComponentInventory,
    SupplierCatalog,
    ProcurementWorkflow,
    OrderAndInvoice,
    BlackboardEntry,
    BenchmarkRun,
    get_session,
    init_db,
)
from services.adk_orchestrator.orchestrator import (
    execute_procurement_workflow,
    complete_approved_workflow,
)
from services.procurement_calc_mcp.server import calculate_tradeoff_score, verify_three_way_match
from services.backend.app.guardrails.input_guardrail import (
    scan_untrusted_text,
    validate_procurement_input_bounds,
)
from contracts.risk import WeightConfig

# Initialize database on startup
init_db()

app = FastAPI(
    title="SupplyChain Autopilot API",
    description="Multi-agent procurement and supply chain risk management backend.",
    version="1.0.0",
)

# Enable CORS for React Frontend (typically running on localhost:5173 or localhost:3000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request & Response Schemas
# ---------------------------------------------------------------------------
class WorkflowRunRequest(BaseModel):
    component_id: str
    architecture: str = Field("HYBRID", description="HYBRID, SEQUENTIAL, or PURE_BLACKBOARD")
    w_cost: Optional[float] = 0.45
    w_lead_time: Optional[float] = 0.35
    w_reliability: Optional[float] = 0.20
    seed: Optional[int] = 42


class DecisionRequest(BaseModel):
    decision: str = Field(..., description="'APPROVED' or 'REJECTED'")
    actor: str = Field("Jane Doe (Procurement Director)", description="Name/title of approving manager")
    comments: Optional[str] = Field("Approved for operational continuity.", description="Manager rationale")


class WhatIfRequest(BaseModel):
    w_cost: float = Field(0.45, ge=0.0, le=1.0)
    w_lead_time: float = Field(0.35, ge=0.0, le=1.0)
    w_reliability: float = Field(0.20, ge=0.0, le=1.0)


class InvoiceReconcileRequest(BaseModel):
    po_id: str
    po_qty: float
    po_unit: str = "units"
    po_unit_price: float
    goods_receipt_ref: Optional[str] = None
    received_qty: Optional[float] = None
    received_unit: Optional[str] = "units"
    invoice_ref: str
    invoiced_qty: float
    invoiced_unit: str = "units"
    invoiced_unit_price: float
    invoice_notes: Optional[str] = None


class GuardrailTestRequest(BaseModel):
    input_text: str


# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------
@app.get("/api/health")
def health():
    return {
        "status": "HEALTHY",
        "timestamp": datetime.utcnow().isoformat(),
        "database": "CONNECTED",
        "agentic_frameworks": ["Google ADK", "CrewAI"],
        "inter_agent_protocol": "A2A v1.0",
    }


@app.get("/api/inventory")
def list_inventory():
    """Returns component inventory, stock levels, burn rate, and buffer status."""
    session = get_session()
    try:
        components = session.query(ComponentInventory).all()
        results = []
        for c in components:
            avail = max(0.0, float(c.on_hand_qty) - float(c.reserved_qty))
            burn = float(c.daily_burn_rate)
            buf = int(avail // burn) if burn > 0 else 999
            is_shortage = avail <= float(c.safety_stock)

            results.append({
                "component_id": c.component_id,
                "name": c.name,
                "unit": c.unit,
                "on_hand_qty": float(c.on_hand_qty),
                "reserved_qty": float(c.reserved_qty),
                "available_qty": avail,
                "safety_stock": float(c.safety_stock),
                "target_stock": float(c.target_stock),
                "daily_burn_rate": burn,
                "buffer_days": buf,
                "downtime_cost_per_day": float(c.downtime_cost_per_day),
                "budget_limit": float(c.budget_limit),
                "criticality": c.criticality,
                "is_shortage": is_shortage,
            })
        return results
    finally:
        session.close()


@app.post("/api/workflows/run")
def run_workflow(req: WorkflowRunRequest):
    """Initiates an autonomous procurement workflow for the requested component."""
    # Scan input for guardrails
    g_res = scan_untrusted_text(req.component_id)
    if g_res.blocked:
        raise HTTPException(status_code=400, detail=g_res.reason)

    try:
        weights = None
        if req.w_cost is not None and req.w_lead_time is not None and req.w_reliability is not None:
            weights = WeightConfig(
                w_cost=req.w_cost,
                w_lead_time=req.w_lead_time,
                w_reliability=req.w_reliability,
            )

        output = execute_procurement_workflow(
            component_id=req.component_id,
            architecture=req.architecture,
            weights=weights,
            seed=req.seed,
        )
        return output.model_dump(mode="json")
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Workflow execution failed: {str(e)}")


@app.get("/api/workflows")
def list_workflows():
    """Lists recent procurement workflows."""
    session = get_session()
    try:
        wfs = session.query(ProcurementWorkflow).order_by(ProcurementWorkflow.created_at.desc()).all()
        return [
            {
                "workflow_id": w.workflow_id,
                "component_id": w.component_id,
                "required_qty": w.required_qty,
                "buffer_days": w.buffer_days,
                "status": w.status,
                "selected_supplier_id": w.selected_supplier_id,
                "estimated_total_cost": w.estimated_total_cost,
                "approval_required": w.approval_required,
                "approval_status": w.approval_status,
                "escalation_reason": w.escalation_reason,
                "created_at": w.created_at.isoformat() if w.created_at else None,
            }
            for w in wfs
        ]
    finally:
        session.close()


@app.get("/api/workflows/{workflow_id}")
def get_workflow_details(workflow_id: str):
    """Fetches comprehensive details, blackboard artifacts, and final report for a workflow."""
    session = get_session()
    try:
        wf = session.query(ProcurementWorkflow).filter_by(workflow_id=workflow_id).first()
        if not wf:
            raise HTTPException(status_code=404, detail=f"Workflow '{workflow_id}' not found.")

        # Fetch blackboard entries
        bb_entries = session.query(BlackboardEntry).filter_by(workflow_id=workflow_id).order_by(
            BlackboardEntry.created_at.asc()
        ).all()

        artifacts = [
            {
                "entry_id": e.entry_id,
                "artifact_type": e.artifact_type,
                "step_name": e.step_name,
                "producer_agent": e.producer_agent,
                "framework": e.framework,
                "payload": e.payload,
                "version": e.version,
                "trace_id": e.trace_id,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in bb_entries
        ]

        # Fetch PO and invoice match if available
        po_record = session.query(OrderAndInvoice).filter_by(workflow_id=workflow_id).first()
        po_data = None
        if po_record:
            po_data = {
                "po_id": po_record.po_id,
                "supplier_id": po_record.supplier_id,
                "po_qty": po_record.po_qty,
                "po_unit_price": po_record.po_unit_price,
                "goods_receipt_ref": po_record.goods_receipt_ref,
                "received_qty": po_record.received_qty,
                "invoice_ref": po_record.invoice_ref,
                "invoiced_qty": po_record.invoiced_qty,
                "invoiced_unit_price": po_record.invoiced_unit_price,
                "match_status": po_record.match_status,
                "discrepancies": po_record.discrepancies_jsonb,
            }

        return {
            "workflow_id": wf.workflow_id,
            "component_id": wf.component_id,
            "required_qty": wf.required_qty,
            "buffer_days": wf.buffer_days,
            "status": wf.status,
            "selected_supplier_id": wf.selected_supplier_id,
            "estimated_total_cost": wf.estimated_total_cost,
            "approval_required": wf.approval_required,
            "approval_status": wf.approval_status,
            "approval_actor": wf.approval_actor,
            "approval_timestamp": wf.approval_timestamp.isoformat() if wf.approval_timestamp else None,
            "escalation_reason": wf.escalation_reason,
            "final_report_md": wf.final_report_md,
            "artifacts": artifacts,
            "order_and_invoice": po_data,
        }
    finally:
        session.close()


@app.post("/api/workflows/{workflow_id}/decide")
def submit_approval_decision(workflow_id: str, req: DecisionRequest):
    """Processes manager approval or rejection for a pending workflow."""
    # Scan manager comment
    g_res = scan_untrusted_text(req.comments)
    if g_res.blocked:
        raise HTTPException(status_code=400, detail=g_res.reason)

    try:
        final_output = complete_approved_workflow(
            workflow_id=workflow_id,
            actor=req.actor,
            decision=req.decision,
            comments=g_res.sanitized_text,
        )
        return final_output.model_dump(mode="json")
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process decision: {str(e)}")


@app.post("/api/workflows/{workflow_id}/what-if")
def calculate_what_if(workflow_id: str, req: WhatIfRequest):
    """Recomputes supplier ranking with alternative trade-off weights without modifying state."""
    session = get_session()
    try:
        # Fetch candidate quotes from Blackboard
        bb_quotes = session.query(BlackboardEntry).filter_by(
            workflow_id=workflow_id, artifact_type="RFQAndQuotesList"
        ).first()

        if not bb_quotes:
            raise HTTPException(status_code=404, detail="No RFQ/Quote artifacts found for this workflow.")

        wf = session.query(ProcurementWorkflow).filter_by(workflow_id=workflow_id).first()
        comp = session.query(ComponentInventory).filter_by(component_id=wf.component_id).first()

        raw_quotes = bb_quotes.payload.get("quotes", [])
        recalculated = calculate_tradeoff_score(
            quotes=raw_quotes,
            required_qty=wf.required_qty,
            buffer_days=wf.buffer_days,
            downtime_cost_per_day=comp.downtime_cost_per_day,
            budget_limit=comp.budget_limit,
            component_criticality=comp.criticality,
            w_cost=req.w_cost,
            w_lead_time=req.w_lead_time,
            w_reliability=req.w_reliability,
        )
        return recalculated
    finally:
        session.close()


@app.post("/api/invoices/reconcile")
def reconcile_invoice(req: InvoiceReconcileRequest):
    """Deterministic 3-way invoice matching API."""
    g_res = scan_untrusted_text(req.invoice_notes)
    if g_res.blocked:
        raise HTTPException(status_code=400, detail=g_res.reason)

    res = verify_three_way_match(
        po_id=req.po_id,
        po_qty=req.po_qty,
        po_unit=req.po_unit,
        po_unit_price=req.po_unit_price,
        goods_receipt_ref=req.goods_receipt_ref,
        received_qty=req.received_qty,
        received_unit=req.received_unit,
        invoice_ref=req.invoice_ref,
        invoiced_qty=req.invoiced_qty,
        invoiced_unit=req.invoiced_unit,
        invoiced_unit_price=req.invoiced_unit_price,
    )
    return res


@app.post("/api/guardrails/test")
def test_guardrails(req: GuardrailTestRequest):
    """Tests an input string against security guardrails and prompt injection scanners."""
    res = scan_untrusted_text(req.input_text)
    return res.model_dump()


@app.get("/api/benchmarks/summary")
def get_benchmark_summary():
    """Returns aggregated performance, cost, and latency metrics across architectures and personas."""
    session = get_session()
    try:
        runs = session.query(BenchmarkRun).all()
        if not runs:
            return {"total_runs": 0, "suite_a": [], "suite_b": []}

        # Suite A Aggregation
        architectures = ["BASELINE_A", "SEQUENTIAL", "PURE_BLACKBOARD", "HYBRID"]
        suite_a = []
        base_runs = [r for r in runs if r.architecture == "BASELINE_A"]
        base_avg_cost = sum(r.total_realized_cost_inr for r in base_runs) / len(base_runs) if base_runs else 1.0

        for arch in architectures:
            a_runs = [r for r in runs if r.architecture == arch]
            if not a_runs:
                continue
            avg_cost = sum(r.total_realized_cost_inr for r in a_runs) / len(a_runs)
            avg_dt = sum(r.downtime_cost_inr for r in a_runs) / len(a_runs)
            avg_lat = sum(r.machine_latency_ms for r in a_runs) / len(a_runs)
            savings = ((base_avg_cost - avg_cost) / base_avg_cost) * 100

            suite_a.append({
                "architecture": arch,
                "runs_count": len(a_runs),
                "avg_realized_cost": round(avg_cost, 2),
                "avg_downtime_cost": round(avg_dt, 2),
                "cost_savings_pct": round(savings, 1),
                "avg_latency_ms": round(avg_lat, 2),
            })

        # Suite B Aggregation
        personas = ["COST_FOCUSED", "RISK_CONSCIOUS", "NEUTRAL"]
        suite_b = []
        for p in personas:
            p_runs = [r for r in runs if r.persona == p]
            if not p_runs:
                continue
            avg_cost = sum(r.total_realized_cost_inr for r in p_runs) / len(p_runs)
            avg_dt = sum(r.downtime_cost_inr for r in p_runs) / len(p_runs)
            avg_tok = sum(r.tokens_used for r in p_runs) / len(p_runs)

            suite_b.append({
                "persona": p,
                "runs_count": len(p_runs),
                "avg_realized_cost": round(avg_cost, 2),
                "avg_downtime_cost": round(avg_dt, 2),
                "avg_tokens": int(avg_tok),
            })

        return {
            "total_runs": len(runs),
            "suite_a_architecture": suite_a,
            "suite_b_personas": suite_b,
        }
    finally:
        session.close()


@app.post("/api/benchmarks/run")
def trigger_benchmark_matrix():
    """Runs the full 105-run evaluation matrix and records results."""
    from evaluation.benchmark import run_benchmark_matrix
    results = run_benchmark_matrix()
    return {"status": "SUCCESS", "runs_completed": len(results)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
