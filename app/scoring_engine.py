"""
SmartOrder AI - Score candidate algos (VWAP, POV, ICEBERG) from context.
Returns best algo and optional tie-break from pattern/hard rules.
"""

from typing import Dict, Any, List

# Algo candidates
ALGOS = ["VWAP", "POV", "ICEBERG"]


def score_algos(
    context: Dict[str, Any],
    rule_algo: str | None = None,
    pattern_algo: str | None = None,
) -> str:
    """
    Score VWAP, POV, ICEBERG from context. Rule override wins; then pattern; then highest score.
    Examples:
    - Large order -> VWAP +2
    - High urgency -> POV +3
    - Low liquidity -> ICEBERG +2
    - Low volatility -> VWAP +2
    """
    scores: Dict[str, int] = {a: 0 for a in ALGOS}
    size_vs_adv = context.get("size_vs_adv", 0.0)
    urgency_level = context.get("urgency_level", "Medium")
    liquidity_bucket = context.get("liquidity_bucket", "Medium")
    volatility_bucket = context.get("volatility_bucket", "Medium")

    # Large order -> VWAP +2
    if size_vs_adv > 0.15:
        scores["VWAP"] += 2

    # High urgency -> POV +3
    if urgency_level == "High":
        scores["POV"] += 3

    # Low liquidity -> ICEBERG +2
    if liquidity_bucket == "Low":
        scores["ICEBERG"] += 2

    # Low volatility -> VWAP +2
    if volatility_bucket == "Low":
        scores["VWAP"] += 2

    # Medium urgency + balanced -> POV gets a nudge
    if urgency_level == "Medium":
        scores["POV"] += 1

    # Rule override: if rule engine set algo, use it
    if rule_algo and rule_algo in ALGOS:
        return rule_algo

    # Pattern tie-break: if pattern suggests one and it's tied or close, prefer it
    best_algo = max(ALGOS, key=lambda a: scores[a])
    best_score = scores[best_algo]
    if pattern_algo and pattern_algo in ALGOS and scores[pattern_algo] >= best_score - 1:
        return pattern_algo

    return best_algo
