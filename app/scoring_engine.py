"""
SmartOrder AI - Score candidate algos (VWAP, POV, ICEBERG) from context.

Scoring uses:
- Size vs ADV
- Time to market close / urgency
- Volatility + liquidity
- Order-note intents (benchmark, impact sensitivity, completion risk)

Returns both the chosen algo and human-readable scoring reasons
for explainability.
"""

from typing import Dict, Any, List, Tuple

from .ebm_stub import ebm_adjust_algo_scores

# Algo candidates
ALGOS = ["VWAP", "POV", "ICEBERG"]


def _dedupe(seq: List[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for s in seq:
        if s and s not in seen:
            seen.add(s)
            out.append(s)
    return out


def score_algos(
    context: Dict[str, Any],
    rule_algo: str | None = None,
    pattern_algo: str | None = None,
) -> Tuple[str, List[str]]:
    """
    Score VWAP, POV, ICEBERG from context.

    Rule override wins; then pattern tie-break; then highest score.
    Also returns explanation strings describing *why* the chosen algo
    scored well (deterministic, no ML/LLM calls).
    """
    scores: Dict[str, float] = {a: 0.0 for a in ALGOS}
    reasons_by_algo: Dict[str, List[str]] = {a: [] for a in ALGOS}

    size_vs_adv = float(context.get("size_vs_adv", 0.0))
    urgency_level = context.get("urgency_level", "Medium")
    eff_ttc = int(context.get("effective_time_to_close", 60))
    liquidity_bucket = context.get("liquidity_bucket", "Medium")
    liquidity_score = float(context.get("liquidity_score", 1.0))
    volatility_bucket = context.get("volatility_bucket", "Medium")
    notes_intents = context.get("notes_intents") or {}

    benchmark_type = notes_intents.get("benchmark_type")
    completion_required = bool(notes_intents.get("completion_required"))
    market_impact_sensitive = bool(notes_intents.get("market_impact_sensitive"))
    aggression_pref = notes_intents.get("aggression_preference")

    def bump(algo: str, delta: float, reason: str) -> None:
        scores[algo] += delta
        reasons_by_algo[algo].append(reason)

    # --- Size vs ADV ---
    if size_vs_adv > 0.25:
        bump("VWAP", 3, "Algo: VWAP (large vs ADV)")
        bump("POV", 1, "Algo: POV (large size, participation control)")
    elif size_vs_adv > 0.10:
        bump("VWAP", 2, "Algo: VWAP (size vs ADV)")
    else:
        bump("POV", 1, "Algo: POV (small size)")

    # --- Urgency / time-to-close ---
    if urgency_level == "High" or eff_ttc <= 20:
        bump("POV", 4, "Algo: POV (urgency / near close)")
    elif urgency_level == "Medium":
        bump("POV", 1.5, "Algo: POV (urgency)")
    else:
        bump("VWAP", 1, "Algo: VWAP (low urgency)")

    if completion_required:
        bump("POV", 3, "Algo: POV (completion by close)")

    # --- Volatility ---
    if volatility_bucket == "Low":
        bump("VWAP", 2, "Algo: VWAP (low vol)")
    elif volatility_bucket == "High":
        bump("POV", 1.5, "Algo: POV (high vol)")
        bump("ICEBERG", 1.5, "Algo: ICEBERG (high vol, hide size)")

    # --- Liquidity ---
    if liquidity_bucket == "Low" or liquidity_score < 0.8:
        bump("ICEBERG", 3, "Algo: ICEBERG (low liquidity)")
    elif liquidity_bucket == "High" and liquidity_score > 1.2:
        bump("POV", 1, "Algo: POV (high liquidity)")

    # --- Notes-based intents ---
    if benchmark_type == "VWAP":
        bump("VWAP", 5, "Algo: VWAP (notes benchmark)")
    elif benchmark_type == "ARRIVAL":
        bump("POV", 2, "Algo: POV (arrival benchmark)")

    if market_impact_sensitive:
        bump("ICEBERG", 3, "Algo: ICEBERG (min impact)")
        bump("VWAP", 1, "Algo: VWAP (passive)")

    if aggression_pref == "HIGH":
        bump("POV", 2, "Algo: POV (aggressive)")
    elif aggression_pref == "LOW":
        bump("VWAP", 1.5, "Algo: VWAP (passive)")
        bump("ICEBERG", 1.0, "Algo: ICEBERG (passive)")

    # --- Rule override: if rule engine forced an algo, it wins ---
    if rule_algo and rule_algo in ALGOS:
        chosen = rule_algo
        score_reasons = [f"Algo: {rule_algo} (rule override)"] + reasons_by_algo.get(chosen, [])
        return chosen, _dedupe(score_reasons)

    # --- Optional EBM stub for ML-based adjustment (currently no-op) ---
    scores, ebm_reasons = ebm_adjust_algo_scores(context, scores)

    # --- Pattern tie-break + best score ---
    best_algo = max(ALGOS, key=lambda a: scores[a])
    best_score = scores[best_algo]

    chosen = best_algo
    score_reasons = reasons_by_algo.get(chosen, [])

    if pattern_algo and pattern_algo in ALGOS and scores[pattern_algo] >= best_score - 1:
        chosen = pattern_algo
        score_reasons = reasons_by_algo.get(chosen, []) + [
            f"Algo: {chosen} (historical preference)"
        ]

    score_reasons = _dedupe(score_reasons + ebm_reasons)
    return chosen, score_reasons

