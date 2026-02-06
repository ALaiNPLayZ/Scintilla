"""
SmartOrder AI - Build context dict from request + loaded data.
Computes size_vs_adv, urgency from time_to_close, and notes-based flags.
"""

from typing import Dict, Any, Optional

from .models import OrderRequest
from .data_loader import get_client_profile, get_instrument_profile, get_market_snapshot, load_all_data


def _urgency_from_time_to_close(time_to_close: int) -> str:
    """
    Derive urgency level from minutes until close.
    < 15 min -> High, < 60 -> Medium, else Low.
    """
    if time_to_close < 15:
        return "High"
    if time_to_close < 60:
        return "Medium"
    return "Low"


def _parse_notes_flags(notes: Optional[str]) -> Dict[str, bool]:
    """Detect keywords in notes: vwap, urgent, close, benchmark (case-insensitive)."""
    text = (notes or "").lower()
    return {
        "vwap": "vwap" in text,
        "urgent": "urgent" in text,
        "close": "close" in text,
        "benchmark": "benchmark" in text,
    }


def build_context(request: OrderRequest, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Build full context dict for the order:
    - client_profile, instrument_profile, market_snapshot
    - size_vs_adv = order_size / adv
    - volatility_bucket, liquidity_bucket, spread
    - urgency_level (from time_to_close)
    - notes_flags (vwap, urgent, close, benchmark)
    """
    if data is None:
        data = load_all_data()

    client = get_client_profile(request.client_id, data)
    instrument = get_instrument_profile(request.symbol, data)
    market = get_market_snapshot(request.symbol, data)

    # Defaults when data is missing (mock-friendly)
    adv = float(instrument["adv"]) if instrument else 1.0
    size_vs_adv = request.order_size / adv if adv else 0.0
    volatility_bucket = (instrument or {}).get("volatility_bucket", "Medium")
    liquidity_bucket = (instrument or {}).get("liquidity_bucket", "Medium")
    spread = (market or {}).get("spread", 0.0)
    urgency_level = _urgency_from_time_to_close(request.time_to_close)
    notes_flags = _parse_notes_flags(request.notes)

    return {
        "request": request,
        "client_profile": client,
        "instrument_profile": instrument,
        "market_snapshot": market,
        "size_vs_adv": size_vs_adv,
        "volatility_bucket": volatility_bucket,
        "liquidity_bucket": liquidity_bucket,
        "spread": spread,
        "urgency_level": urgency_level,
        "notes_flags": notes_flags,
    }
