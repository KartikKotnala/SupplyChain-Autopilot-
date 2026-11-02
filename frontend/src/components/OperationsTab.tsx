import React, { useState } from 'react';
import { InventoryItem, WorkflowDetails } from '../types';
import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  DollarSign,
  Play,
  RotateCcw,
  ShieldAlert,
  ThumbsDown,
  ThumbsUp,
  Truck,
  FileCheck,
} from 'lucide-react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  ResponsiveContainer,
  CartesianGrid,
} from 'recharts';
import { runAutopilotWorkflow, submitDecision, calculateWhatIf } from '../api';

interface Props {
  inventory: InventoryItem[];
  activeWorkflow: WorkflowDetails | null;
  onRefresh: () => void;
  onSelectWorkflow: (wfId: string) => void;
}

export const OperationsTab: React.FC<Props> = ({
  inventory,
  activeWorkflow,
  onRefresh,
  onSelectWorkflow,
}) => {
  const [runningCompId, setRunningCompId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  // Weights state for What-If
  const [wCost, setWCost] = useState(0.45);
  const [wLead, setWLead] = useState(0.35);
  const [wRel, setWRel] = useState(0.20);
  const [whatIfScores, setWhatIfScores] = useState<any[] | null>(null);

  // Decision state
  const [managerComment, setManagerComment] = useState('Approved for operational continuity.');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleRunAutopilot = async (compId: string) => {
    setRunningCompId(compId);
    setActionError(null);
    try {
      const res = await runAutopilotWorkflow(compId, 'HYBRID', {
        w_cost: wCost,
        w_lead_time: wLead,
        w_reliability: wRel,
      });
      onRefresh();
      onSelectWorkflow(res.workflow_id);
    } catch (err: any) {
      setActionError(err.message);
    } finally {
      setRunningCompId(null);
    }
  };

  const handleDecision = async (decision: 'APPROVED' | 'REJECTED') => {
    if (!activeWorkflow) return;
    setIsSubmitting(true);
    setActionError(null);
    try {
      await submitDecision(
        activeWorkflow.workflow_id,
        decision,
        'Jane Doe (Procurement Director)',
        managerComment
      );
      onRefresh();
      onSelectWorkflow(activeWorkflow.workflow_id);
    } catch (err: any) {
      setActionError(err.message);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleRecalculateWhatIf = async () => {
    if (!activeWorkflow) return;
    try {
      const res = await calculateWhatIf(activeWorkflow.workflow_id, {
        w_cost: wCost,
        w_lead_time: wLead,
        w_reliability: wRel,
      });
      setWhatIfScores(res.scores);
    } catch (err: any) {
      setActionError(err.message);
    }
  };

  // Metrics
  const shortagesCount = inventory.filter((i) => i.is_shortage).length;
  const criticalCount = inventory.filter((i) => i.criticality === 'CRITICAL').length;

  // Chart data from active workflow or what-if
  const rawScores =
    whatIfScores ||
    activeWorkflow?.artifacts.find((a) => a.artifact_type === 'RiskDecision')?.payload?.scores ||
    [];

  const chartData = rawScores.map((s: any) => ({
    name: s.supplier_name.split(' ')[0],
    'Acquisition Cost': s.acquisition_cost,
    'Est. Downtime Cost': s.estimated_downtime_cost,
    'Total Cost': s.estimated_total_cost,
    leadTime: s.lead_time_days,
  }));

  return (
    <div className="space-y-6">
      {actionError && (
        <div className="p-4 bg-red-950/80 border border-red-500/50 rounded-lg flex items-center gap-3 text-red-200">
          <ShieldAlert className="w-5 h-5 text-red-400 shrink-0" />
          <span className="text-sm">{actionError}</span>
        </div>
      )}

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="p-4 bg-slate-800/80 border border-slate-700/80 rounded-xl">
          <div className="text-xs font-medium text-slate-400 uppercase tracking-wider">
            Total Components
          </div>
          <div className="mt-2 text-2xl font-bold text-white">{inventory.length}</div>
          <div className="text-xs text-slate-400 mt-1">Simulated ERP Manufacturing</div>
        </div>

        <div className="p-4 bg-slate-800/80 border border-slate-700/80 rounded-xl">
          <div className="text-xs font-medium text-amber-400 uppercase tracking-wider">
            Shortage Breaches
          </div>
          <div className="mt-2 text-2xl font-bold text-amber-400">{shortagesCount}</div>
          <div className="text-xs text-slate-400 mt-1">Below safety threshold</div>
        </div>

        <div className="p-4 bg-slate-800/80 border border-slate-700/80 rounded-xl">
          <div className="text-xs font-medium text-red-400 uppercase tracking-wider">
            Critical Components
          </div>
          <div className="mt-2 text-2xl font-bold text-red-400">{criticalCount}</div>
          <div className="text-xs text-slate-400 mt-1">Downtime risk &gt; ₹10k/day</div>
        </div>

        <div className="p-4 bg-slate-800/80 border border-slate-700/80 rounded-xl">
          <div className="text-xs font-medium text-emerald-400 uppercase tracking-wider">
            Active Workflow Status
          </div>
          <div className="mt-2 text-xl font-bold text-emerald-400">
            {activeWorkflow ? activeWorkflow.status : 'IDLE'}
          </div>
          <div className="text-xs text-slate-400 mt-1">
            {activeWorkflow ? `ID: ${activeWorkflow.workflow_id}` : 'No active execution'}
          </div>
        </div>
      </div>

      {/* Inventory Monitoring Table */}
      <div className="bg-slate-800/80 border border-slate-700/80 rounded-xl p-5 shadow-lg">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-base font-semibold text-white">
              Component Inventory &amp; Production Buffer Monitor
            </h3>
            <p className="text-xs text-slate-400">
              Live stock readings from ERP Database FastMCP tool
            </p>
          </div>
          <button
            onClick={onRefresh}
            className="px-3 py-1.5 text-xs bg-slate-700 hover:bg-slate-600 text-slate-200 rounded-lg flex items-center gap-1.5 transition"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            Refresh Stock
          </button>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-slate-300">
            <thead className="bg-slate-900/60 text-slate-400 uppercase text-[10px] tracking-wider border-b border-slate-700">
              <tr>
                <th className="py-2.5 px-3">Component</th>
                <th className="py-2.5 px-3">Available / On-Hand</th>
                <th className="py-2.5 px-3">Safety Stock</th>
                <th className="py-2.5 px-3">Burn Rate</th>
                <th className="py-2.5 px-3">Buffer Days</th>
                <th className="py-2.5 px-3">Criticality</th>
                <th className="py-2.5 px-3">Status</th>
                <th className="py-2.5 px-3 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-700/50">
              {inventory.map((item) => (
                <tr key={item.component_id} className="hover:bg-slate-750/50 transition">
                  <td className="py-3 px-3 font-medium text-white">
                    <div>{item.name}</div>
                    <div className="text-[10px] text-slate-500 font-mono">
                      {item.component_id}
                    </div>
                  </td>
                  <td className="py-3 px-3">
                    <span className="font-semibold text-white">{item.available_qty}</span>
                    <span className="text-slate-400"> / {item.on_hand_qty} {item.unit}</span>
                  </td>
                  <td className="py-3 px-3">{item.safety_stock} {item.unit}</td>
                  <td className="py-3 px-3">{item.daily_burn_rate} / day</td>
                  <td className="py-3 px-3">
                    <span
                      className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-bold ${
                        item.buffer_days <= 3
                          ? 'bg-red-950 text-red-400 border border-red-800'
                          : item.buffer_days <= 7
                          ? 'bg-amber-950 text-amber-400 border border-amber-800'
                          : 'bg-emerald-950 text-emerald-400 border border-emerald-800'
                      }`}
                    >
                      {item.buffer_days} days
                    </span>
                  </td>
                  <td className="py-3 px-3">
                    <span
                      className={`text-[10px] font-semibold px-2 py-0.5 rounded ${
                        item.criticality === 'CRITICAL'
                          ? 'bg-red-500/20 text-red-300'
                          : item.criticality === 'HIGH'
                          ? 'bg-amber-500/20 text-amber-300'
                          : 'bg-slate-700 text-slate-300'
                      }`}
                    >
                      {item.criticality}
                    </span>
                  </td>
                  <td className="py-3 px-3">
                    {item.is_shortage ? (
                      <span className="inline-flex items-center gap-1 text-red-400 font-medium">
                        <AlertTriangle className="w-3.5 h-3.5" />
                        Deficit Breach
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 text-emerald-400">
                        <CheckCircle2 className="w-3.5 h-3.5" />
                        Adequate
                      </span>
                    )}
                  </td>
                  <td className="py-3 px-3 text-right">
                    <button
                      onClick={() => handleRunAutopilot(item.component_id)}
                      disabled={runningCompId === item.component_id}
                      className="px-3 py-1.5 bg-sky-600 hover:bg-sky-500 disabled:opacity-50 text-white rounded font-medium text-xs flex items-center gap-1.5 ml-auto transition"
                    >
                      <Play className="w-3 h-3 fill-white" />
                      {runningCompId === item.component_id ? 'Running...' : 'Run Autopilot'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Active Procurement Details Section */}
      {activeWorkflow && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Column 1 & 2: Supplier Trade-Off Analysis & Chart */}
          <div className="lg:col-span-2 space-y-6">
            <div className="bg-slate-800/80 border border-slate-700/80 rounded-xl p-5 shadow-lg">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h3 className="text-base font-semibold text-white">
                    Supplier Trade-off &amp; Downtime Impact
                  </h3>
                  <p className="text-xs text-slate-400">
                    Acquisition cost vs. factory downtime penalty (₹15,000/day)
                  </p>
                </div>
                <div className="text-right">
                  <span className="text-xs text-slate-400 font-mono">
                    Workflow: {activeWorkflow.workflow_id}
                  </span>
                  <div className="text-xs font-semibold text-sky-400">
                    Selected:{' '}
                    {activeWorkflow.selected_supplier_id || 'Evaluating...'}
                  </div>
                </div>
              </div>

              {chartData.length > 0 && (
                <div className="h-64 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={chartData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                      <XAxis dataKey="name" stroke="#94a3b8" fontSize={11} />
                      <YAxis stroke="#94a3b8" fontSize={11} tickFormatter={(v) => `₹${v / 1000}k`} />
                      <Tooltip
                        contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '8px' }}
                        formatter={(val: any) => [`₹${Number(val).toLocaleString()}`, '']}
                      />
                      <Legend />
                      <Bar dataKey="Acquisition Cost" fill="#38bdf8" radius={[4, 4, 0, 0]} />
                      <Bar dataKey="Est. Downtime Cost" fill="#f87171" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              )}

              {/* What-If Trade-Off Weights */}
              <div className="mt-5 p-4 bg-slate-900/60 border border-slate-700/60 rounded-lg">
                <div className="text-xs font-semibold text-slate-300 uppercase tracking-wider mb-3">
                  Interactive Policy Weights (What-If Simulation)
                </div>
                <div className="grid grid-cols-3 gap-4">
                  <div>
                    <label className="text-xs text-slate-400 block mb-1">
                      Cost Weight (w₁): {(wCost * 100).toFixed(0)}%
                    </label>
                    <input
                      type="range"
                      min="0.1"
                      max="0.8"
                      step="0.05"
                      value={wCost}
                      onChange={(e) => {
                        const val = parseFloat(e.target.value);
                        setWCost(val);
                        setWLead(parseFloat(((1 - val) * 0.6).toFixed(2)));
                        setWRel(parseFloat(((1 - val) * 0.4).toFixed(2)));
                      }}
                      className="w-full accent-sky-500"
                    />
                  </div>
                  <div>
                    <label className="text-xs text-slate-400 block mb-1">
                      Lead Time Weight (w₂): {(wLead * 100).toFixed(0)}%
                    </label>
                    <input
                      type="range"
                      min="0.1"
                      max="0.8"
                      step="0.05"
                      value={wLead}
                      onChange={(e) => setWLead(parseFloat(e.target.value))}
                      className="w-full accent-amber-500"
                    />
                  </div>
                  <div>
                    <label className="text-xs text-slate-400 block mb-1">
                      Reliability Weight (w₃): {(wRel * 100).toFixed(0)}%
                    </label>
                    <input
                      type="range"
                      min="0.05"
                      max="0.5"
                      step="0.05"
                      value={wRel}
                      onChange={(e) => setWRel(parseFloat(e.target.value))}
                      className="w-full accent-emerald-500"
                    />
                  </div>
                </div>
                <button
                  onClick={handleRecalculateWhatIf}
                  className="mt-3 px-3 py-1 bg-slate-700 hover:bg-slate-600 text-xs text-white rounded font-medium transition"
                >
                  Recalculate Ranking
                </button>
              </div>
            </div>

            {/* PO & 3-Way Match Verification Card */}
            {activeWorkflow.order_and_invoice && (
              <div className="bg-slate-800/80 border border-slate-700/80 rounded-xl p-5 shadow-lg">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <FileCheck className="w-5 h-5 text-emerald-400" />
                    <h3 className="text-sm font-semibold text-white">
                      Purchase Order &amp; Three-Way Match Verification
                    </h3>
                  </div>
                  <span
                    className={`px-2.5 py-1 rounded text-xs font-bold ${
                      activeWorkflow.order_and_invoice.match_status === 'MATCHED'
                        ? 'bg-emerald-950 text-emerald-400 border border-emerald-800'
                        : 'bg-red-950 text-red-400 border border-red-800'
                    }`}
                  >
                    {activeWorkflow.order_and_invoice.match_status}
                  </span>
                </div>

                <div className="grid grid-cols-3 gap-3 text-xs bg-slate-900/60 p-3 rounded border border-slate-700/50">
                  <div>
                    <div className="text-slate-400 font-medium">Purchase Order (PO)</div>
                    <div className="text-white font-mono mt-0.5">
                      {activeWorkflow.order_and_invoice.po_id}
                    </div>
                    <div className="text-slate-300 mt-1">
                      Qty: {activeWorkflow.order_and_invoice.po_qty} units @ ₹
                      {activeWorkflow.order_and_invoice.po_unit_price}
                    </div>
                  </div>

                  <div>
                    <div className="text-slate-400 font-medium">Goods Receipt (GRN)</div>
                    <div className="text-white font-mono mt-0.5">
                      {activeWorkflow.order_and_invoice.goods_receipt_ref || 'Pending'}
                    </div>
                    <div className="text-slate-300 mt-1">
                      Received: {activeWorkflow.order_and_invoice.received_qty ?? 'N/A'} units
                    </div>
                  </div>

                  <div>
                    <div className="text-slate-400 font-medium">Vendor Invoice</div>
                    <div className="text-white font-mono mt-0.5">
                      {activeWorkflow.order_and_invoice.invoice_ref || 'Pending'}
                    </div>
                    <div className="text-slate-300 mt-1">
                      Billed: {activeWorkflow.order_and_invoice.invoiced_qty ?? 'N/A'} units @ ₹
                      {activeWorkflow.order_and_invoice.invoiced_unit_price ?? 'N/A'}
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Column 3: Human-in-the-Loop Approval Action Card */}
          <div className="space-y-6">
            <div className="bg-slate-800/80 border border-slate-700/80 rounded-xl p-5 shadow-lg">
              <div className="flex items-center gap-2 mb-3">
                <ShieldAlert className="w-5 h-5 text-amber-400" />
                <h3 className="text-sm font-semibold text-white">
                  Human-in-the-Loop Governance Gate
                </h3>
              </div>

              <div className="text-xs space-y-2 mb-4">
                <div className="flex justify-between py-1 border-b border-slate-700/60">
                  <span className="text-slate-400">Current State:</span>
                  <span className="font-semibold text-sky-400">{activeWorkflow.status}</span>
                </div>
                <div className="flex justify-between py-1 border-b border-slate-700/60">
                  <span className="text-slate-400">Escalation Trigger:</span>
                  <span className="font-medium text-amber-300 text-right max-w-[180px]">
                    {activeWorkflow.escalation_reason || 'Policy check pending'}
                  </span>
                </div>
                <div className="flex justify-between py-1 border-b border-slate-700/60">
                  <span className="text-slate-400">Estimated Total Cost:</span>
                  <span className="font-semibold text-white">
                    ₹{activeWorkflow.estimated_total_cost?.toLocaleString() || 'N/A'}
                  </span>
                </div>
              </div>

              {activeWorkflow.status === 'PENDING_HITL' ? (
                <div className="space-y-3 pt-2">
                  <div className="p-3 bg-amber-950/40 border border-amber-500/40 rounded text-xs text-amber-200">
                    ⚠️ Order requires authorized manager sign-off before Purchase Order creation.
                  </div>

                  <div>
                    <label className="text-xs text-slate-400 block mb-1">
                      Manager Approval Rationale:
                    </label>
                    <textarea
                      value={managerComment}
                      onChange={(e) => setManagerComment(e.target.value)}
                      rows={2}
                      className="w-full text-xs bg-slate-900 border border-slate-700 rounded p-2 text-white focus:outline-none focus:border-sky-500"
                    />
                  </div>

                  <div className="flex gap-2 pt-1">
                    <button
                      onClick={() => handleDecision('APPROVED')}
                      disabled={isSubmitting}
                      className="flex-1 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded font-medium text-xs flex items-center justify-center gap-1.5 transition"
                    >
                      <ThumbsUp className="w-4 h-4" />
                      Approve Order
                    </button>
                    <button
                      onClick={() => handleDecision('REJECTED')}
                      disabled={isSubmitting}
                      className="flex-1 py-2 bg-red-600 hover:bg-red-500 text-white rounded font-medium text-xs flex items-center justify-center gap-1.5 transition"
                    >
                      <ThumbsDown className="w-4 h-4" />
                      Reject
                    </button>
                  </div>
                </div>
              ) : (
                <div className="p-3 bg-slate-900/60 border border-slate-700/60 rounded text-xs text-slate-400">
                  {activeWorkflow.status === 'COMPLETED'
                    ? '✓ Workflow completed successfully. Purchase order issued and reconciled.'
                    : activeWorkflow.status === 'REJECTED'
                    ? '✗ Workflow rejected by manager. No purchase order was created.'
                    : 'Workflow is currently executing specialized agent tasks.'}
                </div>
              )}
            </div>

            {/* Quick Summary of Executive Report */}
            {activeWorkflow.final_report_md && (
              <div className="bg-slate-800/80 border border-slate-700/80 rounded-xl p-5 shadow-lg max-h-80 overflow-y-auto">
                <h4 className="text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">
                  Generated Executive Report
                </h4>
                <pre className="text-[11px] text-slate-400 font-mono whitespace-pre-wrap">
                  {activeWorkflow.final_report_md}
                </pre>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
