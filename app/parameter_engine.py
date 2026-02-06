"""
SmartOrder AI - Generate core order fields and algo-specific parameters
from chosen algo, context, rule overrides, and market data.

This module focuses on:
- Deterministic, market-aware order type and limit price logic
- Time window and TIF selection
- Impact-sensitive display quantity
- Rule-based POV/VWAP/ICEBERG parameter resolution

Each decision also emits human-readable explanation strings.
"""

from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime

from .models import CoreOrderFields, AlgoParameters


def _now_time_str() -> str:
    """Current time as HH:MM (e.g. 09:45)."""
    return datetime.now().strftime("%H:%M")


def _synthetic_market_now() -> datetime:
    """
    Return a "market-session" timestamp for realistic ticket times.

    Hackathon-friendly behavior:
    - If your system clock is outside typical market hours, we clamp to a
      reasonable intraday time (10:00).
    - This avoids start/end being identical (or looking like 19:30) during demos.
    """
    now = datetime.now().replace(second=0, microsecond=0)
    open_t = now.replace(hour=9, minute=30)
    close_t = now.replace(hour=15, minute=55)
    if now < open_t or now > close_t:
        return now.replace(hour=10, minute=0)
    return now


def _end_time_from_urgency(effective_minutes_to_close: int, urgency: str) -> str:
    """
    End time: approximate the execution window.

    For simplicity we keep everything inside the trading day, but
    compress or extend based on urgency and time to close.
    """
    # Assume a 16:00 close; don't exceed that.
    now = datetime.now()
    if urgency == "High":
        # Finish close to the bell
        target_minutes = min(effective_minutes_to_close, 30)
    elif urgency == "Medium":
        target_minutes = min(effective_minutes_to_close, 90)
    else:
        target_minutes = min(effective_minutes_to_close, 240)

    end_dt = now.replace(second=0, microsecond=0) + timedelta(minutes=target_minutes)
    return end_dt.strftime("%H:%M")


def _tif_from_window(effective_minutes_to_close: int) -> str:
    """
    Time-in-force derived from how much time is realistically available.
    """
    if effective_minutes_to_close <= 5:
        return "IOC"
    # For intraday algo-style orders, DAY is a reasonable default.
    return "DAY"


def _protection_banded_limit_price(
    direction: str,
    bid: Optional[float],
    ask: Optional[float],
    ltp: Optional[float],
    spread: float,
) -> Optional[float]:
    """
    Compute a passive limit price using bid/ask references and simple
    buy/sell protection bands.

    - For BUY: aim inside the spread but never far through the ask.
    - For SELL: aim inside the spread but never far through the bid.
    """
    if not ltp and bid is None and ask is None:
        return None

    if bid is None and ask is not None:
        bid = ask - spread
    if ask is None and bid is not None:
        ask = bid + spread

    bid = float(bid or ltp or 0.0)
    ask = float(ask or ltp or 0.0)
    spread = float(spread or max(ask - bid, 0.01))

    mid = (bid + ask) / 2.0

    if direction.lower() == "buy":
        # Slightly passive inside the spread for buys.
        limit = bid + 0.25 * spread
        # Do not cross more than one spread through the ask.
        upper_band = ask + spread
        return round(min(limit, upper_band), 2)
    else:
        # For sells, lean inside the spread toward the bid.
        limit = ask - 0.25 * spread
        lower_band = bid - spread
        return round(max(limit, lower_band), 2)


def build_core_fields(
    context: Dict[str, Any],
    chosen_algo: str,
    rule_order_type: Optional[str] = None,
) -> Tuple[CoreOrderFields, List[str]]:
    """
    Core order fields:
    - Order Type (Market / Limit / Stop) from urgency, liquidity, notes, and price protection.
    - Limit Price using bid/ask reference and buy/sell protection bands.
    - Start / End time from urgency and time-to-close.
    - TIF derived from execution window length.

    Returns:
        (CoreOrderFields, explanation_reasons)
    """
    from datetime import timedelta  # local import to avoid polluting module namespace

    request = context["request"]
    market = context.get("market_snapshot") or {}
    notes_intents = context.get("notes_intents") or {}

    ltp = context.get("ltp", market.get("ltp"))
    bid = context.get("bid", market.get("bid"))
    ask = context.get("ask", market.get("ask"))
    spread = float(context.get("spread", market.get("spread", 0.0)))

    urgency = context.get("urgency_level", "Medium")
    liquidity_bucket = context.get("liquidity_bucket", "Medium")
    effective_ttc = int(context.get("effective_time_to_close", request.time_to_close))

    reasons: List[str] = []

    # 1) Order Type
    order_type = "Limit"

    if rule_order_type:
        order_type = rule_order_type
        reasons.append(f"Order type: {order_type} (rule)")
    else:
        if "stop" in (request.notes or "").lower():
            order_type = "Stop"
            reasons.append("Order type: Stop (notes)")
        elif urgency == "High" and liquidity_bucket in ("High", "Medium") and spread <= 0.10:
            order_type = "Market"
            reasons.append("Order type: Market (urgency, liquidity)")
        else:
            order_type = "Limit"
            reasons.append("Order type: Limit")

    # 2) Limit Price (for Limit/Stop)
    limit_price: Optional[float] = None
    if order_type in ("Limit", "Stop"):
        limit_price = _protection_banded_limit_price(
            direction=request.direction,
            bid=bid,
            ask=ask,
            ltp=ltp,
            spread=spread,
        )
        if limit_price is not None:
            reasons.append("Limit: bid/ask band")

    # 3) Start / End time and TIF
    now = _synthetic_market_now()
    start_time_str = now.strftime("%H:%M")
    if urgency == "High":
        window_minutes = min(effective_ttc, 30)
    elif urgency == "Medium":
        window_minutes = min(effective_ttc, 90)
    else:
        window_minutes = min(effective_ttc, 240)

    # Ensure a non-zero realistic window for algos unless the trader explicitly provided 0.
    if effective_ttc > 0 and window_minutes < 10:
        window_minutes = min(effective_ttc, 10)

    end_dt = now + timedelta(minutes=window_minutes)
    # Keep inside the synthetic trading day (15:59 cap)
    day_cap = now.replace(hour=15, minute=59)
    if end_dt > day_cap:
        end_dt = day_cap
    end_time_str = end_dt.strftime("%H:%M")

    tif = _tif_from_window(effective_ttc)
    reasons.append(f"TIF: {tif} ({window_minutes}m window)")

    core = CoreOrderFields(
        order_type=order_type,
        limit_price=limit_price,
        direction=request.direction,
        time_in_force=tif,
        start_time=start_time_str,
        end_time=end_time_str,
        algo_type=chosen_algo,
    )
    return core, reasons


def build_algo_parameters(
    context: Dict[str, Any],
    chosen_algo: str,
    rule_aggression: Optional[str] = None,
    pattern_aggression: Optional[str] = None,
) -> Tuple[AlgoParameters, List[str]]:
    """
    Algo-specific parameters:
    - POV: % of volume, Min/Max order, Aggression Level.
    - VWAP: volume curve, Max % volume, Aggression Level, urgency, Get Done flag.
    - ICEBERG: display quantity, Aggression Level.

    Resolution priority:
    1) Order notes intents
    2) Trader/client profile (synthetic clients.csv)
    3) Market urgency (time-to-close)

    Returns:
        (AlgoParameters, explanation_reasons)
    """
    request = context["request"]
    client = context.get("client_profile") or {}
    instrument = context.get("instrument_profile") or {}
    market = context.get("market_snapshot") or {}
    notes_intents = context.get("notes_intents") or {}

    urgency = context.get("urgency_level", "Medium")
    volatility_bucket = context.get("volatility_bucket", "Medium")
    adv = instrument.get("adv", 1)
    order_size = request.order_size
    last_trade_size = market.get("last_trade_size", 500)

    reasons: List[str] = []

    # --- Aggression resolution ---
    aggression = client.get("aggression_bias", "Medium") or "Medium"

    if notes_intents.get("aggression_preference") == "HIGH":
        aggression = "High"
        reasons.append("Aggression: High (notes)")
    elif notes_intents.get("aggression_preference") == "LOW":
        aggression = "Low"
        reasons.append("Aggression: Low (notes)")

    if urgency == "High" and aggression != "High":
        aggression = "High"
        reasons.append("Aggression: High (urgency)")

    if pattern_aggression:
        aggression = pattern_aggression
        reasons.append(f"Aggression: {pattern_aggression} (history)")
    if rule_aggression:
        aggression = rule_aggression
        reasons.append(f"Aggression: {rule_aggression} (rule)")

    # Defaults (non-algo-specific)
    participation_rate = None
    min_clip_size = None
    max_clip_size = None
    volume_curve = None
    max_volume_pct = None
    display_quantity = None

    # --- POV parameters ---
    if chosen_algo == "POV":
        base = float(client.get("participation_pref", 0.10))
        if notes_intents.get("benchmark_type") == "ARRIVAL":
            base = min(base + 0.02, 0.30)
        if urgency == "High":
            base = min(0.30, base + 0.05)
        if notes_intents.get("market_impact_sensitive"):
            base = max(0.05, base - 0.03)
        participation_rate = round(base, 2)
        pct = int(participation_rate * 100)
        reasons.append(f"POV participation: {pct}%")

        avg_trade = max(last_trade_size, 100)
        min_clip_size = max(1, int(avg_trade * 0.5))
        max_clip_size = int(avg_trade * 2)
        reasons.append(f"POV clips: {min_clip_size}–{max_clip_size} (vs avg trade)")

    # --- VWAP parameters ---
    elif chosen_algo == "VWAP":
        if notes_intents.get("benchmark_type") == "VWAP":
            volume_curve = "Historical"
        elif urgency == "High":
            volume_curve = "Front-loaded"
        else:
            volume_curve = "Historical"
        reasons.append(f"VWAP curve: {volume_curve}")

        max_volume_pct = 20.0 if volatility_bucket == "High" else 15.0
        reasons.append(f"VWAP max vol: {int(max_volume_pct)}%")

    # --- ICEBERG parameters ---
    elif chosen_algo == "ICEBERG":
        pct_adv = max(1, int(adv * 0.02))
        pct_order = max(1, int(order_size * 0.10))
        display_quantity = min(pct_adv, pct_order)

        if notes_intents.get("market_impact_sensitive"):
            display_quantity = max(1, int(display_quantity * 0.7))
        reasons.append(f"ICEBERG display: {display_quantity}")

    algo_params = AlgoParameters(
        participation_rate=participation_rate,
        min_clip_size=min_clip_size,
        max_clip_size=max_clip_size,
        volume_curve=volume_curve,
        max_volume_pct=max_volume_pct,
        display_quantity=display_quantity,
        aggression_level=aggression,
    )
    return algo_params, reasons

