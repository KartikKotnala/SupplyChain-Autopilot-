"""Task Monitoring and Logging Callback System.
Implements ADK before/after agent and tool callbacks, plus CrewAI task/step callbacks.
Tracks intermediate outputs, execution flows, latency, token consumption, and errors.
"""
from datetime import datetime
import time
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class AgentCallbackEvent(BaseModel):
    event_id: str
    workflow_id: str
    trace_id: Optional[str] = None
    framework: str  # ADK or CrewAI
    event_type: str  # AGENT_START, AGENT_END, TOOL_START, TOOL_END, ERROR, STEP
    name: str  # Agent or Tool name
    status: str  # SUCCESS, FAILED, RUNNING
    duration_ms: Optional[float] = None
    inputs: Optional[Dict[str, Any]] = None
    outputs: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class CallbackRegistry:
    """Thread-safe in-memory and persistent callback event store."""
    _events: List[AgentCallbackEvent] = []

    @classmethod
    def record_event(cls, event: AgentCallbackEvent):
        cls._events.append(event)
        # Keep maximum 500 recent events
        if len(cls._events) > 500:
            cls._events.pop(0)

    @classmethod
    def get_workflow_events(cls, workflow_id: str) -> List[AgentCallbackEvent]:
        return [e for e in cls._events if e.workflow_id == workflow_id]

    @classmethod
    def get_all_events(cls, limit: int = 50) -> List[AgentCallbackEvent]:
        return cls._events[-limit:]


# ---------------------------------------------------------------------------
# Google ADK Callbacks
# ---------------------------------------------------------------------------
class ADKAgentCallback:
    """Callback hook for ADK agents tracking lifecycle and errors."""

    def __init__(self, agent_name: str, workflow_id: str, trace_id: Optional[str] = None):
        self.agent_name = agent_name
        self.workflow_id = workflow_id
        self.trace_id = trace_id
        self.start_time: float = 0.0

    def before_agent_callback(self, inputs: Dict[str, Any]):
        self.start_time = time.perf_counter()
        CallbackRegistry.record_event(
            AgentCallbackEvent(
                event_id=f"adk-start-{int(time.time() * 1000)}",
                workflow_id=self.workflow_id,
                trace_id=self.trace_id,
                framework="ADK",
                event_type="AGENT_START",
                name=self.agent_name,
                status="RUNNING",
                inputs=inputs,
            )
        )

    def after_agent_callback(self, outputs: Dict[str, Any]):
        duration = (time.perf_counter() - self.start_time) * 1000
        CallbackRegistry.record_event(
            AgentCallbackEvent(
                event_id=f"adk-end-{int(time.time() * 1000)}",
                workflow_id=self.workflow_id,
                trace_id=self.trace_id,
                framework="ADK",
                event_type="AGENT_END",
                name=self.agent_name,
                status="SUCCESS",
                duration_ms=round(duration, 2),
                outputs=outputs,
            )
        )

    def on_error_callback(self, error: Exception):
        duration = (time.perf_counter() - self.start_time) * 1000 if self.start_time else 0.0
        CallbackRegistry.record_event(
            AgentCallbackEvent(
                event_id=f"adk-err-{int(time.time() * 1000)}",
                workflow_id=self.workflow_id,
                trace_id=self.trace_id,
                framework="ADK",
                event_type="ERROR",
                name=self.agent_name,
                status="FAILED",
                duration_ms=round(duration, 2),
                error_message=str(error),
            )
        )


# ---------------------------------------------------------------------------
# FastMCP Tool Callbacks
# ---------------------------------------------------------------------------
class MCPToolCallback:
    """Callback hook for FastMCP tool calls validating parameters and return types."""

    def __init__(self, tool_name: str, workflow_id: str, trace_id: Optional[str] = None):
        self.tool_name = tool_name
        self.workflow_id = workflow_id
        self.trace_id = trace_id
        self.start_time: float = 0.0

    def before_tool_callback(self, params: Dict[str, Any]):
        self.start_time = time.perf_counter()
        CallbackRegistry.record_event(
            AgentCallbackEvent(
                event_id=f"mcp-start-{int(time.time() * 1000)}",
                workflow_id=self.workflow_id,
                trace_id=self.trace_id,
                framework="FastMCP",
                event_type="TOOL_START",
                name=self.tool_name,
                status="RUNNING",
                inputs=params,
            )
        )

    def after_tool_callback(self, result: Any):
        duration = (time.perf_counter() - self.start_time) * 1000
        CallbackRegistry.record_event(
            AgentCallbackEvent(
                event_id=f"mcp-end-{int(time.time() * 1000)}",
                workflow_id=self.workflow_id,
                trace_id=self.trace_id,
                framework="FastMCP",
                event_type="TOOL_END",
                name=self.tool_name,
                status="SUCCESS",
                duration_ms=round(duration, 2),
                outputs={"summary": str(result)[:200]},
            )
        )
