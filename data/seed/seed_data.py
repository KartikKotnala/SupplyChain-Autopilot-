"""Seed data script for SupplyChain Autopilot.
Populates simulated refrigerator manufacturing components and qualified suppliers.
"""
from datetime import datetime
from services.backend.app.models.database import (
    ComponentInventory,
    SupplierCatalog,
    get_session,
    init_db,
    get_engine,
)


COMPONENTS = [
    {
        "component_id": "COMP-001",
        "name": "Variable Speed Hermetic Compressor",
        "unit": "units",
        "on_hand_qty": 20.0,
        "reserved_qty": 5.0,
        "safety_stock": 25.0,
        "target_stock": 65.0,
        "daily_burn_rate": 5.0,
        "downtime_cost_per_day": 15000.0,
        "budget_limit": 50000.0,
        "criticality": "CRITICAL",  # Available: 15, Buffer: 3 days -> SHORTAGE ALERT
    },
    {
        "component_id": "COMP-002",
        "name": "Copper Fin-and-Tube Condenser Coil",
        "unit": "units",
        "on_hand_qty": 45.0,
        "reserved_qty": 10.0,
        "safety_stock": 20.0,
        "target_stock": 50.0,
        "daily_burn_rate": 4.0,
        "downtime_cost_per_day": 8000.0,
        "budget_limit": 30000.0,
        "criticality": "HIGH",  # Available: 35, Buffer: 8 days -> HEALTHY
    },
    {
        "component_id": "COMP-003",
        "name": "Roll-Bond Evaporator Plate",
        "unit": "units",
        "on_hand_qty": 35.0,
        "reserved_qty": 15.0,
        "safety_stock": 20.0,
        "target_stock": 45.0,
        "daily_burn_rate": 3.0,
        "downtime_cost_per_day": 7000.0,
        "budget_limit": 25000.0,
        "criticality": "MEDIUM",  # Available: 20, Buffer: 6 days -> ON EDGE
    },
    {
        "component_id": "COMP-004",
        "name": "Microprocessor Inverter Control Board",
        "unit": "units",
        "on_hand_qty": 8.0,
        "reserved_qty": 2.0,
        "safety_stock": 15.0,
        "target_stock": 35.0,
        "daily_burn_rate": 2.0,
        "downtime_cost_per_day": 12000.0,
        "budget_limit": 40000.0,
        "criticality": "CRITICAL",  # Available: 6, Buffer: 3 days -> SHORTAGE ALERT
    },
    {
        "component_id": "COMP-005",
        "name": "Digital Thermostat Sensor Assembly",
        "unit": "units",
        "on_hand_qty": 60.0,
        "reserved_qty": 10.0,
        "safety_stock": 20.0,
        "target_stock": 60.0,
        "daily_burn_rate": 5.0,
        "downtime_cost_per_day": 4000.0,
        "budget_limit": 15000.0,
        "criticality": "LOW",  # Available: 50, Buffer: 10 days -> HEALTHY
    },
]

SUPPLIERS = [
    # COMP-001 (Compressor) Suppliers
    {
        "supplier_id": "SUP-001",
        "component_id": "COMP-001",
        "supplier_name": "Kirloskar Compressors Ltd",
        "unit_price": 800.0,
        "shipping_cost": 500.0,
        "lead_time_days": 10,
        "capacity": 200.0,
        "moq": 10.0,
        "reliability_score": 0.92,
        "is_active": True,
        "technical_compliant": True,
    },
    {
        "supplier_id": "SUP-002",
        "component_id": "COMP-001",
        "supplier_name": "Apex Thermal Systems",
        "unit_price": 950.0,
        "shipping_cost": 400.0,
        "lead_time_days": 3,
        "capacity": 150.0,
        "moq": 5.0,
        "reliability_score": 0.98,
        "is_active": True,
        "technical_compliant": True,
    },
    {
        "supplier_id": "SUP-003",
        "component_id": "COMP-001",
        "supplier_name": "BlueStar Cooling Components",
        "unit_price": 850.0,
        "shipping_cost": 450.0,
        "lead_time_days": 6,
        "capacity": 180.0,
        "moq": 10.0,
        "reliability_score": 0.95,
        "is_active": True,
        "technical_compliant": True,
    },
    {
        "supplier_id": "SUP-004",
        "component_id": "COMP-001",
        "supplier_name": "Budget Coolers Inc",
        "unit_price": 720.0,
        "shipping_cost": 800.0,
        "lead_time_days": 14,
        "capacity": 100.0,
        "moq": 20.0,
        "reliability_score": 0.78,
        "is_active": True,
        "technical_compliant": True,
    },
    # COMP-002 (Condenser) Suppliers
    {
        "supplier_id": "SUP-005",
        "component_id": "COMP-002",
        "supplier_name": "Subros Thermal Ltd",
        "unit_price": 450.0,
        "shipping_cost": 250.0,
        "lead_time_days": 4,
        "capacity": 300.0,
        "moq": 10.0,
        "reliability_score": 0.96,
        "is_active": True,
        "technical_compliant": True,
    },
    # COMP-004 (Control Board) Suppliers
    {
        "supplier_id": "SUP-006",
        "component_id": "COMP-004",
        "supplier_name": "Dixon Embedded Technologies",
        "unit_price": 1200.0,
        "shipping_cost": 300.0,
        "lead_time_days": 4,
        "capacity": 120.0,
        "moq": 5.0,
        "reliability_score": 0.97,
        "is_active": True,
        "technical_compliant": True,
    },
    {
        "supplier_id": "SUP-007",
        "component_id": "COMP-004",
        "supplier_name": "MicroLogic Systems",
        "unit_price": 1050.0,
        "shipping_cost": 400.0,
        "lead_time_days": 8,
        "capacity": 80.0,
        "moq": 10.0,
        "reliability_score": 0.89,
        "is_active": True,
        "technical_compliant": True,
    },
]


def seed_database(db_url: str = None):
    engine = init_db(get_engine(db_url))
    session = get_session(engine)

    try:
        # Seed components
        for comp in COMPONENTS:
            existing = session.query(ComponentInventory).filter_by(component_id=comp["component_id"]).first()
            if not existing:
                session.add(ComponentInventory(**comp))
            else:
                for k, v in comp.items():
                    setattr(existing, k, v)

        # Seed suppliers
        for sup in SUPPLIERS:
            existing = session.query(SupplierCatalog).filter_by(
                supplier_id=sup["supplier_id"], component_id=sup["component_id"]
            ).first()
            if not existing:
                session.add(SupplierCatalog(**sup))
            else:
                for k, v in sup.items():
                    setattr(existing, k, v)

        session.commit()
        print(f"Successfully seeded {len(COMPONENTS)} components and {len(SUPPLIERS)} supplier catalog records.")
    except Exception as e:
        session.rollback()
        print(f"Error seeding database: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    from services.backend.app.models.database import get_engine
    seed_database()
