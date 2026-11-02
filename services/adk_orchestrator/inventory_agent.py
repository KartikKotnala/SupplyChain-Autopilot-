"""Inventory Monitoring Agent (Google ADK).
Queries erp-db-mcp, evaluates stock buffers against production burn rate,
and produces ShortageAlert artifacts when safety stocks are breached.
"""
from datetime import datetime
from typing import Optional

from contracts.shortage import ShortageAlert, UrgencyLevel
from services.erp_db_mcp.server import get_component_inventory
from services.backend.app.models.database import BlackboardEntry, get_session


def run_inventory_monitoring_agent(
    component_id: str,
    workflow_id: str,
    trace_id: Optional[str] = None,
) -> Optional[ShortageAlert]:
    """Evaluates component inventory and returns ShortageAlert if replenish is required."""
    inv = get_component_inventory(component_id=component_id)
    if not inv.get("found"):
        raise ValueError(f"Component '{component_id}' does not exist in inventory.")

    available = inv["available_qty"]
    safety_stock = inv["safety_stock"]
    target_stock = inv["target_stock"]
    burn_rate = inv["daily_burn_rate"]
    buffer_days = inv["buffer_days"]
    criticality = inv["criticality"].upper()

    # Shortage rule: Available stock at or below safety stock threshold
    if available <= safety_stock:
        required = max(1.0, target_stock - available)
        
        # Determine urgency level based on buffer days and criticality
        if buffer_days <= 3 or criticality == "CRITICAL":
            urgency = UrgencyLevel.CRITICAL
        elif buffer_days <= 7 or criticality == "HIGH":
            urgency = UrgencyLevel.HIGH
        elif buffer_days <= 14:
            urgency = UrgencyLevel.MEDIUM
        else:
            urgency = UrgencyLevel.LOW

        shortage_reason = (
            f"Available stock ({available:.0f} {inv['unit']}) is at or below safety stock "
            f"({safety_stock:.0f} {inv['unit']}). Buffer: {buffer_days} days at burn rate {burn_rate:.1f}/day."
        )

        alert = ShortageAlert(
            component_id=component_id,
            component_name=inv["name"],
            on_hand_qty=inv["on_hand_qty"],
            reserved_qty=inv["reserved_qty"],
            available_qty=available,
            daily_burn_rate=burn_rate,
            buffer_days=buffer_days,
            safety_stock=safety_stock,
            target_stock=target_stock,
            required_qty=required,
            urgency=urgency,
            shortage_reason=shortage_reason,
            detected_at=datetime.utcnow(),
        )

        # Persist to Blackboard
        session = get_session()
        try:
            bb_entry = BlackboardEntry(
                workflow_id=workflow_id,
                artifact_type="ShortageAlert",
                step_name="inventory_shortage_detection",
                producer_agent="ADK_InventoryAgent",
                framework="ADK",
                payload=alert.model_dump(mode="json"),
                version=1,
                trace_id=trace_id,
            )
            session.add(bb_entry)
            session.commit()
        finally:
            session.close()

        return alert

    return None
