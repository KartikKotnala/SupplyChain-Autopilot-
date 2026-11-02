"""Security Guardrails and Prompt Injection Detection.
Validates API boundaries and untrusted supplier/invoice text according to Section 12.
"""
import re
from typing import Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

# Common prompt-injection patterns in untrusted vendor text or invoice notes
INJECTION_PATTERNS = [
    r"(ignore|disregard)\s+(all\s+)?(the\s+)?(previous|prior|above|system)\s+(instructions|prompt|prompts|rules)",
    r"system\s*:\s*you\s+are",
    r"you\s+are\s+now\s+(an?\s+)?unrestricted",
    r"bypass\s+(the\s+)?approval",
    r"execute\s+arbitrary",
    r"drop\s+table",
    r"select\s+\*\s+from",
    r"union\s+select",
    r"<script.*?>",
]

INJECTION_REGEX = re.compile("|".join(INJECTION_PATTERNS), re.IGNORECASE)


class GuardrailCheckResult(BaseModel):
    is_safe: bool
    blocked: bool
    threat_type: Optional[str] = None
    reason: Optional[str] = None
    sanitized_text: str


def scan_untrusted_text(text: Optional[str]) -> GuardrailCheckResult:
    """Scans untrusted supplier, invoice, or user input for prompt injection or malicious payloads."""
    if not text:
        return GuardrailCheckResult(is_safe=True, blocked=False, sanitized_text="")

    match = INJECTION_REGEX.search(text)
    if match:
        matched_str = match.group(0)
        return GuardrailCheckResult(
            is_safe=False,
            blocked=True,
            threat_type="PROMPT_INJECTION_OR_EXPLOIT",
            reason=f"Blocked potentially malicious instruction matching pattern: '{matched_str}'",
            sanitized_text="[REDACTED_BY_SECURITY_GUARDRAIL]",
        )

    # Clean and strip control characters
    sanitized = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text).strip()
    return GuardrailCheckResult(is_safe=True, blocked=False, sanitized_text=sanitized)


def validate_procurement_input_bounds(
    quantity: float,
    unit_price: Optional[float] = None,
    lead_time_days: Optional[int] = None,
) -> Tuple[bool, Optional[str]]:
    """Enforces physical and numeric boundaries on quantities, prices, and lead times."""
    if quantity <= 0.0 or quantity > 1_000_000.0:
        return False, f"Quantity ({quantity}) must be positive and within reasonable operational bounds (<= 1,000,000)."

    if unit_price is not None and (unit_price <= 0.0 or unit_price > 10_000_000.0):
        return False, f"Unit price (₹{unit_price:,.2f}) must be positive and <= ₹10,000,000."

    if lead_time_days is not None and (lead_time_days < 1 or lead_time_days > 365):
        return False, f"Lead time ({lead_time_days} days) must be between 1 and 365 days."

    return True, None
