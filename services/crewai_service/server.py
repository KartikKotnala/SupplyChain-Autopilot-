"""CrewAI A2A Service - FastAPI Server.
Exposes the Agent Card at `/.well-known/agent-card.json` and implements the A2A protocol
for task delegation from the Google ADK Master Orchestrator.
"""
import os
import sys
from typing import Any, Dict, Optional
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

# Ensure project root is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from services.crewai_service.agents import run_sourcing_and_rfq_crew, run_invoice_audit_crew

app = FastAPI(title="CrewAI A2A Service", version="1.0.0")

# Agent Card conforming to A2A specification
AGENT_CARD = {
    "protocol_version": "1.0",
    "name": "CrewAI Sourcing and Logistics Service",
    "description": "Specialized CrewAI agent service providing supplier discovery, RFQ generation, quotation simulation, and 3-way invoice reconciliation.",
    "endpoints": {
        "message_send": "/api/a2a/message/send"
    },
    "capabilities": [
        {
            "name": "sourcing_and_rfq",
            "description": "Discovers qualified suppliers for component deficits, drafts RFQ payloads, and simulates validated quotations.",
            "input_schema": {
                "workflow_id": "string",
                "component_id": "string",
                "component_name": "string",
                "required_qty": "number",
                "buffer_days": "integer",
                "trace_id": "string (optional)",
                "seed": "integer (optional)"
            },
            "output_schema": "RFQAndQuotesList"
        },
        {
            "name": "invoice_three_way_match",
            "description": "Performs 3-way reconciliation across Purchase Order, Goods Receipt Note, and Vendor Invoice.",
            "input_schema": {
                "workflow_id": "string",
                "po_id": "string",
                "po_qty": "number",
                "po_unit": "string",
                "po_unit_price": "number",
                "goods_receipt_ref": "string (optional)",
                "received_qty": "number (optional)",
                "received_unit": "string (optional)",
                "invoice_ref": "string",
                "invoiced_qty": "number",
                "invoiced_unit": "string",
                "invoiced_unit_price": "number",
                "supplier_id": "string",
                "trace_id": "string (optional)"
            },
            "output_schema": "InvoiceAuditResult"
        }
    ]
}


class A2AMessageRequest(BaseModel):
    capability: str = Field(..., description="Target capability: 'sourcing_and_rfq' or 'invoice_three_way_match'")
    workflow_id: str
    trace_id: Optional[str] = None
    payload: Dict[str, Any] = Field(..., description="Capability input parameters")


class A2AMessageResponse(BaseModel):
    status: str = Field(..., description="'SUCCESS' or 'ERROR'")
    capability: str
    workflow_id: str
    trace_id: Optional[str] = None
    artifact: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


@app.get("/.well-known/agent-card.json")
def get_agent_card():
    """A2A protocol discovery endpoint returning the Agent Card."""
    return AGENT_CARD


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "CrewAI A2A Service"}


@app.post("/api/a2a/message/send", response_model=A2AMessageResponse)
@app.post("/message/send", response_model=A2AMessageResponse)
def handle_a2a_message(req: A2AMessageRequest):
    """A2A message handler handling task execution requests from ADK."""
    try:
        if req.capability == "sourcing_and_rfq":
            p = req.payload
            result = run_sourcing_and_rfq_crew(
                workflow_id=req.workflow_id,
                component_id=p["component_id"],
                component_name=p.get("component_name", p["component_id"]),
                required_qty=float(p["required_qty"]),
                buffer_days=int(p.get("buffer_days", 0)),
                trace_id=req.trace_id,
                seed=p.get("seed", 42),
            )
            return A2AMessageResponse(
                status="SUCCESS",
                capability=req.capability,
                workflow_id=req.workflow_id,
                trace_id=req.trace_id,
                artifact=result.model_dump(mode="json"),
            )

        elif req.capability == "invoice_three_way_match":
            p = req.payload
            result = run_invoice_audit_crew(
                workflow_id=req.workflow_id,
                po_id=p["po_id"],
                po_qty=float(p["po_qty"]),
                po_unit=p.get("po_unit", "units"),
                po_unit_price=float(p["po_unit_price"]),
                goods_receipt_ref=p.get("goods_receipt_ref"),
                received_qty=float(p["received_qty"]) if p.get("received_qty") is not None else None,
                received_unit=p.get("received_unit"),
                invoice_ref=p["invoice_ref"],
                invoiced_qty=float(p["invoiced_qty"]),
                invoiced_unit=p.get("invoiced_unit", "units"),
                invoiced_unit_price=float(p["invoiced_unit_price"]),
                supplier_id=p.get("supplier_id", "UNKNOWN"),
                trace_id=req.trace_id,
            )
            return A2AMessageResponse(
                status="SUCCESS",
                capability=req.capability,
                workflow_id=req.workflow_id,
                trace_id=req.trace_id,
                artifact=result.model_dump(mode="json"),
            )

        else:
            raise HTTPException(status_code=400, detail=f"Unsupported capability: {req.capability}")

    except Exception as e:
        return A2AMessageResponse(
            status="ERROR",
            capability=req.capability,
            workflow_id=req.workflow_id,
            trace_id=req.trace_id,
            error=str(e),
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
