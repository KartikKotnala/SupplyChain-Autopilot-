"""Contract 5: FinalWorkflowOutput
Aggregates artifacts and audit data into a canonical final schema with
JSON, Markdown, and table-row serialization.
"""
from datetime import datetime
import json
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field
from tabulate import tabulate

from .shortage import ShortageAlert
from .rfq_quotes import RFQAndQuotesList
from .risk import RiskDecision
from .invoice import InvoiceAuditResult


class FinalWorkflowOutput(BaseModel):
    workflow_id: str
    status: str = Field(..., description="Final workflow status (e.g. COMPLETED, REJECTED, NO_FEASIBLE_SUPPLIER)")
    shortage_summary: ShortageAlert
    rfq_summary: Optional[RFQAndQuotesList] = None
    risk_decision: Optional[RiskDecision] = None
    approval_decision: Optional[Dict[str, Any]] = None
    po_reference: Optional[str] = None
    invoice_audit: Optional[InvoiceAuditResult] = None
    escalation_reason: Optional[str] = None
    trace_id: Optional[str] = None
    generated_at: datetime = Field(default_factory=datetime.utcnow)

    def to_json_str(self, indent: int = 2) -> str:
        """Serializes canonical workflow outcome to JSON string."""
        return self.model_dump_json(indent=indent)

    def to_markdown(self) -> str:
        """Generates executive markdown summary report."""
        lines = [
            f"# SupplyChain Autopilot - Procurement Execution Report",
            f"**Workflow ID**: `{self.workflow_id}` | **Status**: **{self.status}** | **Trace ID**: `{self.trace_id or 'N/A'}`",
            f"*Generated at: {self.generated_at.strftime('%Y-%m-%d %H:%M:%S UTC')}*",
            "",
            "## 1. Inventory & Shortage Summary",
            f"- **Component**: {self.shortage_summary.component_name} (`{self.shortage_summary.component_id}`)",
            f"- **Stock Status**: On-Hand: {self.shortage_summary.on_hand_qty:.0f} | Reserved: {self.shortage_summary.reserved_qty:.0f} | Available: {self.shortage_summary.available_qty:.0f}",
            f"- **Burn Rate**: {self.shortage_summary.daily_burn_rate:.1f}/day | **Buffer Days**: {self.shortage_summary.buffer_days} days",
            f"- **Required Replenishment**: {self.shortage_summary.required_qty:.0f} units | **Urgency**: `{self.shortage_summary.urgency.value}`",
            f"- **Deficit Reason**: {self.shortage_summary.shortage_reason}",
            "",
        ]

        if self.risk_decision:
            rd = self.risk_decision
            lines.extend([
                "## 2. Supplier Discovery & Risk Decision",
                f"- **Selected Supplier**: **{rd.selected_supplier_name}** (`{rd.selected_supplier_id}`)",
                f"- **Acquisition Cost**: ₹{rd.selected_acquisition_cost:,.2f}",
                f"- **Estimated Downtime Cost**: ₹{rd.selected_estimated_downtime_cost:,.2f}",
                f"- **Estimated Total Cost**: **₹{rd.selected_estimated_total_cost:,.2f}**",
                f"- **Approval Required**: `{'YES' if rd.approval_required else 'NO'}`",
                f"- **Rationale**: {rd.rationale}",
                "",
                "### Evaluated Supplier Alternatives:",
            ])
            table_headers = ["Rank", "Supplier", "Acquisition Cost", "Est. Downtime", "Total Cost", "Score", "Feasible"]
            table_rows = []
            for s in rd.scores:
                table_rows.append([
                    s.rank,
                    f"{s.supplier_name} ({s.supplier_id})",
                    f"₹{s.acquisition_cost:,.2f}",
                    f"₹{s.estimated_downtime_cost:,.2f}",
                    f"₹{s.estimated_total_cost:,.2f}",
                    f"{s.weighted_score:.4f}",
                    "Yes" if s.is_feasible else f"No ({s.disqualification_reason})"
                ])
            lines.append(tabulate(table_rows, headers=table_headers, tablefmt="github"))
            lines.append("")

        if self.approval_decision:
            ad = self.approval_decision
            lines.extend([
                "## 3. Governance & Manager Approval",
                f"- **Decision**: `{ad.get('decision', 'N/A')}`",
                f"- **Actor**: {ad.get('actor', 'Demo Manager')}",
                f"- **Comments**: {ad.get('comments', 'None')}",
                f"- **Timestamp**: {ad.get('timestamp', 'N/A')}",
                "",
            ])

        if self.po_reference:
            lines.extend([
                "## 4. Purchase Order",
                f"- **PO Reference**: `{self.po_reference}`",
                "",
            ])

        if self.invoice_audit:
            ia = self.invoice_audit
            lines.extend([
                "## 5. Three-Way Invoice Audit",
                f"- **Match Status**: **{ia.match_status.value}** (Discrepancy Detected: `{ia.has_discrepancy}`)",
                f"- **PO Reference**: `{ia.po_id}` (Qty: {ia.po_qty} {ia.po_unit} @ ₹{ia.po_unit_price})",
                f"- **Goods Receipt**: `{ia.goods_receipt_ref or 'N/A'}` (Received Qty: {ia.received_qty} {ia.received_unit})",
                f"- **Invoice Reference**: `{ia.invoice_ref}` (Invoiced Qty: {ia.invoiced_qty} {ia.invoiced_unit} @ ₹{ia.invoiced_unit_price})",
            ])
            if ia.discrepancies:
                lines.append("\n**Discrepancy Details:**")
                for d in ia.discrepancies:
                    lines.append(f"- **{d.discrepancy_type.value}** on `{d.field_name}`: Expected `{d.expected_value}`, got `{d.actual_value}` ({d.description})")
            lines.append("")

        if self.escalation_reason:
            lines.extend([
                "## Escalation / Failure Details",
                f"> ⚠️ {self.escalation_reason}",
                ""
            ])

        return "\n".join(lines)

    def to_table_rows(self) -> List[Tuple[str, str]]:
        """Returns key-value pairs formatted for dashboard table rows."""
        rows = [
            ("Workflow ID", self.workflow_id),
            ("Status", self.status),
            ("Component", f"{self.shortage_summary.component_name} ({self.shortage_summary.component_id})"),
            ("Required Quantity", f"{self.shortage_summary.required_qty:.0f} units"),
            ("Buffer Days", f"{self.shortage_summary.buffer_days} days"),
            ("Urgency", self.shortage_summary.urgency.value),
        ]
        if self.risk_decision:
            rows.extend([
                ("Selected Supplier", f"{self.risk_decision.selected_supplier_name} ({self.risk_decision.selected_supplier_id})"),
                ("Acquisition Cost", f"₹{self.risk_decision.selected_acquisition_cost:,.2f}"),
                ("Estimated Total Cost", f"₹{self.risk_decision.selected_estimated_total_cost:,.2f}"),
                ("Approval Required", "Yes" if self.risk_decision.approval_required else "No"),
            ])
        if self.po_reference:
            rows.append(("Purchase Order", self.po_reference))
        if self.invoice_audit:
            rows.append(("Invoice Match Status", self.invoice_audit.match_status.value))
            rows.append(("Discrepancies", str(len(self.invoice_audit.discrepancies))))
        return rows
