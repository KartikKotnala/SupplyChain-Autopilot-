"""Prompt Engineering and Persona Variants.
Implements the Multi-Prompt Matrix according to Section 8 & 12:
- Architectural Prompt Styles: STANDARD, FEW_SHOT, REACT
- Persona Profiles: COST_FOCUSED, RISK_CONSCIOUS, NEUTRAL
"""
from typing import Dict, Any


# ---------------------------------------------------------------------------
# Persona Definitions
# ---------------------------------------------------------------------------
PERSONA_PROMPTS = {
    "COST_FOCUSED": (
        "You are a Cost-Optimization Procurement Specialist. Your primary objective is to minimize "
        "total cash outflow and acquisition cost while strictly respecting component technical specifications. "
        "Penalize unnecessary shipping overheads and prioritize volume discounts."
    ),
    "RISK_CONSCIOUS": (
        "You are an Industrial Supply Risk and Continuity Manager. Your primary goal is to ensure zero factory "
        "downtime and prevent stockout delays. Even if a vendor is more expensive, you prioritize short delivery "
        "lead times and high historical reliability (>= 95%). Factory downtime costs ₹15,000/day and must be prevented."
    ),
    "NEUTRAL": (
        "You are a Balanced Procurement Policy Auditor. You evaluate supplier quotations objectively using the "
        "governed multi-criteria policy: Cost (45%), Lead Time (35%), and Reliability Risk (20%)."
    ),
}


# ---------------------------------------------------------------------------
# Architectural Prompt Styles
# ---------------------------------------------------------------------------
STANDARD_PROMPT = """
{persona}

TASK:
Evaluate the candidate supplier quotations for component '{component_id}' with required quantity {required_qty} units.
Current production buffer is {buffer_days} days. Daily downtime cost is ₹{downtime_cost:,.2f}/day.

CONSTRAINTS:
1. Filter out technically non-compliant suppliers or those with capacity < required_qty.
2. Calculate acquisition cost = (unit_price * qty) + shipping_cost.
3. Calculate estimated downtime cost = downtime_cost_per_day * max(0, lead_time_days - buffer_days).
4. Return a structured JSON response matching the RiskDecision schema.
"""

FEW_SHOT_PROMPT = """
{persona}

TASK:
Evaluate candidate supplier quotations for component '{component_id}'.
Here are two approved reference decisions from previous procurement cycles:

EXAMPLE 1:
Input: Compressor shortage (buffer: 2 days). Vendor A (₹800, 10 days, 92%), Vendor B (₹950, 2 days, 98%).
Decision: Vendor B selected. Although unit price is higher by ₹150, Vendor A would incur 8 days downtime (₹120,000 penalty). Vendor B saves ₹115,000 net.
Approval: NOT REQUIRED.

EXAMPLE 2:
Input: Condenser Coil shortage (buffer: 8 days). Vendor X (₹450, 4 days, 96%), Vendor Y (₹600, 2 days, 99%).
Decision: Vendor X selected. Both vendors deliver within the 8-day buffer (0 downtime penalty). Vendor X provides lower acquisition cost.
Approval: NOT REQUIRED.

NOW EVALUATE:
Component: {component_id}, Required Qty: {required_qty}, Buffer Days: {buffer_days}.
"""

REACT_PROMPT = """
{persona}

Solve the procurement trade-off step-by-step using the ReAct (Reason -> Action -> Observation) paradigm:

Question: Which supplier provides optimal trade-off between price, delivery delay, and reliability for {component_id}?
Thought 1: I need to check current buffer days ({buffer_days} days) against candidate lead times.
Action 1: calculate_tradeoff_score(quotes, buffer_days={buffer_days})
Observation 1: Review downtime exposure and weighted composite utility.
Thought 2: Check if any mandatory approval policy is triggered (budget limit ₹{budget_limit} or critical component delay).
Action 2: Finalize RiskDecision artifact.
"""


def render_prompt(style: str, persona: str, context: Dict[str, Any]) -> str:
    """Renders formatted prompt based on style and persona combination."""
    persona_text = PERSONA_PROMPTS.get(persona.upper(), PERSONA_PROMPTS["NEUTRAL"])
    base_template = STANDARD_PROMPT
    if style.upper() == "FEW_SHOT":
        base_template = FEW_SHOT_PROMPT
    elif style.upper() == "REACT":
        base_template = REACT_PROMPT

    return base_template.format(
        persona=persona_text,
        component_id=context.get("component_id", "COMP-001"),
        required_qty=context.get("required_qty", 45),
        buffer_days=context.get("buffer_days", 3),
        downtime_cost=context.get("downtime_cost", 15000),
        budget_limit=context.get("budget_limit", 50000),
    )
