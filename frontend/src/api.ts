import { InventoryItem, WorkflowDetails, BenchmarkSummary } from './types';

const BASE_URL = '/api';

export async function fetchInventory(): Promise<InventoryItem[]> {
  const res = await fetch(`${BASE_URL}/inventory`);
  if (!res.ok) throw new Error('Failed to load inventory');
  return res.json();
}

export async function runAutopilotWorkflow(
  componentId: string,
  architecture: string = 'HYBRID',
  weights?: { w_cost: number; w_lead_time: number; w_reliability: number }
): Promise<any> {
  const res = await fetch(`${BASE_URL}/workflows/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      component_id: componentId,
      architecture,
      ...weights,
    }),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || 'Workflow execution failed');
  }
  return res.json();
}

export async function fetchWorkflowDetails(workflowId: string): Promise<WorkflowDetails> {
  const res = await fetch(`${BASE_URL}/workflows/${workflowId}`);
  if (!res.ok) throw new Error('Failed to fetch workflow');
  return res.json();
}

export async function fetchRecentWorkflows(): Promise<any[]> {
  const res = await fetch(`${BASE_URL}/workflows`);
  if (!res.ok) throw new Error('Failed to fetch workflows');
  return res.json();
}

export async function submitDecision(
  workflowId: string,
  decision: 'APPROVED' | 'REJECTED',
  actor: string,
  comments: string
): Promise<any> {
  const res = await fetch(`${BASE_URL}/workflows/${workflowId}/decide`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ decision, actor, comments }),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || 'Decision submission failed');
  }
  return res.json();
}

export async function calculateWhatIf(
  workflowId: string,
  weights: { w_cost: number; w_lead_time: number; w_reliability: number }
): Promise<any> {
  const res = await fetch(`${BASE_URL}/workflows/${workflowId}/what-if`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(weights),
  });
  if (!res.ok) throw new Error('What-If simulation failed');
  return res.json();
}

export async function testGuardrail(inputText: string): Promise<any> {
  const res = await fetch(`${BASE_URL}/guardrails/test`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ input_text: inputText }),
  });
  if (!res.ok) throw new Error('Guardrail test failed');
  return res.json();
}

export async function fetchBenchmarkSummary(): Promise<BenchmarkSummary> {
  const res = await fetch(`${BASE_URL}/benchmarks/summary`);
  if (!res.ok) throw new Error('Failed to fetch benchmarks');
  return res.json();
}

export async function triggerBenchmarkRun(): Promise<any> {
  const res = await fetch(`${BASE_URL}/benchmarks/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  });
  if (!res.ok) throw new Error('Benchmark run failed');
  return res.json();
}
