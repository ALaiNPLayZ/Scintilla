"""
SmartOrder AI - Match current order to historical data by client, size bucket, volatility.
Returns most frequent algo and aggression from history (for scoring / tie-breaking).
"""

from typing import Dict, Any, Optional, Tuple
import pandas as pd

from .data_loader import get_historical_data

# Size bucket thresholds (as fraction of ADV): small < 5%, medium < 20%, else large
SIZE_SMALL = 0.05
SIZE_MEDIUM = 0.20


def _size_bucket(size_vs_adv: float) -> str:
    """Map size_vs_adv to small / medium / large."""
    if size_vs_adv < SIZE_SMALL:
        return "small"
    if size_vs_adv < SIZE_MEDIUM:
        return "medium"
    return "large"


def match_historical(
    client_id: str,
    symbol: str,
    size_vs_adv: float,
    volatility_bucket: str,
    data: Optional[Dict[str, pd.DataFrame]] = None,
) -> Tuple[Optional[str], Optional[str], list]:
    """
    Match on client_id, size_bucket, volatility_bucket.
    Returns (preferred_algo, preferred_aggression, list of reason strings).
    """
    hist = get_historical_data(data)
    if hist is None or hist.empty:
        return None, None, []

    bucket = _size_bucket(size_vs_adv)
    # Filter: same client, same size bucket, same volatility bucket (symbol optional for broader match)
    mask = (
        (hist["client_id"] == client_id)
        & (hist["size_bucket"] == bucket)
        & (hist["volatility_bucket"] == volatility_bucket)
    )
    subset = hist.loc[mask]

    if subset.empty:
        # Fallback: client + size_bucket only
        mask2 = (hist["client_id"] == client_id) & (hist["size_bucket"] == bucket)
        subset = hist.loc[mask2]

    if subset.empty:
        return None, None, []

    # Most frequent algo and aggression
    algo_counts = subset["algo_used"].value_counts()
    agg_counts = subset["aggression_level"].value_counts()
    preferred_algo = algo_counts.index[0] if not algo_counts.empty else None
    preferred_aggression = agg_counts.index[0] if not agg_counts.empty else None

    reasons = []
    if preferred_algo:
        reasons.append(f"Client historically prefers {preferred_algo} (size bucket={bucket}, vol={volatility_bucket})")
    if preferred_aggression:
        reasons.append(f"Historical aggression for this context: {preferred_aggression}")

    return preferred_algo, preferred_aggression, reasons
