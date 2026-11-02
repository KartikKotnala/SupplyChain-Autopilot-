"""Unit tests for the two FastMCP servers: erp-db-mcp and procurement-calc-mcp."""
import pytest
from services.erp_db_mcp.server import get_component_inventory, get_qualified_suppliers
from services.procurement_calc_mcp.server import calculate_tradeoff_score, verify_three_way_match
from data.seed.seed_data import seed_database


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    seed_database()


def test_erp_get_component_inventory():
    res = get_component_inventory("COMP-001")
    assert res["found"] is True
    assert res["component_id"] == "COMP-001"
    assert res["available_qty"] == 15.0  # 20 on hand - 5 reserved
    assert res["buffer_days"] == 3       # 15 available / 5 burn rate
    assert res["criticality"] == "CRITICAL"

    # Not found
    not_found = get_component_inventory("COMP-999")
    assert not_found["found"] is False


def test_erp_get_qualified_suppliers():
    suppliers = get_qualified_suppliers("COMP-001", 30.0)
    assert len(suppliers) >= 3
    # Check that all returned suppliers can fulfill >= 30 qty
    for s in suppliers:
        assert s["capacity"] >= 30.0
        assert s["moq"] <= 30.0
        assert s["is_active"] is True
        assert s["technical_compliant"] is True


def test_procurement_calc_tradeoff_scoring():
    quotes = [
        {
            "supplier_id": "SUP-001",
            "supplier_name": "Vendor A",
            "unit_price": 800.0,
            "shipping_cost": 500.0,
            "lead_time_days": 10,
            "reliability_score": 0.92,
            "capacity": 200.0,
            "moq": 10.0,
            "technical_compliance": True,
        },
        {
            "supplier_id": "SUP-002",
            "supplier_name": "Vendor B",
            "unit_price": 950.0,
            "shipping_cost": 400.0,
            "lead_time_days": 3,
            "reliability_score": 0.98,
            "capacity": 150.0,
            "moq": 5.0,
            "technical_compliance": True,
        },
        {
            "supplier_id": "SUP-003",
            "supplier_name": "Vendor C",
            "unit_price": 850.0,
            "shipping_cost": 450.0,
            "lead_time_days": 6,
            "reliability_score": 0.95,
            "capacity": 180.0,
            "moq": 10.0,
            "technical_compliance": True,
        },
    ]

    # Required: 35 units, buffer: 3 days, downtime: 15,000/day
    res = calculate_tradeoff_score(
        quotes=quotes,
        required_qty=35.0,
        buffer_days=3,
        downtime_cost_per_day=15000.0,
        budget_limit=50000.0,
        component_criticality="CRITICAL",
    )

    assert res["has_feasible_supplier"] is True
    # In tight buffer situations, SUP-002 has 3 days lead time (0 delay, 0 downtime cost)
    # SUP-001 has 10 days lead time (7 days delay = ₹105,000 downtime cost!)
    assert res["selected_supplier_id"] == "SUP-002"
    assert res["selected_estimated_downtime_cost"] == 0.0


def test_three_way_match_clean():
    res = verify_three_way_match(
        po_id="PO-001",
        po_qty=35.0,
        po_unit="units",
        po_unit_price=950.0,
        goods_receipt_ref="GRN-001",
        received_qty=35.0,
        received_unit="units",
        invoice_ref="INV-001",
        invoiced_qty=35.0,
        invoiced_unit="units",
        invoiced_unit_price=950.0,
    )
    assert res["match_status"] == "MATCHED"
    assert res["has_discrepancy"] is False
    assert len(res["discrepancies"]) == 0


def test_three_way_match_price_discrepancy():
    res = verify_three_way_match(
        po_id="PO-001",
        po_qty=35.0,
        po_unit="units",
        po_unit_price=950.0,
        goods_receipt_ref="GRN-001",
        received_qty=35.0,
        received_unit="units",
        invoice_ref="INV-002",
        invoiced_qty=35.0,
        invoiced_unit="units",
        invoiced_unit_price=1050.0,  # Overbilled!
    )
    assert res["match_status"] == "DISCREPANCY"
    assert res["has_discrepancy"] is True
    assert any(d["discrepancy_type"] == "PRICE_MISMATCH" for d in res["discrepancies"])


def test_three_way_match_quantity_discrepancy():
    res = verify_three_way_match(
        po_id="PO-001",
        po_qty=35.0,
        po_unit="units",
        po_unit_price=950.0,
        goods_receipt_ref="GRN-001",
        received_qty=30.0,  # Only 30 received
        received_unit="units",
        invoice_ref="INV-003",
        invoiced_qty=35.0,  # Billed for 35!
        invoiced_unit="units",
        invoiced_unit_price=950.0,
    )
    assert res["match_status"] == "DISCREPANCY"
    assert res["has_discrepancy"] is True
    assert any(d["discrepancy_type"] == "QTY_MISMATCH" for d in res["discrepancies"])


def test_three_way_match_missing_receipt():
    res = verify_three_way_match(
        po_id="PO-001",
        po_qty=35.0,
        po_unit="units",
        po_unit_price=950.0,
        goods_receipt_ref=None,
        received_qty=None,
        received_unit=None,
        invoice_ref="INV-004",
        invoiced_qty=35.0,
        invoiced_unit="units",
        invoiced_unit_price=950.0,
    )
    assert res["match_status"] == "UNMATCHED"
    assert res["has_discrepancy"] is True
    assert any(d["discrepancy_type"] == "MISSING_RECEIPT" for d in res["discrepancies"])
