"""Unit tests for the 5 Pydantic v2 core contracts."""
import pytest
from datetime import datetime
from contracts import (
    ShortageAlert,
    UrgencyLevel,
    RFQPayload,
    SupplierQuote,
    RFQAndQuotesList,
    WeightConfig,
    SupplierScoreBreakdown,
    RiskDecision,
    DiscrepancyType,
    MatchStatus,
    DiscrepancyDetail,
    InvoiceAuditResult,
    FinalWorkflowOutput,
)


def test_shortage_alert_validation():
    # Valid shortage alert
    alert = ShortageAlert(
        component_id="COMP-001",
        component_name="Compressor",
        on_hand_qty=25.0,
        reserved_qty=5.0,
        available_qty=20.0,
        daily_burn_rate=5.0,
        buffer_days=4,
        safety_stock=15.0,
        target_stock=50.0,
        required_qty=30.0,
        urgency=UrgencyLevel.HIGH,
        shortage_reason="Buffer days below lead time threshold",
    )
    assert alert.available_qty == 20.0
    assert alert.buffer_days == 4

    # Invalid available_qty calculation should raise ValueError
    with pytest.raises(ValueError, match="available_qty"):
        ShortageAlert(
            component_id="COMP-001",
            component_name="Compressor",
            on_hand_qty=25.0,
            reserved_qty=5.0,
            available_qty=999.0,  # Invalid!
            daily_burn_rate=5.0,
            buffer_days=4,
            safety_stock=15.0,
            target_stock=50.0,
            required_qty=30.0,
            urgency=UrgencyLevel.HIGH,
            shortage_reason="Deficit",
        )


def test_weight_config_sum():
    # Valid sum = 1.0
    w = WeightConfig(w_cost=0.45, w_lead_time=0.35, w_reliability=0.20)
    assert abs(w.w_cost + w.w_lead_time + w.w_reliability - 1.0) < 1e-4

    # Invalid sum != 1.0
    with pytest.raises(ValueError, match="Weights must sum to 1.0"):
        WeightConfig(w_cost=0.5, w_lead_time=0.5, w_reliability=0.5)


def test_final_output_serialization():
    alert = ShortageAlert(
        component_id="COMP-001",
        component_name="Compressor",
        on_hand_qty=20.0,
        reserved_qty=0.0,
        available_qty=20.0,
        daily_burn_rate=5.0,
        buffer_days=4,
        safety_stock=15.0,
        target_stock=50.0,
        required_qty=30.0,
        urgency=UrgencyLevel.CRITICAL,
        shortage_reason="Projected safety stock breach",
    )

    rd = RiskDecision(
        workflow_id="wf-100",
        component_id="COMP-001",
        selected_supplier_id="SUP-002",
        selected_supplier_name="Apex Refrigeration Components",
        selected_suppliers=["SUP-002"],
        weights=WeightConfig(w_cost=0.45, w_lead_time=0.35, w_reliability=0.20),
        scores=[
            SupplierScoreBreakdown(
                supplier_id="SUP-002",
                supplier_name="Apex Refrigeration Components",
                acquisition_cost=25500.0,
                estimated_downtime_cost=0.0,
                estimated_total_cost=25500.0,
                norm_acquisition_cost=0.2,
                norm_lead_time=0.1,
                norm_reliability_risk=0.05,
                weighted_score=0.135,
                rank=1,
            )
        ],
        selected_acquisition_cost=25500.0,
        selected_estimated_downtime_cost=0.0,
        selected_estimated_total_cost=25500.0,
        approval_required=False,
        rationale="Lowest delivery risk and reliable lead time.",
    )

    final = FinalWorkflowOutput(
        workflow_id="wf-100",
        status="COMPLETED",
        shortage_summary=alert,
        risk_decision=rd,
        po_reference="PO-20261102-01",
    )

    # Test JSON serialization
    json_str = final.to_json_str()
    assert "wf-100" in json_str
    assert "Apex Refrigeration" in json_str

    # Test Markdown output
    md_str = final.to_markdown()
    assert "# SupplyChain Autopilot - Procurement Execution Report" in md_str
    assert "Apex Refrigeration Components" in md_str

    # Test Table rows
    rows = final.to_table_rows()
    assert any(k == "Workflow ID" and v == "wf-100" for k, v in rows)
