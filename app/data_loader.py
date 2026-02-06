"""
SmartOrder AI - Load mock data from local CSV files into Pandas DataFrames.
Provides accessors for client, instrument, market snapshot, and historical orders.
"""

import pandas as pd
from typing import Optional, Dict, Any

from .utils import get_data_path, CLIENTS_CSV, INSTRUMENTS_CSV, HISTORICAL_ORDERS_CSV, MARKET_SNAPSHOT_CSV


def _load_csv(name: str) -> pd.DataFrame:
    """Load a CSV from data/ into a DataFrame. Returns empty DataFrame if file missing."""
    path = get_data_path(name)
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def load_all_data() -> Dict[str, pd.DataFrame]:
    """
    Load all four CSVs into a dict of DataFrames.
    Keys: 'clients', 'instruments', 'historical_orders', 'market_snapshot'.
    """
    return {
        "clients": _load_csv(CLIENTS_CSV),
        "instruments": _load_csv(INSTRUMENTS_CSV),
        "historical_orders": _load_csv(HISTORICAL_ORDERS_CSV),
        "market_snapshot": _load_csv(MARKET_SNAPSHOT_CSV),
    }


def get_client_profile(client_id: str, data: Optional[Dict[str, pd.DataFrame]] = None) -> Optional[Dict[str, Any]]:
    """
    Get client profile by client_id.
    Returns dict with keys: urgency_profile, preferred_algo, aggression_bias, participation_pref.
    """
    df = (data or {}).get("clients")
    if df is None or df.empty:
        df = _load_csv(CLIENTS_CSV)
    row = df[df["client_id"] == client_id]
    if row.empty:
        return None
    r = row.iloc[0]
    return {
        "client_id": str(r["client_id"]),
        "urgency_profile": str(r["urgency_profile"]),
        "preferred_algo": str(r["preferred_algo"]),
        "aggression_bias": str(r["aggression_bias"]),
        "participation_pref": float(r["participation_pref"]),
    }


def get_instrument_profile(symbol: str, data: Optional[Dict[str, pd.DataFrame]] = None) -> Optional[Dict[str, Any]]:
    """
    Get instrument profile by symbol.
    Returns dict with: symbol, adv, volatility_bucket, liquidity_bucket.
    """
    df = (data or {}).get("instruments")
    if df is None or df.empty:
        df = _load_csv(INSTRUMENTS_CSV)
    row = df[df["symbol"] == symbol]
    if row.empty:
        return None
    r = row.iloc[0]
    return {
        "symbol": str(r["symbol"]),
        "adv": int(r["adv"]),
        "volatility_bucket": str(r["volatility_bucket"]),
        "liquidity_bucket": str(r["liquidity_bucket"]),
    }


def get_market_snapshot(symbol: str, data: Optional[Dict[str, pd.DataFrame]] = None) -> Optional[Dict[str, Any]]:
    """
    Get market snapshot for symbol.
    Returns dict with: symbol, spread, intraday_vol, last_trade_size, bid, ask, ltp.
    """
    df = (data or {}).get("market_snapshot")
    if df is None or df.empty:
        df = _load_csv(MARKET_SNAPSHOT_CSV)
    row = df[df["symbol"] == symbol]
    if row.empty:
        return None
    r = row.iloc[0]
    return {
        "symbol": str(r["symbol"]),
        "spread": float(r["spread"]),
        "intraday_vol": float(r["intraday_vol"]),
        "last_trade_size": int(r["last_trade_size"]),
        "bid": float(r["bid"]),
        "ask": float(r["ask"]),
        "ltp": float(r["ltp"]),
    }


def get_historical_data(data: Optional[Dict[str, pd.DataFrame]] = None) -> pd.DataFrame:
    """Return full historical orders DataFrame (client_id, symbol, size_bucket, volatility_bucket, algo_used, aggression_level)."""
    if data and "historical_orders" in data:
        return data["historical_orders"].copy()
    return _load_csv(HISTORICAL_ORDERS_CSV)
