"""
SmartOrder AI - Collect human-readable explanations from:
- Market- and note-based rules
- Historical pattern matching
- Algo scoring
- Parameter resolution

All explanations are deterministic and ordered by importance.
"""

from typing import Dict, Any, List


def _dedupe(seq: List[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for s in seq:
        if s and s not in seen:
            seen.add(s)
            out.append(s)
    return out


def build_explanations(
    context: Dict[str, Any],
    rule_reasons: List[str],
    pattern_reasons: List[str],
    score_reasons: List[str],
    param_reasons: List[str],
) -> List[str]:
    """
    Assemble final explanation list:
    1. Size vs ADV and key intents (benchmark, completion, impact sensitivity)
    2. Algo scoring reasons
    3. Order/parameter resolution reasons (limit price, TIF, clips, display qty)
    4. Historical matches
    5. Hard rule triggers
    """
    explanations: List[str] = []
    size_vs_adv = context.get("size_vs_adv", 0.0)
    notes_intents = context.get("notes_intents") or {}

    # 1) Always mention size vs ADV
    pct = round(size_vs_adv * 100, 0)
    explanations.append(f"Order size is {int(pct)}% of ADV")

    # Fat-finger quantity check (read-only warning)
    if context.get("fat_finger_flag"):
        tol = context.get("historical_tolerance_ratio")
        if tol:
            explanations.append(
                f"Quantity breaches historical size tolerance (~{tol*100:.0f}% of ADV); flagging potential fat-finger"
            )
        else:
            explanations.append("Quantity is unusually large relative to historical patterns; flagging potential fat-finger")

    # Notes-derived intents (high-level drivers)
    benchmark_type = notes_intents.get("benchmark_type")
    if benchmark_type == "VWAP":
        explanations.append("Order notes specify a VWAP benchmark")
    elif benchmark_type == "ARRIVAL":
        explanations.append("Order notes specify an arrival-price benchmark")

    if notes_intents.get("completion_required"):
        explanations.append("Order must complete by close as indicated in notes")

    if notes_intents.get("market_impact_sensitive"):
        explanations.append("Order notes request minimising market impact")

    # 2) Algo scoring reasons (already target-specific)
    for r in score_reasons:
        explanations.append(r)

    # 3) Parameter / field resolution (order type, limit, POV/VWAP/ICEBERG params)
    for r in param_reasons:
        explanations.append(r)

    # 4) Historical / pattern reasons
    for r in pattern_reasons:
        explanations.append(r)

    # 5) Rule reasons (e.g. "Notes specify VWAP", "Order size > 25% ADV...")
    for r in rule_reasons:
        explanations.append(r)

    return _dedupe(explanations)

