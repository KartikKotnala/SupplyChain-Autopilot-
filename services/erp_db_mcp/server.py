"""FastMCP Server 1: erp-db-mcp
Provides parameterized, read-only ERP database tools for component inventory and qualified suppliers.
No arbitrary SQL is exposed to agents.
"""
import os
import sys
from typing import Any, Dict, List, Optional
from fastmcp import FastMCP
from sqlalchemy import select

# Ensure project root is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from services.backend.app.models.database import (
    ComponentInventory,
    SupplierCatalog,
    get_session,
)

mcp = FastMCP("erp-db-mcp")


@mcp.tool()
def get_component_inventory(component_id: str) -> Dict[str, Any]:
    """Retrieve verified component inventory, burn rate, and safety stock thresholds.
    
    Args:
        component_id: The unique identifier of the component (e.g. 'COMP-001').
    
    Returns:
        Dictionary containing stock levels, burn rate, buffer days, and criticality.
    """
    session = get_session()
    try:
        comp = session.query(ComponentInventory).filter_by(component_id=component_id.strip()).first()
        if not comp:
            return {
                "error": f"Component '{component_id}' not found in ERP inventory records.",
                "found": False,
            }
        
        available_qty = max(0.0, float(comp.on_hand_qty) - float(comp.reserved_qty))
        burn_rate = float(comp.daily_burn_rate)
        buffer_days = int(available_qty // burn_rate) if burn_rate > 0 else 999

        return {
            "found": True,
            "component_id": comp.component_id,
            "name": comp.name,
            "unit": comp.unit,
            "on_hand_qty": float(comp.on_hand_qty),
            "reserved_qty": float(comp.reserved_qty),
            "available_qty": available_qty,
            "safety_stock": float(comp.safety_stock),
            "target_stock": float(comp.target_stock),
            "daily_burn_rate": burn_rate,
            "buffer_days": buffer_days,
            "downtime_cost_per_day": float(comp.downtime_cost_per_day),
            "budget_limit": float(comp.budget_limit),
            "criticality": comp.criticality,
        }
    finally:
        session.close()


@mcp.tool()
def get_qualified_suppliers(component_id: str, required_qty: float) -> List[Dict[str, Any]]:
    """Retrieve pre-qualified, active suppliers capable of fulfilling the requested component and quantity.
    
    Filters out suppliers that are inactive, technically non-compliant, or have insufficient capacity or MOQ.
    
    Args:
        component_id: The target component ID (e.g. 'COMP-001').
        required_qty: The required purchase quantity.
        
    Returns:
        List of qualified supplier catalog profiles.
    """
    session = get_session()
    try:
        suppliers = session.query(SupplierCatalog).filter(
            SupplierCatalog.component_id == component_id.strip(),
            SupplierCatalog.is_active == True,
            SupplierCatalog.technical_compliant == True,
            SupplierCatalog.capacity >= required_qty,
            SupplierCatalog.moq <= required_qty,
        ).all()

        results = []
        for s in suppliers:
            results.append({
                "supplier_id": s.supplier_id,
                "component_id": s.component_id,
                "supplier_name": s.supplier_name,
                "unit_price": float(s.unit_price),
                "shipping_cost": float(s.shipping_cost),
                "lead_time_days": int(s.lead_time_days),
                "capacity": float(s.capacity),
                "moq": float(s.moq),
                "reliability_score": float(s.reliability_score),
                "is_active": s.is_active,
                "technical_compliant": s.technical_compliant,
            })
        return results
    finally:
        session.close()


if __name__ == "__main__":
    mcp.run()
