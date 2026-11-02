"""CrewAI Task and Step Callback Hooks.
Tracks CrewAI agent execution, steps, and tool invocations.
"""
import time
from typing import Any, Dict, Optional
from services.adk_orchestrator.callbacks import AgentCallbackEvent, CallbackRegistry


class CrewAICallbackHandler:
    def __init__(self, task_name: str, workflow_id: str, trace_id: Optional[str] = None):
        self.task_name = task_name
        self.workflow_id = workflow_id
        self.trace_id = trace_id
        self.start_time: float = 0.0

    def task_callback(self, task_output: Any):
        """Called when a CrewAI task completes."""
        duration = (time.perf_counter() - self.start_time) * 1000 if self.start_time else 0.0
        CallbackRegistry.record_event(
            AgentCallbackEvent(
                event_id=f"crew-task-{int(time.time() * 1000)}",
                workflow_id=self.workflow_id,
                trace_id=self.trace_id,
                framework="CrewAI",
                event_type="AGENT_END",
                name=self.task_name,
                status="SUCCESS",
                duration_ms=round(duration, 2),
                outputs={"output_preview": str(task_output)[:200]},
            )
        )

    def step_callback(self, step_details: Dict[str, Any]):
        """Called during each intermediate agent reasoning step."""
        CallbackRegistry.record_event(
            AgentCallbackEvent(
                event_id=f"crew-step-{int(time.time() * 1000)}",
                workflow_id=self.workflow_id,
                trace_id=self.trace_id,
                framework="CrewAI",
                event_type="STEP",
                name=self.task_name,
                status="RUNNING",
                inputs=step_details,
            )
        )
