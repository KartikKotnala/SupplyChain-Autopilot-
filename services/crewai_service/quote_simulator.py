"""Deterministic vendor quotation simulator for CrewAI Sourcing Agent.
Generates reproducible supplier quotes using catalog baselines and controlled variation.
"""
import random
from typing import Any, Dict, List, Optional
from contracts.rfq_quotes import SupplierQuote


def simulate_vendor_quotes(
    qualified_suppliers: List[Dict[str, Any]],
    required_qty: float,
    seed: Optional[int] = None,
    allow_variation: bool = False,
) -> List[SupplierQuote]:
    """Generates structured quotes for qualified suppliers.
    
    If allow_variation is False or seed is provided, outputs are completely deterministic.
    """
    rng = random.Random(seed) if seed is not None else random.Random(42)
    quotes = []

    for s in qualified_suppliers:
        base_price = float(s["unit_price"])
        base_shipping = float(s["shipping_cost"])
        base_lead = int(s["lead_time_days"])
        reliability = float(s["reliability_score"])
        capacity = float(s["capacity"])
        moq = float(s["moq"])

        # Controlled variation for benchmark experiments if enabled
        if allow_variation:
            price_factor = rng.uniform(0.98, 1.05)
            lead_time_delta = rng.choice([-1, 0, 0, 1])
        else:
            price_factor = 1.0
            lead_time_delta = 0

        final_price = round(base_price * price_factor, 2)
        final_lead = max(1, base_lead + lead_time_delta)

        quote = SupplierQuote(
            quote_id=f"QUOTE-{s['supplier_id']}-{int(rng.random() * 10000):04d}",
            supplier_id=s["supplier_id"],
            supplier_name=s["supplier_name"],
            unit_price=final_price,
            quoted_quantity=required_qty,
            lead_time_days=final_lead,
            shipping_cost=base_shipping,
            capacity=capacity,
            moq=moq,
            reliability_score=reliability,
            technical_compliance=s.get("technical_compliant", True),
            quote_valid=True,
        )
        quotes.append(quote)

    return quotes
