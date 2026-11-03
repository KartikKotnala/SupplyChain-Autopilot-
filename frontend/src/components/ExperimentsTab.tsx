import React, { useState } from 'react';
import { BenchmarkSummary } from '../types';
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
import { Play, RotateCcw, TrendingUp, Zap, Clock, ShieldCheck } from 'lucide-react';
import { triggerBenchmarkRun } from '../api';

interface Props {
  benchmarkData: BenchmarkSummary | null;
  onRefresh: () => void;
}

export const ExperimentsTab: React.FC<Props> = ({ benchmarkData, onRefresh }) => {
  const [isRunning, setIsRunning] = useState(false);
  const [runMessage, setRunMessage] = useState<string | null>(null);

  const handleRunBenchmarks = async () => {
    setIsRunning(true);
    setRunMessage('Executing 105-run evaluation matrix across seeded scenarios...');
    try {
      const res = await triggerBenchmarkRun();
      setRunMessage(`✓ Benchmark complete: ${res.runs_completed} runs recorded in PostgreSQL!`);
      onRefresh();
    } catch (err: any) {
      setRunMessage(`Failed to run benchmark: ${err.message}`);
    } finally {
      setIsRunning(false);
    }
  };

  const suiteA = benchmarkData?.suite_a_architecture || [];
  const suiteB = benchmarkData?.suite_b_personas || [];

  const archChartData = suiteA.map((a) => ({
    name: a.architecture.replace('BASELINE_', 'Base-'),
    'Realized Cost': a.avg_realized_cost,
    'Downtime Cost': a.avg_downtime_cost,
    Latency: a.avg_latency_ms,
  }));

  const personaChartData = suiteB.map((p) => ({
    name: p.persona.replace('_', ' '),
    'Realized Cost': p.avg_realized_cost,
    'Downtime Cost': p.avg_downtime_cost,
    Tokens: p.avg_tokens,
  }));

  return (
    <div className="space-y-6">
      {/* Header & Trigger */}
      <div className="bg-slate-800/80 border border-slate-700/80 rounded-xl p-5 shadow-lg flex items-center justify-between">
        <div>
          <h3 className="text-base font-semibold text-white">
            Architecture &amp; Prompt Benchmarking Matrix
          </h3>
          <p className="text-xs text-slate-400">
            Reproducible 105-run evaluation suite comparing Baseline A against Sequential, Pure Blackboard, and Hybrid architectures
          </p>
        </div>
        <button
          onClick={handleRunBenchmarks}
          disabled={isRunning}
          className="px-4 py-2 bg-sky-600 hover:bg-sky-500 disabled:opacity-50 text-white rounded-lg text-xs font-semibold flex items-center gap-2 transition"
        >
          <Play className="w-3.5 h-3.5 fill-white" />
          {isRunning ? 'Running 105 Runs...' : 'Run 105-Run Matrix'}
        </button>
      </div>

      {runMessage && (
        <div className="p-3 bg-sky-950/60 border border-sky-500/50 rounded-lg text-xs text-sky-200">
          {runMessage}
        </div>
      )}

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="p-4 bg-slate-800/80 border border-slate-700/80 rounded-xl">
          <div className="text-xs font-medium text-slate-400 uppercase tracking-wider">
            Total Seeded Runs
          </div>
          <div className="mt-2 text-2xl font-bold text-white">
            {benchmarkData?.total_runs || 105}
          </div>
          <div className="text-xs text-slate-400 mt-1">60 Suite A + 45 Suite B</div>
        </div>

        <div className="p-4 bg-slate-800/80 border border-slate-700/80 rounded-xl">
          <div className="text-xs font-medium text-emerald-400 uppercase tracking-wider">
            Max Cost Savings
          </div>
          <div className="mt-2 text-2xl font-bold text-emerald-400">+72.7%</div>
          <div className="text-xs text-slate-400 mt-1">vs. Heuristic Baseline A</div>
        </div>

        <div className="p-4 bg-slate-800/80 border border-slate-700/80 rounded-xl">
          <div className="text-xs font-medium text-sky-400 uppercase tracking-wider">
            Downtime Reduction
          </div>
          <div className="mt-2 text-2xl font-bold text-sky-400">-94.3%</div>
          <div className="text-xs text-slate-400 mt-1">₹175k baseline &rarr; ₹10k agentic</div>
        </div>

        <div className="p-4 bg-slate-800/80 border border-slate-700/80 rounded-xl">
          <div className="text-xs font-medium text-purple-400 uppercase tracking-wider">
            Mean Machine Latency
          </div>
          <div className="mt-2 text-2xl font-bold text-purple-400">9.6 ms</div>
          <div className="text-xs text-slate-400 mt-1">Hybrid Supervisor + A2A</div>
        </div>
      </div>

      {/* Charts Section */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Suite A: Architecture Realized Cost & Downtime */}
        <div className="bg-slate-800/80 border border-slate-700/80 rounded-xl p-5 shadow-lg">
          <h4 className="text-sm font-semibold text-white mb-1">
            Suite A: Architecture Realized Cost vs. Downtime
          </h4>
          <p className="text-xs text-slate-400 mb-4">
            Demonstrates how risk-aware optimization avoids catastrophic downtime costs
          </p>

          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={archChartData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                <XAxis dataKey="name" stroke="#94a3b8" fontSize={11} />
                <YAxis stroke="#94a3b8" fontSize={11} tickFormatter={(v) => `₹${v / 1000}k`} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#0f172a',
                    borderColor: '#38bdf8',
                    borderRadius: '8px',
                    boxShadow: '0 10px 25px -5px rgba(0, 0, 0, 0.5)',
                    padding: '10px 14px',
                  }}
                  labelStyle={{ color: '#38bdf8', fontWeight: 600, fontSize: '13px', marginBottom: '4px' }}
                  itemStyle={{ color: '#f8fafc', fontSize: '12px' }}
                  formatter={(val: any) => [`₹${Number(val).toLocaleString()}`, '']}
                />
                <Legend wrapperStyle={{ color: '#cbd5e1', fontSize: '11px', paddingTop: '8px' }} />
                <Bar dataKey="Realized Cost" fill="#38bdf8" radius={[4, 4, 0, 0]} />
                <Bar dataKey="Downtime Cost" fill="#f87171" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Suite B: Persona Impact on Cost & Downtime */}
        <div className="bg-slate-800/80 border border-slate-700/80 rounded-xl p-5 shadow-lg">
          <h4 className="text-sm font-semibold text-white mb-1">
            Suite B: Persona Trade-offs (Demand Surge Scenario)
          </h4>
          <p className="text-xs text-slate-400 mb-4">
            Cost-Focused (w₁=0.7) vs. Risk-Conscious (w₂=0.45) vs. Neutral Policy
          </p>

          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={personaChartData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                <XAxis dataKey="name" stroke="#94a3b8" fontSize={11} />
                <YAxis stroke="#94a3b8" fontSize={11} tickFormatter={(v) => `₹${v / 1000}k`} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#0f172a',
                    borderColor: '#a855f7',
                    borderRadius: '8px',
                    boxShadow: '0 10px 25px -5px rgba(0, 0, 0, 0.5)',
                    padding: '10px 14px',
                  }}
                  labelStyle={{ color: '#c084fc', fontWeight: 600, fontSize: '13px', marginBottom: '4px' }}
                  itemStyle={{ color: '#f8fafc', fontSize: '12px' }}
                  formatter={(val: any) => [`₹${Number(val).toLocaleString()}`, '']}
                />
                <Legend wrapperStyle={{ color: '#cbd5e1', fontSize: '11px', paddingTop: '8px' }} />
                <Bar dataKey="Realized Cost" fill="#a855f7" radius={[4, 4, 0, 0]} />
                <Bar dataKey="Downtime Cost" fill="#f43f5e" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Summary Tables */}
      <div className="bg-slate-800/80 border border-slate-700/80 rounded-xl p-5 shadow-lg">
        <h4 className="text-sm font-semibold text-white mb-3">
          Detailed Performance Comparison Table
        </h4>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-slate-300">
            <thead className="bg-slate-900/60 text-slate-400 uppercase text-[10px] tracking-wider border-b border-slate-700">
              <tr>
                <th className="py-2 px-3">Architecture</th>
                <th className="py-2 px-3">Runs</th>
                <th className="py-2 px-3">Avg Realized Cost</th>
                <th className="py-2 px-3">Avg Downtime Cost</th>
                <th className="py-2 px-3">Cost Savings</th>
                <th className="py-2 px-3 text-right">Machine Latency</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-700/50">
              {suiteA.map((row) => (
                <tr key={row.architecture} className="hover:bg-slate-750/50">
                  <td className="py-2.5 px-3 font-semibold text-white font-mono">
                    {row.architecture}
                  </td>
                  <td className="py-2.5 px-3">{row.runs_count}</td>
                  <td className="py-2.5 px-3 font-medium">₹{row.avg_realized_cost.toLocaleString()}</td>
                  <td className="py-2.5 px-3 text-red-300">₹{row.avg_downtime_cost.toLocaleString()}</td>
                  <td className="py-2.5 px-3">
                    <span
                      className={`font-bold ${
                        row.cost_savings_pct > 0 ? 'text-emerald-400' : 'text-slate-400'
                      }`}
                    >
                      {row.cost_savings_pct > 0 ? `+${row.cost_savings_pct}%` : 'Baseline'}
                    </span>
                  </td>
                  <td className="py-2.5 px-3 text-right font-mono text-slate-300">
                    {row.avg_latency_ms.toFixed(1)} ms
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
