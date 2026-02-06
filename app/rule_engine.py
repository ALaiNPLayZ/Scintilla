"""
SmartOrder AI - Hard rules that override other logic.

These rules:
- Interpret critical signals from notes and context
- May force algo, aggression, or order_type
- Always emit deterministic explanation strings
"""

from typing import Dict, Any, List, Optional

# Rule output: optional overrides + list of reason strings
RULE_ALGO = "algo"
RULE_AGGRESSION = "aggression"
RULE_ORDER_TYPE = "order_type"
RULE_REASONS = "reasons"


def apply_rules(context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Apply hard rules. Returns dict with optional keys:
    - algo: str (VWAP, POV, ICEBERG) if forced
    - aggression: str (Low, Medium, High) if forced
    - order_type: str (Market, Limit) if forced
    - reasons: list of explanation strings
    """
    reasons: List[str] = []
    algo: Optional[str] = None
    aggression: Optional[str] = None
    order_type: Optional[str] = None

    notes_flags = context.get("notes_flags") or {}
    notes_intents = context.get("notes_intents") or {}
    urgency_level = context.get("urgency_level", "Medium")
    size_vs_adv = context.get("size_vs_adv", 0.0)
    liquidity_bucket = context.get("liquidity_bucket", "Medium")

    # Rule: explicit VWAP benchmark in notes or flags -> force VWAP
    if notes_flags.get("vwap") or notes_intents.get("benchmark_type") == "VWAP":
        algo = "VWAP"
        reasons.append("Notes specify VWAP benchmark; algo forced to VWAP")

    # Rule: completion required by close -> prefer POV and higher aggression
    if notes_intents.get("completion_required"):
        if algo is None:
            algo = "POV"
            reasons.append("Order must complete by close; algo forced to POV")
        aggression = "High"
        reasons.append("Completion requirement: aggression forced to High")

    # Rule: time_to_close high-urgency -> aggression HIGH
    if urgency_level == "High" and aggression is None:
        aggression = "High"
        reasons.append("High urgency from time-to-close; aggression set to High")

    # Rule: order > 25% ADV -> avoid Market order (prefer Limit)
    if size_vs_adv > 0.25:
        order_type = "Limit"
        reasons.append("Order size > 25% ADV; avoiding Market order (using Limit)")

    # Rule: very low liquidity and impact-sensitive notes -> avoid Market
    if notes_intents.get("market_impact_sensitive") and liquidity_bucket == "Low":
        if order_type != "Limit":
            order_type = "Limit"
        reasons.append("Impact-sensitive in low liquidity; Market orders disallowed (Limit only)")

    # Rule: urgency EOD (High) -> prefer POV (only if algo not already set)
    if urgency_level == "High" and algo is None:
        algo = "POV"
        reasons.append("End-of-day urgency; defaulting to POV")

    result: Dict[str, Any] = {"reasons": reasons}
    if algo is not None:
        result[RULE_ALGO] = algo
    if aggression is not None:
        result[RULE_AGGRESSION] = aggression
    if order_type is not None:
        result[RULE_ORDER_TYPE] = order_type
    return result

