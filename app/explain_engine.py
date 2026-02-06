"""
SmartOrder AI - Collect human-readable explanations from rules, scoring, and history.
"""

from typing import Dict, Any, List


def build_explanations(
    context: Dict[str, Any],
    rule_reasons: List[str],
    pattern_reasons: List[str],
    chosen_algo: str,
) -> List[str]:
    """
    Assemble explanation list:
    - Size vs ADV
    - Rule triggers (already in rule_reasons)
    - Scoring logic (why this algo)
    - Historical match (pattern_reasons)
    """
    explanations: List[str] = []
    size_vs_adv = context.get("size_vs_adv", 0.0)
    volatility_bucket = context.get("volatility_bucket", "Medium")
    urgency_level = context.get("urgency_level", "Medium")
    liquidity_bucket = context.get("liquidity_bucket", "Medium")

    # Always mention size vs ADV
    pct = round(size_vs_adv * 100, 0)
    explanations.append(f"Order size is {int(pct)}% of ADV")

    # Scoring-style reasons for chosen algo
    if chosen_algo == "VWAP":
        if volatility_bucket == "Low":
            explanations.append("Low volatility favors VWAP strategy")
        if size_vs_adv > 0.15:
            explanations.append("Large order size favors VWAP execution")
    elif chosen_algo == "POV":
        if urgency_level == "High":
            explanations.append("High urgency favors POV (participation) strategy")
        if urgency_level == "Medium":
            explanations.append("Medium urgency; POV selected for balanced participation")
    elif chosen_algo == "ICEBERG":
        if liquidity_bucket == "Low":
            explanations.append("Low liquidity favors ICEBERG to minimize market impact")

    # Historical / pattern reasons (avoid duplicate "historically prefers" if already in pattern_reasons)
    for r in pattern_reasons:
        if r not in explanations:
            explanations.append(r)

    # Rule reasons (e.g. "Notes specify VWAP", "Time to close < 15 min")
    for r in rule_reasons:
        if r not in explanations:
            explanations.append(r)

    return explanations
