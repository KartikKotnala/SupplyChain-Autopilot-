"""Integration test for the Week 4 Walking Skeleton.
Tests the complete end-to-end procurement lifecycle from shortage detection to 3-way matching.
"""
import pytest
from data.seed.seed_data import seed_database
from services.adk_orchestrator.orchestrator import (
    execute_procurement_workflow,
    complete_approved_workflow,
)
from services.backend.app.models.database import (
    ProcurementWorkflow,
    OrderAndInvoice,
    BlackboardEntry,
    get_session,
)


@pytest.fixture(scope="module", autouse=True)
def prepare_database():
    seed_database()


def test_walking_skeleton_lifecycle():
    session = get_session()
    # Clean previous test workflows if any
    session.query(OrderAndInvoice).delete()
    session.query(BlackboardEntry).delete()
    session.query(ProcurementWorkflow).delete()
    session.commit()
    session.close()

    # 1. Trigger workflow on COMP-001 (Compressor, which has low stock)
    wf_id = "wf-skeleton-001"
    output = execute_procurement_workflow(
        component_id="COMP-001",
        workflow_id=wf_id,
        architecture="HYBRID",
        seed=42,
    )

    # Verify Stage 1 (Shortage Alert)
    assert output.workflow_id == wf_id
    assert output.shortage_summary.component_id == "COMP-001"
    assert output.shortage_summary.buffer_days == 3
    assert output.shortage_summary.required_qty == 50.0  # target (65) - available (15) = 50

    # Verify Stage 2 & 3 (RFQ & Risk Decision)
    assert output.rfq_summary is not None
    assert len(output.rfq_summary.quotes) >= 3
    assert output.risk_decision is not None
    # In a 3-day buffer scenario, SUP-002 (3 days lead time) avoids massive downtime costs!
    assert output.risk_decision.selected_supplier_id == "SUP-002"

    # Verify Governance & Approval Gate
    session = get_session()
    wf_record = session.query(ProcurementWorkflow).filter_by(workflow_id=wf_id).first()
    assert wf_record is not None

    if output.status == "PENDING_HITL":
        # PO must NOT be created yet!
        po_count = session.query(OrderAndInvoice).filter_by(workflow_id=wf_id).count()
        assert po_count == 0

        # Now simulate Manager Approval
        final_output = complete_approved_workflow(
            workflow_id=wf_id,
            actor="Jane Doe (Procurement Director)",
            decision="APPROVED",
            comments="Approved for immediate production replenishment.",
            shortage=output.shortage_summary,
            rfq_quotes=output.rfq_summary,
            risk_decision=output.risk_decision,
        )

        assert final_output.status == "COMPLETED"
        assert final_output.po_reference is not None
        assert final_output.po_reference.startswith("PO-")
        assert final_output.invoice_audit is not None
        assert final_output.invoice_audit.match_status.value == "MATCHED"

        # Verify PO is now recorded in database
        po_record = session.query(OrderAndInvoice).filter_by(workflow_id=wf_id).first()
        assert po_record is not None
        assert po_record.po_id == final_output.po_reference
        assert po_record.match_status == "MATCHED"

    elif output.status == "COMPLETED":
        # Auto-approved branch
        assert output.po_reference is not None
        assert output.invoice_audit.match_status.value == "MATCHED"

    # Verify Blackboard entries were persisted across frameworks
    bb_entries = session.query(BlackboardEntry).filter_by(workflow_id=wf_id).all()
    artifact_types = [e.artifact_type for e in bb_entries]
    frameworks = {e.framework for e in bb_entries}

    assert "ShortageAlert" in artifact_types
    assert "RFQAndQuotesList" in artifact_types
    assert "RiskDecision" in artifact_types
    assert "InvoiceAuditResult" in artifact_types
    assert "ADK" in frameworks
    assert "CrewAI" in frameworks

    session.close()


def test_duplicate_workflow_prevention():
    # Attempting to start another workflow for an already active or pending component
    # should be rejected by the deduplication policy
    session = get_session()
    # Ensure there is a pending or running workflow for COMP-001
    active = session.query(ProcurementWorkflow).filter(
        ProcurementWorkflow.component_id == "COMP-001",
        ProcurementWorkflow.status.in_(["RUNNING", "PENDING_HITL", "APPROVED"]),
    ).first()

    if active:
        active.status = "PENDING_HITL"
        session.commit()

        with pytest.raises(ValueError, match="already exists"):
            execute_procurement_workflow(
                component_id="COMP-001",
                workflow_id="wf-duplicate-test",
            )
    session.close()
