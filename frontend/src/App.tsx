import React, { useState, useEffect } from 'react';
import { InventoryItem, WorkflowDetails, BenchmarkSummary } from './types';
import { fetchInventory, fetchWorkflowDetails, fetchBenchmarkSummary, fetchRecentWorkflows } from './api';
import { OperationsTab } from './components/OperationsTab';
import { ObservatoryTab } from './components/ObservatoryTab';
import { ExperimentsTab } from './components/ExperimentsTab';
import { Layers, Activity, Cpu, PlayCircle, BarChart3, ShieldCheck } from 'lucide-react';

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'operations' | 'observatory' | 'experiments'>('operations');
  const [inventory, setInventory] = useState<InventoryItem[]>([]);
  const [activeWorkflow, setActiveWorkflow] = useState<WorkflowDetails | null>(null);
  const [benchmarkData, setBenchmarkData] = useState<BenchmarkSummary | null>(null);
  const [recentWorkflows, setRecentWorkflows] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  const loadData = async () => {
    try {
      const [inv, wfs, bench] = await Promise.all([
        fetchInventory(),
        fetchRecentWorkflows(),
        fetchBenchmarkSummary(),
      ]);
      setInventory(inv);
      setRecentWorkflows(wfs);
      setBenchmarkData(bench);

      // Auto-select latest workflow if none selected or if active
      if (wfs.length > 0 && !activeWorkflow) {
        const latest = await fetchWorkflowDetails(wfs[0].workflow_id);
        setActiveWorkflow(latest);
      }
    } catch (err) {
      console.error('Error fetching dashboard data:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleSelectWorkflow = async (wfId: string) => {
    try {
      const details = await fetchWorkflowDetails(wfId);
      setActiveWorkflow(details);
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 10000); // Polling every 10s
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
      {/* Top Navigation Bar */}
      <header className="bg-slate-900 border-b border-slate-800 px-6 py-4 sticky top-0 z-50 shadow-md">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-sky-500/20 border border-sky-400/40 flex items-center justify-center text-sky-400">
              <Cpu className="w-5 h-5" />
            </div>
            <div>
              <div className="text-base font-bold text-white flex items-center gap-2">
                SupplyChain Autopilot
                <span className="text-[10px] font-mono font-semibold px-2 py-0.5 bg-sky-950 border border-sky-500/40 text-sky-400 rounded">
                  v1.0 Baseline
                </span>
              </div>
              <div className="text-xs text-slate-400">
                Google ADK + CrewAI &bull; A2A Protocol &bull; FastMCP Tools &bull; PostgreSQL Blackboard
              </div>
            </div>
          </div>

          {/* Tab Selector */}
          <div className="flex bg-slate-950 p-1 rounded-xl border border-slate-800">
            <button
              onClick={() => setActiveTab('operations')}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold transition ${
                activeTab === 'operations'
                  ? 'bg-sky-600 text-white shadow'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Activity className="w-3.5 h-3.5" />
              1. Operations &amp; Approval
            </button>
            <button
              onClick={() => setActiveTab('observatory')}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold transition ${
                activeTab === 'observatory'
                  ? 'bg-sky-600 text-white shadow'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Layers className="w-3.5 h-3.5" />
              2. Agent Observatory &amp; Blackboard
            </button>
            <button
              onClick={() => setActiveTab('experiments')}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold transition ${
                activeTab === 'experiments'
                  ? 'bg-sky-600 text-white shadow'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <BarChart3 className="w-3.5 h-3.5" />
              3. Architecture &amp; Experiments
            </button>
          </div>
        </div>
      </header>

      {/* Main Content Body */}
      <main className="max-w-7xl mx-auto w-full px-6 py-6 flex-1">
        {loading ? (
          <div className="flex items-center justify-center h-64 text-sm text-slate-400">
            Connecting to backend and FastMCP servers...
          </div>
        ) : (
          <>
            {activeTab === 'operations' && (
              <OperationsTab
                inventory={inventory}
                activeWorkflow={activeWorkflow}
                onRefresh={loadData}
                onSelectWorkflow={handleSelectWorkflow}
              />
            )}
            {activeTab === 'observatory' && (
              <ObservatoryTab activeWorkflow={activeWorkflow} />
            )}
            {activeTab === 'experiments' && (
              <ExperimentsTab benchmarkData={benchmarkData} onRefresh={loadData} />
            )}
          </>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-900 bg-slate-950 px-6 py-3 text-center text-xs text-slate-500">
        SupplyChain Autopilot &bull; Multi-Agent Procurement &bull; Google ADK &amp; CrewAI Interoperability
      </footer>
    </div>
  );
};
