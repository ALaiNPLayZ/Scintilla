"""
SmartOrder AI - Collect human-readable explanations from:
- Market- and note-based rules
- Historical pattern matching
- Algo scoring
- Parameter resolution

All explanations are deterministic and ordered by importance.
"""

from typing import Dict, Any, List


def _consolidate_by_param(explanations: List[str]) -> List[str]:
    """
    Merge lines with same parameter prefix (e.g. "Algo:") into one short line.
    Keeps explanations trader-friendly and concise.
    """
    by_prefix: Dict[str, List[str]] = {}
    standalone: List[str] = []

    for s in explanations:
        if not s or not s.strip():
            continue
        if ": " in s:
            prefix, rest = s.split(": ", 1)
            key = prefix.strip()
            if key not in by_prefix:
                by_prefix[key] = []
            by_prefix[key].append(rest.strip())
        else:
            standalone.append(s)

    out: List[str] = []
    for s in standalone:
        out.append(s)

    # Emit one line per parameter; use final reason (last wins for overrides)
    for prefix, parts in by_prefix.items():
        final = parts[-1] if parts else ""
        out.append(f"{prefix}: {final}")

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

    # 1) Size context (trader keyword)
    pct = round(size_vs_adv * 100, 0)
    explanations.append(f"Size: {int(pct)}% ADV")

    # Fat-finger quantity check
    if context.get("fat_finger_flag"):
        explanations.append("Quantity: fat-finger check flag")

    # 2) Algo scoring
    for r in score_reasons:
        explanations.append(r)

    # 3) Parameter / field resolution
    for r in param_reasons:
        explanations.append(r)

    # 4) Historical
    for r in pattern_reasons:
        explanations.append(r)

    # 5) Rules
    for r in rule_reasons:
        explanations.append(r)

    # Consolidate by param (last reason wins); skip dedupe so rule overrides stay last
    return _consolidate_by_param(explanations)

