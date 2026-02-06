"""
SmartOrder AI - Hard rules that override other logic.
Returns partial decisions (algo, aggression, order_type) and reasons when rules fire.
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
    urgency_level = context.get("urgency_level", "Medium")
    size_vs_adv = context.get("size_vs_adv", 0.0)
    liquidity_bucket = context.get("liquidity_bucket", "Medium")

    # Rule: Notes contain VWAP -> algo = VWAP
    if notes_flags.get("vwap"):
        algo = "VWAP"
        reasons.append("Notes specify VWAP; algo set to VWAP")

    # Rule: time_to_close < 15 -> aggression HIGH
    if urgency_level == "High":
        aggression = "High"
        reasons.append("Time to close < 15 min; aggression set to High")

    # Rule: order > 25% ADV -> avoid Market order (prefer Limit)
    if size_vs_adv > 0.25:
        order_type = "Limit"
        reasons.append("Order size > 25% ADV; avoiding Market order (using Limit)")

    # Rule: urgency EOD (High) -> prefer POV (only if algo not already set by notes)
    if urgency_level == "High" and algo is None:
        algo = "POV"
        reasons.append("End-of-day urgency; prefer POV")

    result: Dict[str, Any] = {"reasons": reasons}
    if algo is not None:
        result[RULE_ALGO] = algo
    if aggression is not None:
        result[RULE_AGGRESSION] = aggression
    if order_type is not None:
        result[RULE_ORDER_TYPE] = order_type
    return result
