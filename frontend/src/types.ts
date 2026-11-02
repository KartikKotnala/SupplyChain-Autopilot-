export interface InventoryItem {
  component_id: string;
  name: string;
  unit: string;
  on_hand_qty: number;
  reserved_qty: number;
  available_qty: number;
  safety_stock: number;
  target_stock: number;
  daily_burn_rate: number;
  buffer_days: number;
  downtime_cost_per_day: number;
  budget_limit: number;
  criticality: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
  is_shortage: boolean;
}

export interface SupplierScore {
  supplier_id: string;
  supplier_name: string;
  unit_price: number;
  shipping_cost: number;
  lead_time_days: number;
  reliability_score: number;
  acquisition_cost: number;
  estimated_downtime_cost: number;
  estimated_total_cost: number;
  weighted_score: number;
  rank: number;
  is_feasible: boolean;
  disqualification_reason?: string;
}

export interface RiskDecisionData {
  workflow_id: string;
  component_id: string;
  selected_supplier_id: string;
  selected_supplier_name: string;
  selected_acquisition_cost: number;
  selected_estimated_downtime_cost: number;
  selected_estimated_total_cost: number;
  approval_required: boolean;
  escalation_reasons: string[];
  rationale: string;
  scores: SupplierScore[];
}

export interface BlackboardArtifact {
  entry_id: string;
  artifact_type: string;
  step_name: string;
  producer_agent: string;
  framework: string;
  payload: any;
  version: number;
  trace_id?: string;
  created_at: string;
}

export interface WorkflowDetails {
  workflow_id: string;
  component_id: string;
  required_qty: number;
  buffer_days: number;
  status: string;
  selected_supplier_id?: string;
  estimated_total_cost?: number;
  approval_required: boolean;
  approval_status?: string;
  approval_actor?: string;
  approval_timestamp?: string;
  escalation_reason?: string;
  final_report_md?: string;
  artifacts: BlackboardArtifact[];
  order_and_invoice?: {
    po_id: string;
    supplier_id: string;
    po_qty: number;
    po_unit_price: number;
    goods_receipt_ref?: string;
    received_qty?: number;
    invoice_ref?: string;
    invoiced_qty?: number;
    invoiced_unit_price?: number;
    match_status: string;
    discrepancies?: any[];
  };
}

export interface BenchmarkSummary {
  total_runs: number;
  suite_a_architecture: {
    architecture: string;
    runs_count: number;
    avg_realized_cost: number;
    avg_downtime_cost: number;
    cost_savings_pct: number;
    avg_latency_ms: number;
  }[];
  suite_b_personas: {
    persona: string;
    runs_count: number;
    avg_realized_cost: number;
    avg_downtime_cost: number;
    avg_tokens: number;
  }[];
}
