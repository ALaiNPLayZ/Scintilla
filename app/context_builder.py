"""
SmartOrder AI - Build a rich context dict from request + loaded data.

Context combines:
- Client / instrument profiles
- Synthetic market data (bid/ask/ltp, volatility, liquidity proxies)
- Size vs ADV and historical size tolerance
- Time-to-close (from request and system clock)
- Parsed order note intents (urgency, benchmark, impact sensitivity, etc.)

This module is intentionally deterministic: no LLMs or external calls.
"""

from datetime import datetime, time as time_type
from typing import Dict, Any, Optional

from .models import OrderRequest
from .data_loader import (
    get_client_profile,
    get_instrument_profile,
    get_market_snapshot,
    load_all_data,
    get_historical_data,
)


def _urgency_from_time_to_close(minutes_to_close: int) -> str:
    """
    Derive urgency level from minutes until close.
    < 15 min -> High, < 60 -> Medium, else Low.
    """
    if minutes_to_close < 15:
        return "High"
    if minutes_to_close < 60:
        return "Medium"
    return "Low"


def _system_minutes_to_close(close_hour: int = 16, close_minute: int = 0) -> int:
    """
    Synthetic "time to market close" derived from the local system clock.
    Assumes a 16:00 close in the local timezone.
    """
    now = datetime.now()
    close_dt = datetime.combine(now.date(), time_type(close_hour, close_minute))
    delta = (close_dt - now).total_seconds() / 60.0
    return max(0, int(delta))


def _parse_notes_flags(notes: Optional[str]) -> Dict[str, bool]:
    """Simple keyword flags in notes: vwap, urgent, close, benchmark (case-insensitive)."""
    text = (notes or "").lower()
    return {
        "vwap": "vwap" in text,
        "urgent": "urgent" in text,
        "close": "close" in text,
        "benchmark": "benchmark" in text,
    }


def _parse_notes_intents(notes: Optional[str]) -> Dict[str, Any]:
    """
    Deterministic intent extraction from order notes using keyword/phrase matching.

    Extracts:
    - urgency_intent: LOW / MEDIUM / HIGH / None
    - benchmark_type: VWAP / ARRIVAL / None
    - aggression_preference: LOW / MEDIUM / HIGH / None
    - completion_required: bool
    - market_impact_sensitive: bool
    """
    text = (notes or "").lower()

    urgency_intent: Optional[str] = None
    benchmark_type: Optional[str] = None
    aggression_preference: Optional[str] = None
    completion_required = False
    market_impact_sensitive = False

    # Benchmarks
    if "vwap benchmark" in text or "benchmark: vwap" in text or "vwap " in text:
        benchmark_type = "VWAP"
    if "benchmark: arrival price" in text or "arrival price" in text:
        benchmark_type = "ARRIVAL"

    # Urgency / completion
    if "eod compliance required" in text or "must complete by close" in text:
        urgency_intent = "HIGH"
        completion_required = True
    elif "must complete" in text:
        urgency_intent = "HIGH"
        completion_required = True
    elif "urgent" in text:
        urgency_intent = "HIGH"
    elif "steady execution" in text:
        # steady but not slow
        urgency_intent = urgency_intent or "MEDIUM"

    # Impact sensitivity
    if "minimize market impact" in text or "minimise market impact" in text:
        market_impact_sensitive = True
        aggression_preference = "LOW"

    # Aggression hints
    if "steady execution" in text:
        aggression_preference = aggression_preference or "MEDIUM"

    return {
        "urgency_intent": urgency_intent,
        "benchmark_type": benchmark_type,
        "aggression_preference": aggression_preference,
        "completion_required": completion_required,
        "market_impact_sensitive": market_impact_sensitive,
    }


def _volatility_bucket_from_intraday(vol: float) -> str:
    """Derive a simple volatility bucket from numeric intraday volatility."""
    if vol <= 0.01:
        return "Low"
    if vol <= 0.02:
        return "Medium"
    return "High"


def _liquidity_score(adv: float, spread: float, avg_trade_size: float) -> float:
    """
    Simple liquidity proxy: larger ADV & trade size + tighter spreads => higher score.
    This is intentionally heuristic for the hackathon.
    """
    adv_norm = adv / 1e6  # millions of shares
    spread_penalty = max(spread, 0.01)
    trade_norm = avg_trade_size / 1000.0
    return (adv_norm * 0.6 + trade_norm * 0.4) / spread_penalty


def _historical_size_tolerance(
    client_id: str,
    symbol: str,
    size_vs_adv: float,
    data: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Use synthetic historical order patterns to derive a "fat-finger" size tolerance.
    We map size_bucket -> numeric ratio to ADV and compare current size_vs_adv.
    """
    hist = get_historical_data(data)
    result = {
        "fat_finger_flag": False,
        "historical_tolerance_ratio": None,
    }
    if hist is None or hist.empty:
        return result

    bucket_ratio = {"small": 0.02, "medium": 0.10, "large": 0.30}

    subset = hist[(hist["client_id"] == client_id) & (hist["symbol"] == symbol)]
    if subset.empty:
        subset = hist[hist["client_id"] == client_id]
    if subset.empty:
        return result

    ratios = subset["size_bucket"].map(bucket_ratio)
    ratios = ratios.dropna()
    if ratios.empty:
        return result

    typical = float(ratios.median())
    tolerance = typical * 3.0  # 3x typical size bucket as "fat-finger" threshold
    result["historical_tolerance_ratio"] = tolerance
    if size_vs_adv > tolerance:
        result["fat_finger_flag"] = True
    return result


def build_context(request: OrderRequest, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Build full context dict for the order:
    - client_profile, instrument_profile, market_snapshot
    - synthetic market fields: volatility (numeric + bucket), avg trade size, liquidity proxy
    - size_vs_adv = order_size / adv
    - urgency_level (combined from request + system clock + notes intents)
    - parsed order note intents + simple flags
    - historical size tolerance (fat-finger detection)
    """
    if data is None:
        data = load_all_data()

    client = get_client_profile(request.client_id, data)
    instrument = get_instrument_profile(request.symbol, data)
    market = get_market_snapshot(request.symbol, data)

    # Defaults when data is missing (mock-friendly)
    adv = float(instrument["adv"]) if instrument else 1.0
    size_vs_adv = request.order_size / adv if adv else 0.0

    volatility_bucket_instr = (instrument or {}).get("volatility_bucket", "Medium")
    liquidity_bucket = (instrument or {}).get("liquidity_bucket", "Medium")

    spread = (market or {}).get("spread", 0.0)
    intraday_vol = (market or {}).get("intraday_vol", 0.015)
    avg_trade_size = float((market or {}).get("last_trade_size", 500))
    bid = (market or {}).get("bid", None)
    ask = (market or {}).get("ask", None)
    ltp = (market or {}).get("ltp", None)

    # Market-derived volatility bucket and liquidity score
    market_vol_bucket = _volatility_bucket_from_intraday(float(intraday_vol))
    liquidity_score = _liquidity_score(adv, float(spread), avg_trade_size)

    # Time to close: request-provided + system-derived.
    #
    # Important hackathon detail:
    # - When testing after-hours, system-derived time-to-close will be 0.
    # - In that case we should fall back to the request-provided value,
    #   otherwise start/end times collapse to the same minute.
    time_to_close_req = int(request.time_to_close)
    time_to_close_sys = _system_minutes_to_close()
    if time_to_close_sys <= 0 and time_to_close_req > 0:
        effective_time_to_close = time_to_close_req
    elif time_to_close_req <= 0 and time_to_close_sys > 0:
        effective_time_to_close = time_to_close_sys
    elif time_to_close_req > 0 and time_to_close_sys > 0:
        effective_time_to_close = min(time_to_close_req, time_to_close_sys)
    else:
        effective_time_to_close = 0

    # Notes: simple flags + richer intents
    notes_flags = _parse_notes_flags(request.notes)
    notes_intents = _parse_notes_intents(request.notes)

    # Base urgency from time-to-close, then overridden by notes intent if present
    urgency_level = _urgency_from_time_to_close(effective_time_to_close)
    if notes_intents.get("urgency_intent") == "HIGH":
        urgency_level = "High"
    elif notes_intents.get("urgency_intent") == "MEDIUM" and urgency_level == "Low":
        urgency_level = "Medium"
    elif notes_intents.get("urgency_intent") == "LOW":
        # Do not downgrade; treat as soft preference
        pass

    # Historical size tolerance for fat-finger checks
    size_tolerance_info = _historical_size_tolerance(
        request.client_id,
        request.symbol,
        size_vs_adv,
        data,
    )

    return {
        "request": request,
        "client_profile": client,
        "instrument_profile": instrument,
        "market_snapshot": market,
        "size_vs_adv": size_vs_adv,
        "adv": adv,
        "volatility_bucket_instrument": volatility_bucket_instr,
        "volatility_bucket": market_vol_bucket,
        "intraday_vol": intraday_vol,
        "liquidity_bucket": liquidity_bucket,
        "liquidity_score": liquidity_score,
        "spread": spread,
        "bid": bid,
        "ask": ask,
        "ltp": ltp,
        "time_to_close_request": time_to_close_req,
        "time_to_close_system": time_to_close_sys,
        "effective_time_to_close": effective_time_to_close,
        "urgency_level": urgency_level,
        "notes_flags": notes_flags,
        "notes_intents": notes_intents,
        "fat_finger_flag": size_tolerance_info["fat_finger_flag"],
        "historical_tolerance_ratio": size_tolerance_info["historical_tolerance_ratio"],
    }

