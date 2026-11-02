"""Heuristic Baseline (Baseline A).
Selects the cheapest qualified supplier regardless of delivery lead time or downtime risk.
Used as the benchmark comparison for the proposed multi-agent system.
"""
import time
from typing import Any, Dict
from services.erp_db_mcp.server import get_component_inventory, get_qualified_suppliers


def run_heuristic_baseline(
    component_id: str,
    required_qty: float,
    buffer_days: int,
    downtime_cost_per_day: float,
    delay_days: int = 0,
) -> Dict[str, Any]:
    """Executes the conventional rule-based reorder policy:
    Selects the lowest price supplier meeting hard MOQ and capacity.
    """
    start_time = time.perf_counter()

    suppliers = get_qualified_suppliers(component_id=component_id, required_qty=required_qty)
    if not suppliers:
        return {
            "selected_supplier_id": "NONE",
            "realized_cost": 0.0,
            "downtime_cost": 0.0,
            "total_cost": 0.0,
            "latency_ms": (time.perf_counter() - start_time) * 1000,
        }

    # Baseline A: Sort strictly by unit price ascending
    suppliers.sort(key=lambda s: s["unit_price"])
    cheapest = suppliers[0]

    unit_price = float(cheapest["unit_price"])
    shipping = float(cheapest["shipping_cost"])
    lead_time = int(cheapest["lead_time_days"]) + delay_days

    procurement_cost = (unit_price * required_qty) + shipping
    overdue_days = max(0, lead_time - buffer_days)
    downtime_cost = overdue_days * downtime_cost_per_day
    total_cost = procurement_cost + downtime_cost
    elapsed_ms = (time.perf_counter() - start_time) * 1000

    return {
        "selected_supplier_id": cheapest["supplier_id"],
        "selected_supplier_name": cheapest["supplier_name"],
        "unit_price": unit_price,
        "lead_time_days": lead_time,
        "realized_procurement_cost": procurement_cost,
        "downtime_cost": downtime_cost,
        "total_realized_cost": total_cost,
        "machine_latency_ms": elapsed_ms,
    }
