"""Unit tests for Callbacks (Req 5) and Multi-Prompt Variants (Req 8 & 10)."""
import pytest
from services.adk_orchestrator.callbacks import (
    ADKAgentCallback,
    MCPToolCallback,
    CallbackRegistry,
)
from services.crewai_service.callbacks import CrewAICallbackHandler
from services.adk_orchestrator.prompts import render_prompt, PERSONA_PROMPTS


def test_callback_lifecycle_tracking():
    wf_id = "wf-callback-test"
    cb = ADKAgentCallback("TestAgent", wf_id, trace_id="trace-cb-01")

    # Start
    cb.before_agent_callback({"step": 1})
    events = CallbackRegistry.get_workflow_events(wf_id)
    assert len(events) == 1
    assert events[0].event_type == "AGENT_START"
    assert events[0].status == "RUNNING"

    # End
    cb.after_agent_callback({"result": "success"})
    events = CallbackRegistry.get_workflow_events(wf_id)
    assert len(events) == 2
    assert events[1].event_type == "AGENT_END"
    assert events[1].status == "SUCCESS"
    assert events[1].duration_ms is not None

    # Error
    cb.on_error_callback(ValueError("Simulated error"))
    events = CallbackRegistry.get_workflow_events(wf_id)
    assert len(events) == 3
    assert events[2].event_type == "ERROR"
    assert events[2].status == "FAILED"
    assert "Simulated error" in events[2].error_message


def test_mcp_tool_callback():
    wf_id = "wf-mcp-test"
    mcp_cb = MCPToolCallback("get_component_inventory", wf_id)
    mcp_cb.before_tool_callback({"component_id": "COMP-001"})
    mcp_cb.after_tool_callback({"found": True, "available_qty": 15.0})

    events = CallbackRegistry.get_workflow_events(wf_id)
    assert len(events) == 2
    assert events[0].framework == "FastMCP"
    assert events[1].status == "SUCCESS"


def test_prompt_rendering_variants():
    ctx = {
        "component_id": "COMP-001",
        "required_qty": 50,
        "buffer_days": 3,
        "downtime_cost": 15000,
        "budget_limit": 50000,
    }

    # Standard Style with Cost-Focused Persona
    std_cost = render_prompt("STANDARD", "COST_FOCUSED", ctx)
    assert "Cost-Optimization Procurement Specialist" in std_cost
    assert "COMP-001" in std_cost

    # Few-Shot Style with Risk-Conscious Persona
    few_risk = render_prompt("FEW_SHOT", "RISK_CONSCIOUS", ctx)
    assert "Supply Risk and Continuity Manager" in few_risk
    assert "EXAMPLE 1" in few_risk
    assert "EXAMPLE 2" in few_risk

    # ReAct Style with Neutral Persona
    react_neutral = render_prompt("REACT", "NEUTRAL", ctx)
    assert "Balanced Procurement Policy Auditor" in react_neutral
    assert "Thought 1" in react_neutral
    assert "Action 1" in react_neutral
