"""Unit tests for the 6-table database layer and repository queries."""
import pytest
from services.backend.app.models.database import (
    ComponentInventory,
    SupplierCatalog,
    BlackboardEntry,
    ProcurementWorkflow,
    OrderAndInvoice,
    init_db,
    get_session,
    get_engine,
)


@pytest.fixture(scope="module")
def db_session():
    # Use in-memory SQLite for high-speed isolated unit testing
    engine = init_db(get_engine("sqlite:///:memory:"))
    session = get_session(engine)

    # Insert test component
    comp = ComponentInventory(
        component_id="COMP-TEST",
        name="Test Condenser",
        unit="units",
        on_hand_qty=30.0,
        reserved_qty=5.0,
        safety_stock=20.0,
        target_stock=60.0,
        daily_burn_rate=5.0,
        downtime_cost_per_day=10000.0,
        budget_limit=50000.0,
        criticality="HIGH",
    )
    session.add(comp)

    # Insert test supplier
    sup = SupplierCatalog(
        supplier_id="SUP-TEST-1",
        component_id="COMP-TEST",
        supplier_name="Test Vendor Alpha",
        unit_price=500.0,
        shipping_cost=200.0,
        lead_time_days=4,
        capacity=100.0,
        moq=5.0,
        reliability_score=0.95,
        is_active=True,
        technical_compliant=True,
    )
    session.add(sup)
    session.commit()

    yield session
    session.close()


def test_component_inventory_query(db_session):
    comp = db_session.query(ComponentInventory).filter_by(component_id="COMP-TEST").first()
    assert comp is not None
    assert comp.name == "Test Condenser"
    assert comp.on_hand_qty - comp.reserved_qty == 25.0


def test_supplier_catalog_query(db_session):
    suppliers = db_session.query(SupplierCatalog).filter_by(
        component_id="COMP-TEST", is_active=True
    ).all()
    assert len(suppliers) == 1
    assert suppliers[0].supplier_name == "Test Vendor Alpha"
    assert suppliers[0].lead_time_days == 4


def test_blackboard_entry_versioning(db_session):
    # Test saving versioned blackboard entries
    entry_v1 = BlackboardEntry(
        workflow_id="wf-test-01",
        artifact_type="ShortageAlert",
        step_name="inventory_check",
        producer_agent="InventoryAgent",
        framework="ADK",
        payload={"available_qty": 25.0, "buffer_days": 5},
        version=1,
        trace_id="trace-abc-123",
    )
    db_session.add(entry_v1)
    db_session.commit()

    retrieved = db_session.query(BlackboardEntry).filter_by(
        workflow_id="wf-test-01", artifact_type="ShortageAlert", version=1
    ).first()
    assert retrieved is not None
    assert retrieved.payload["buffer_days"] == 5
    assert retrieved.framework == "ADK"
