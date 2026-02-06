"""
SmartOrder AI - Generate core order fields and algo-specific parameters
from chosen algo, context, rule overrides, and market data.
"""

from typing import Dict, Any, Optional
from datetime import datetime

from .models import CoreOrderFields, AlgoParameters


def _now_time_str() -> str:
    """Current time as HH:MM (e.g. 09:45)."""
    return datetime.now().strftime("%H:%M")


def _end_time_from_urgency(time_to_close: int, urgency: str) -> str:
    """End time: approximate from time_to_close. Simple mock: 16:00 - minutes or fixed windows."""
    if urgency == "High":
        # EOD -> 15:55
        return "15:55"
    if urgency == "Medium":
        return "14:30"
    return "16:00"


def build_core_fields(
    context: Dict[str, Any],
    chosen_algo: str,
    rule_order_type: Optional[str] = None,
) -> CoreOrderFields:
    """
    Core order fields:
    - order_type = Market if urgency high & liquid; else Limit (or from rule).
    - limit_price = LTP ± 0.1% if passive (Limit).
    - start_time = now, end_time from urgency / time_to_close.
    """
    request = context["request"]
    market = context.get("market_snapshot") or {}
    ltp = market.get("ltp", 0.0)
    urgency = context.get("urgency_level", "Medium")
    liquidity = context.get("liquidity_bucket", "Medium")
    time_to_close = request.time_to_close

    # Order type: rule override, else Market only if high urgency and liquid
    if rule_order_type:
        order_type = rule_order_type
    elif urgency == "High" and liquidity in ("High", "Medium"):
        order_type = "Market"
    else:
        order_type = "Limit"

    # Limit price: LTP ± 0.1% for passive (Buy: LTP - 0.1%, Sell: LTP + 0.1%)
    limit_price = None
    if order_type == "Limit" and ltp:
        pct = 0.001
        if request.direction.lower() == "buy":
            limit_price = round(ltp * (1 - pct), 2)
        else:
            limit_price = round(ltp * (1 + pct), 2)

    start_time = _now_time_str()
    end_time = _end_time_from_urgency(time_to_close, urgency)

    return CoreOrderFields(
        order_type=order_type,
        limit_price=limit_price,
        direction=request.direction,
        time_in_force="DAY",
        start_time=start_time,
        end_time=end_time,
        algo_type=chosen_algo,
    )


def build_algo_parameters(
    context: Dict[str, Any],
    chosen_algo: str,
    rule_aggression: Optional[str] = None,
    pattern_aggression: Optional[str] = None,
) -> AlgoParameters:
    """
    Algo-specific parameters:
    - POV: participation_rate (client pref + urgency), min/max clip from avg trade size.
    - VWAP: volume_curve (historical or front-loaded), max_volume_pct (20% high vol, else 15%).
    - ICEBERG: display_quantity = min(2% ADV, 10% order size).
    Aggression: rule > pattern > client bias.
    """
    request = context["request"]
    client = context.get("client_profile") or {}
    instrument = context.get("instrument_profile") or {}
    market = context.get("market_snapshot") or {}
    urgency = context.get("urgency_level", "Medium")
    volatility_bucket = context.get("volatility_bucket", "Medium")
    adv = instrument.get("adv", 1)
    order_size = request.order_size
    last_trade_size = market.get("last_trade_size", 500)

    # Aggression: rule override > pattern > client bias > default Medium
    aggression = rule_aggression or pattern_aggression or client.get("aggression_bias", "Medium") or "Medium"

    # Defaults (non-algo-specific)
    participation_rate = None
    min_clip_size = None
    max_clip_size = None
    volume_curve = None
    max_volume_pct = None
    display_quantity = None

    if chosen_algo == "POV":
        # participation_rate from client pref + urgency bump
        base = float(client.get("participation_pref", 0.10))
        if urgency == "High":
            base = min(0.25, base + 0.05)
        participation_rate = round(base, 2)
        # Clips relative to avg trade size (use last_trade_size as proxy)
        avg_trade = max(last_trade_size, 100)
        min_clip_size = max(1, int(avg_trade * 0.5))
        max_clip_size = int(avg_trade * 2)

    elif chosen_algo == "VWAP":
        volume_curve = "Front-loaded" if urgency == "High" else "Historical"
        max_volume_pct = 20.0 if volatility_bucket == "High" else 15.0

    elif chosen_algo == "ICEBERG":
        # display_quantity = min(2% ADV, 10% order size)
        pct_adv = max(1, int(adv * 0.02))
        pct_order = max(1, int(order_size * 0.10))
        display_quantity = min(pct_adv, pct_order)

    return AlgoParameters(
        participation_rate=participation_rate,
        min_clip_size=min_clip_size,
        max_clip_size=max_clip_size,
        volume_curve=volume_curve,
        max_volume_pct=max_volume_pct,
        display_quantity=display_quantity,
        aggression_level=aggression,
    )
