"""
SmartOrder AI - Streamlit Frontend (Hackathon Prototype)
-------------------------------------------------------
Professional-style institutional order ticket UI that:
- Collects core order inputs (trader-entered)
- Calls the SmartOrder AI backend to get an intelligent prefill
- Prefills the ticket (but NEVER locks fields)
- Shows clear explanations + context flags (read-only)

Backend (assumed already running):
POST http://127.0.0.1:8001/recommend

Run:
  streamlit run streamlit_app.py
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
from typing import Any, Dict, List, Optional

import html
import requests
import streamlit as st
import pandas as pd
from pathlib import Path


# -----------------------------
# Configuration
# -----------------------------

API_URL = "http://127.0.0.1:8001/recommend"

# Static mock values for dropdowns (hackathon prototype)
MOCK_CLIENTS = [
    "CLT001",
    "CLT002",
    "CLT003",
    "CLT004",
    "CLT005",
    "CLT006",
    "CLT007",
    "CLT008",
    "CLT009",
    "CLT010",
]

SIDES = ["Buy", "Sell"]
ORDER_TYPES = ["Market", "Limit"]
TIFS = ["DAY", "IOC", "GTC"]
ALGOS = ["VWAP", "POV", "ICEBERG"]
AGGRESSION_LEVELS = ["Low", "Medium", "High"]
VWAP_CURVES = ["Historical", "Front-loaded"]


# -----------------------------
# Small helpers
# -----------------------------


def _parse_hhmm(s: Optional[str]) -> Optional[time]:
    """Parse 'HH:MM' into a time object."""
    if not s:
        return None
    try:
        return datetime.strptime(s, "%H:%M").time()
    except ValueError:
        return None


def _time_to_hhmm(t: Optional[time]) -> Optional[str]:
    """Format time object as 'HH:MM'."""
    if t is None:
        return None
    return t.strftime("%H:%M")


def _safe_float(x: Any) -> Optional[float]:
    try:
        if x is None:
            return None
        return float(x)
    except Exception:
        return None


def _safe_int(x: Any) -> Optional[int]:
    try:
        if x is None:
            return None
        return int(x)
    except Exception:
        return None


def _ss_get(key: str, default: Any) -> Any:
    if key not in st.session_state:
        st.session_state[key] = default
    return st.session_state[key]


def _mark_override(key: str) -> None:
    """
    Mark a field as trader-overridden.
    Called by widget on_change callbacks.
    """
    overrides: Dict[str, bool] = st.session_state.setdefault("overrides", {})
    overrides[key] = True


def _set_field_if_not_overridden(key: str, value: Any) -> None:
    """
    Apply AI-prefill into the live widget value ONLY if the trader
    hasn't overridden that field since the last prefill.
    """
    overrides: Dict[str, bool] = st.session_state.setdefault("overrides", {})
    if not overrides.get(key, False):
        st.session_state[key] = value


def _set_suggested(key: str, value: Any) -> None:
    """Store AI-suggested value for yellow-highlight styling."""
    suggested: Dict[str, Any] = st.session_state.setdefault("suggested", {})
    suggested[key] = value


def _is_suggested(key: str) -> bool:
    """True if this field was AI-prefilled (yellow strip indicator)."""
    return key in st.session_state.get("suggested", {})


# -----------------------------
# API client
# -----------------------------


@dataclass
class ApiResult:
    ok: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


def call_recommend_api(payload: Dict[str, Any]) -> ApiResult:
    """
    Call backend and return parsed JSON.
    No external integrations; local only.
    """
    try:
        r = requests.post(API_URL, json=payload, timeout=10)
        if r.status_code >= 400:
            return ApiResult(ok=False, error=f"API {r.status_code}: {r.text}")
        return ApiResult(ok=True, data=r.json())
    except requests.RequestException as e:
        return ApiResult(ok=False, error=f"API request failed: {e}")
    except ValueError:
        return ApiResult(ok=False, error="API returned non-JSON response")


def apply_prefill_from_response(resp: Dict[str, Any]) -> None:
    """
    Map backend response into UI fields.
    CRITICAL: Prefill != lock. We only set fields if not overridden.
    """
    st.session_state["api_response"] = resp

    core = resp.get("core_order_fields", {}) or {}
    algo = resp.get("algo_parameters", {}) or {}
    context = resp.get("context_flags", {}) or {}

    # --- Core Order Fields ---
    _set_suggested("order_type", core.get("order_type"))
    _set_field_if_not_overridden("order_type", core.get("order_type") or "Limit")

    _set_suggested("limit_price", _safe_float(core.get("limit_price")))
    _set_field_if_not_overridden("limit_price", _safe_float(core.get("limit_price")))

    _set_suggested("time_in_force", core.get("time_in_force"))
    _set_field_if_not_overridden("time_in_force", core.get("time_in_force") or "DAY")

    _set_suggested("algo_type", core.get("algo_type"))
    _set_field_if_not_overridden("algo_type", core.get("algo_type") or "VWAP")

    # --- Timing (backend uses HH:MM strings) ---
    st_t = _parse_hhmm(core.get("start_time"))
    en_t = _parse_hhmm(core.get("end_time"))
    if st_t:
        _set_suggested("start_time", st_t)
        _set_field_if_not_overridden("start_time", st_t)
    if en_t:
        _set_suggested("end_time", en_t)
        _set_field_if_not_overridden("end_time", en_t)

    # --- Algo Parameters (dynamic) ---
    # Aggression applies to all.
    _set_suggested("aggression_level", algo.get("aggression_level"))
    _set_field_if_not_overridden("aggression_level", algo.get("aggression_level") or "Medium")

    # VWAP
    _set_suggested("vwap_volume_curve", algo.get("volume_curve"))
    _set_field_if_not_overridden("vwap_volume_curve", algo.get("volume_curve") or "Historical")
    _set_suggested("vwap_max_volume_pct", _safe_float(algo.get("max_volume_pct")))
    _set_field_if_not_overridden("vwap_max_volume_pct", _safe_float(algo.get("max_volume_pct")))

    # POV
    _set_suggested("pov_participation_rate", _safe_float(algo.get("participation_rate")))
    _set_field_if_not_overridden("pov_participation_rate", _safe_float(algo.get("participation_rate")))
    _set_suggested("pov_min_clip", _safe_int(algo.get("min_clip_size")))
    _set_field_if_not_overridden("pov_min_clip", _safe_int(algo.get("min_clip_size")))
    _set_suggested("pov_max_clip", _safe_int(algo.get("max_clip_size")))
    _set_field_if_not_overridden("pov_max_clip", _safe_int(algo.get("max_clip_size")))

    # ICEBERG
    _set_suggested("iceberg_display_quantity", _safe_int(algo.get("display_quantity")))
    _set_field_if_not_overridden("iceberg_display_quantity", _safe_int(algo.get("display_quantity")))

    # Context flags are read-only; store for explain panel.
    st.session_state["context_flags"] = context
    st.session_state["explanations"] = resp.get("explanations", []) or []


def reset_prefill_state() -> None:
    """Clear API response, suggested values, and override flags (keeps current inputs)."""
    st.session_state["api_response"] = None
    st.session_state["suggested"] = {}
    st.session_state["overrides"] = {}
    st.session_state["context_flags"] = {}
    st.session_state["explanations"] = []
    st.session_state["pending_api_response"] = None
    st.session_state["last_prefill_ok"] = None
    st.session_state["last_prefill_msg"] = ""


# -----------------------------
# Streamlit page
# -----------------------------


st.set_page_config(page_title="suggestION", layout="wide")

# Compact layout and yellow highlight for AI-prefilled fields (single-screen, no scroll)
st.markdown(
    """
<style>
  .block-container { padding-top: 2rem; padding-bottom: 0.35rem; }
  div[data-testid="stVerticalBlock"] { gap: 0.35rem !important; }
  div[data-testid="stVerticalBlock"] div:has(> div[data-testid="stForm"]) { gap: 0.25rem !important; }
  div[data-testid="stHorizontalBlock"] { gap: 0.5rem !important; }
  label { margin-bottom: 0.15rem !important; }
  .stCaption { margin-top: -0.3rem; font-size: 0.82rem; }
  .prefill-yellow-strip { background: #fffde7; border-radius: 3px; min-height: 2rem; }
  button[kind="primary"] { background-color: #1E88E5 !important; }
  h1 { font-size: 1.5rem !important; margin-top: 0.25rem !important; margin-bottom: 0.05rem !important; }
  h2 { font-size: 1.2rem !important; margin-top: 0.25rem !important; margin-bottom: 0.2rem !important; }
  h3 { font-size: 1.0rem !important; margin-top: 0.25rem !important; margin-bottom: 0.2rem !important; }
  hr { margin: 0.35rem 0 !important; }
  [data-testid="stExpander"] { margin: 0.2rem 0 !important; }
  /* Force Order Notes text area smaller (Streamlit enforces min ~98px otherwise) */
  div[data-testid="stTextArea"] textarea { height: 52px !important; min-height: 52px !important; }
</style>
""",
    unsafe_allow_html=True,
)

st.title("suggestION")


# -----------------------------
# Session defaults
# -----------------------------


_ss_get("api_response", None)
_ss_get("suggested", {})
_ss_get("overrides", {})
_ss_get("context_flags", {})
_ss_get("explanations", [])
_ss_get("pending_api_response", None)
_ss_get("last_prefill_ok", None)
_ss_get("last_prefill_msg", "")

# Market data cache: only refresh when symbol changes (not on Fill All rerun)
_ss_get("market_data_symbol", None)
_ss_get("market_data_cache", None)

# Core trader-entered inputs (request)
_ss_get("client_id", MOCK_CLIENTS[0])
_ss_get("direction", "Buy")
_ss_get("order_size", 1000)
_ss_get("symbol", "AAPL")
_ss_get("time_to_close", 120)
_ss_get("notes", "")

# Prefill targets (these remain editable)
_ss_get("order_type", "Limit")
_ss_get("limit_price", None)  # float or None
_ss_get("time_in_force", "DAY")
_ss_get("display_qty_core", None)  # optional "Display Qty" at top

_ss_get("algo_type", "VWAP")
_ss_get("hold", "No")
_ss_get("start_time", datetime.now().time().replace(second=0, microsecond=0))
_ss_get("end_time", time(16, 0))

# Algo dynamic fields
_ss_get("aggression_level", "Medium")
_ss_get("urgency_ui", "Auto")  # UI-only (backend also returns urgency in context_flags)

_ss_get("vwap_volume_curve", "Historical")
_ss_get("vwap_max_volume_pct", None)

_ss_get("pov_participation_rate", None)
_ss_get("pov_min_clip", None)
_ss_get("pov_max_clip", None)

_ss_get("iceberg_display_quantity", None)


# Apply any pending AI prefill BEFORE widgets are built.
# This avoids modifying st.session_state widget keys after
# their widgets have been instantiated in the same run.
pending_resp = st.session_state.get("pending_api_response")
if pending_resp is not None:
    apply_prefill_from_response(pending_resp)
    st.session_state["pending_api_response"] = None


# -----------------------------
# Layout: main ticket (left) + explainability panel (right)
# -----------------------------


ticket_col, explain_col = st.columns([3.2, 1.3], gap="medium")


with ticket_col:
    # -------- SECTION 1 — Core Order Entry (Top) --------
    st.subheader("🟦 Core Order Entry")

    c1, c2, c3, c4, c5, c6, c7, c8 = st.columns([1.1, 0.8, 1.0, 1.0, 1.0, 1.0, 0.9, 0.9], gap="small")

    with c1:
        st.selectbox(
            "Client",
            options=MOCK_CLIENTS,
            key="client_id",
            on_change=_mark_override,
            args=("client_id",),
        )

    with c2:
        st.selectbox("Side", options=SIDES, key="direction", on_change=_mark_override, args=("direction",))

    with c3:
        st.number_input(
            "Quantity",
            min_value=1,
            step=100,
            key="order_size",
            on_change=_mark_override,
            args=("order_size",),
        )

    with c4:
        st.text_input("Symbol", key="symbol", on_change=_mark_override, args=("symbol",))

    with c5:
        if _is_suggested("order_type"):
            _s, _m = st.columns([0.06, 0.94])
            with _s:
                st.markdown('<div class="prefill-yellow-strip">&nbsp;</div>', unsafe_allow_html=True)
            with _m:
                st.selectbox("Order Type", options=ORDER_TYPES, key="order_type", on_change=_mark_override, args=("order_type",))
        else:
            st.selectbox("Order Type", options=ORDER_TYPES, key="order_type", on_change=_mark_override, args=("order_type",))

    with c6:
        if _is_suggested("limit_price"):
            _s, _m = st.columns([0.06, 0.94])
            with _s:
                st.markdown('<div class="prefill-yellow-strip">&nbsp;</div>', unsafe_allow_html=True)
            with _m:
                st.number_input("Limit Price", min_value=0.0, step=0.01, format="%.2f", key="limit_price", on_change=_mark_override, args=("limit_price",))
        else:
            st.number_input("Limit Price", min_value=0.0, step=0.01, format="%.2f", key="limit_price", on_change=_mark_override, args=("limit_price",))

    with c7:
        if _is_suggested("time_in_force"):
            _s, _m = st.columns([0.06, 0.94])
            with _s:
                st.markdown('<div class="prefill-yellow-strip">&nbsp;</div>', unsafe_allow_html=True)
            with _m:
                st.selectbox("TIF", options=TIFS, key="time_in_force", on_change=_mark_override, args=("time_in_force",))
        else:
            st.selectbox("TIF", options=TIFS, key="time_in_force", on_change=_mark_override, args=("time_in_force",))

    with c8:
        if _is_suggested("display_qty_core"):
            _s, _m = st.columns([0.06, 0.94])
            with _s:
                st.markdown('<div class="prefill-yellow-strip">&nbsp;</div>', unsafe_allow_html=True)
            with _m:
                st.number_input("Display Qty", min_value=0, step=100, key="display_qty_core", on_change=_mark_override, args=("display_qty_core",))
        else:
            st.number_input("Display Qty", min_value=0, step=100, key="display_qty_core", on_change=_mark_override, args=("display_qty_core",))

    # Prefill action row
    b1, b2, b3, _sp = st.columns([1.2, 1.2, 1.6, 5.0], gap="small")
    with b1:
        generate = st.button("Fill All", type="primary", use_container_width=True)
    with b2:
        clear = st.button("Clear Prefill", use_container_width=True)
    with b3:
        st.number_input("Minutes to Close", min_value=0, step=5, key="time_to_close", on_change=_mark_override, args=("time_to_close",))

    status_msg = st.session_state.get("last_prefill_msg")
    status_ok = st.session_state.get("last_prefill_ok")
    if status_msg:
        esc = html.escape(status_msg)
        if status_ok:
            st.markdown('<p style="color: #2e7d32; font-size: 0.8rem; margin: 0.15rem 0;">' + esc + '</p>', unsafe_allow_html=True)
        else:
            st.markdown('<p style="color: #e65100; font-size: 0.8rem; margin: 0.15rem 0;">' + esc + '</p>', unsafe_allow_html=True)

    if clear:
        reset_prefill_state()
        st.markdown('<p style="color: #2e7d32; font-size: 0.8rem; margin: 0.15rem 0;">Cleared AI-prefill state. All fields remain as you set them.</p>', unsafe_allow_html=True)

    if generate:
        payload = {
            "client_id": st.session_state["client_id"],
            "symbol": st.session_state["symbol"],
            "order_size": int(st.session_state["order_size"]),
            "direction": st.session_state["direction"],
            "time_to_close": int(st.session_state["time_to_close"]),
            "notes": st.session_state.get("notes", "") or "",
        }
        api = call_recommend_api(payload)
        if not api.ok:
            st.session_state["last_prefill_ok"] = False
            st.session_state["last_prefill_msg"] = api.error or "Unknown API error. You can continue manual entry."
            st.session_state["pending_api_response"] = None
        else:
            st.session_state["last_prefill_ok"] = True
            st.session_state["last_prefill_msg"] = "Smart Prefill applied. You can override any field."
            st.session_state["pending_api_response"] = api.data or {}
        # Trigger a rerun so the prefill is applied before widgets render
        st.rerun()

    st.divider()

    # -------- SECTION 2 — Order Notes --------
    st.subheader("🟦 Order Notes")
    st.text_area("Order Notes", key="notes", height=10, on_change=_mark_override, args=("notes",))

    st.divider()

    # -------- SECTION 3 — Algo Selection & Timing --------
    st.subheader("🟦 Algo Selection & Timing")
    a1, a2, a3, a4, a5 = st.columns([1.4, 1.4, 1.0, 1.1, 1.1], gap="small")

    with a1:
        st.text_input("Service", value="SmartOrder AI", disabled=True)

    with a2:
        if _is_suggested("algo_type"):
            _s, _m = st.columns([0.06, 0.94])
            with _s:
                st.markdown('<div class="prefill-yellow-strip">&nbsp;</div>', unsafe_allow_html=True)
            with _m:
                st.selectbox("Executor / Algo Type", options=ALGOS, key="algo_type", on_change=_mark_override, args=("algo_type",))
        else:
            st.selectbox("Executor / Algo Type", options=ALGOS, key="algo_type", on_change=_mark_override, args=("algo_type",))

    with a3:
        st.selectbox("Hold", options=["No", "Yes"], key="hold", on_change=_mark_override, args=("hold",))

    with a4:
        if _is_suggested("start_time"):
            _s, _m = st.columns([0.06, 0.94])
            with _s:
                st.markdown('<div class="prefill-yellow-strip">&nbsp;</div>', unsafe_allow_html=True)
            with _m:
                st.time_input("Start Time", key="start_time", on_change=_mark_override, args=("start_time",))
        else:
            st.time_input("Start Time", key="start_time", on_change=_mark_override, args=("start_time",))

    with a5:
        if _is_suggested("end_time"):
            _s, _m = st.columns([0.06, 0.94])
            with _s:
                st.markdown('<div class="prefill-yellow-strip">&nbsp;</div>', unsafe_allow_html=True)
            with _m:
                st.time_input("End Time", key="end_time", on_change=_mark_override, args=("end_time",))
        else:
            st.time_input("End Time", key="end_time", on_change=_mark_override, args=("end_time",))

    st.divider()

    # -------- SECTION 4 — Algo Parameters (Dynamic) --------
    st.subheader("🟦 Algo Parameters (Dynamic)")

    # Shared parameters row
    p_shared1, p_shared2 = st.columns([1.2, 1.2], gap="small")
    with p_shared1:
        if _is_suggested("aggression_level"):
            _s, _m = st.columns([0.06, 0.94])
            with _s:
                st.markdown('<div class="prefill-yellow-strip">&nbsp;</div>', unsafe_allow_html=True)
            with _m:
                st.selectbox("Aggression Level", options=AGGRESSION_LEVELS, key="aggression_level", on_change=_mark_override, args=("aggression_level",))
        else:
            st.selectbox("Aggression Level", options=AGGRESSION_LEVELS, key="aggression_level", on_change=_mark_override, args=("aggression_level",))
    with p_shared2:
        # UX: required in spec; backend already returns urgency_level in context flags
        st.selectbox(
            "Urgency (UI)",
            options=["Auto", "Low", "Medium", "High"],
            key="urgency_ui",
            on_change=_mark_override,
            args=("urgency_ui",),
        )

    chosen_algo_ui = st.session_state.get("algo_type", "VWAP")

    if chosen_algo_ui == "VWAP":
        v1, v2 = st.columns([1.2, 1.2], gap="small")
        with v1:
            if _is_suggested("vwap_volume_curve"):
                _s, _m = st.columns([0.06, 0.94])
                with _s:
                    st.markdown('<div class="prefill-yellow-strip">&nbsp;</div>', unsafe_allow_html=True)
                with _m:
                    st.selectbox("Volume Curve", options=VWAP_CURVES, key="vwap_volume_curve", on_change=_mark_override, args=("vwap_volume_curve",))
            else:
                st.selectbox("Volume Curve", options=VWAP_CURVES, key="vwap_volume_curve", on_change=_mark_override, args=("vwap_volume_curve",))
        with v2:
            if _is_suggested("vwap_max_volume_pct"):
                _s, _m = st.columns([0.06, 0.94])
                with _s:
                    st.markdown('<div class="prefill-yellow-strip">&nbsp;</div>', unsafe_allow_html=True)
                with _m:
                    st.number_input("Max % of Volume", min_value=0.0, max_value=100.0, step=1.0, key="vwap_max_volume_pct", on_change=_mark_override, args=("vwap_max_volume_pct",))
            else:
                st.number_input("Max % of Volume", min_value=0.0, max_value=100.0, step=1.0, key="vwap_max_volume_pct", on_change=_mark_override, args=("vwap_max_volume_pct",))

    elif chosen_algo_ui == "POV":
        p1, p2, p3 = st.columns([1.2, 1.2, 1.2], gap="small")
        with p1:
            if _is_suggested("pov_participation_rate"):
                _s, _m = st.columns([0.06, 0.94])
                with _s:
                    st.markdown('<div class="prefill-yellow-strip">&nbsp;</div>', unsafe_allow_html=True)
                with _m:
                    st.number_input("Target Participation %", min_value=0.0, max_value=1.0, step=0.01, format="%.2f", key="pov_participation_rate", on_change=_mark_override, args=("pov_participation_rate",))
            else:
                st.number_input("Target Participation %", min_value=0.0, max_value=1.0, step=0.01, format="%.2f", key="pov_participation_rate", on_change=_mark_override, args=("pov_participation_rate",))
        with p2:
            if _is_suggested("pov_min_clip"):
                _s, _m = st.columns([0.06, 0.94])
                with _s:
                    st.markdown('<div class="prefill-yellow-strip">&nbsp;</div>', unsafe_allow_html=True)
                with _m:
                    st.number_input("Min Clip Qty", min_value=0, step=100, key="pov_min_clip", on_change=_mark_override, args=("pov_min_clip",))
            else:
                st.number_input("Min Clip Qty", min_value=0, step=100, key="pov_min_clip", on_change=_mark_override, args=("pov_min_clip",))
        with p3:
            if _is_suggested("pov_max_clip"):
                _s, _m = st.columns([0.06, 0.94])
                with _s:
                    st.markdown('<div class="prefill-yellow-strip">&nbsp;</div>', unsafe_allow_html=True)
                with _m:
                    st.number_input("Max Clip Qty", min_value=0, step=100, key="pov_max_clip", on_change=_mark_override, args=("pov_max_clip",))
            else:
                st.number_input("Max Clip Qty", min_value=0, step=100, key="pov_max_clip", on_change=_mark_override, args=("pov_max_clip",))

    elif chosen_algo_ui == "ICEBERG":
        if _is_suggested("iceberg_display_quantity"):
            _s, _m = st.columns([0.06, 0.94])
            with _s:
                st.markdown('<div class="prefill-yellow-strip">&nbsp;</div>', unsafe_allow_html=True)
            with _m:
                st.number_input("Display Quantity", min_value=0, step=100, key="iceberg_display_quantity", on_change=_mark_override, args=("iceberg_display_quantity",))
        else:
            st.number_input("Display Quantity", min_value=0, step=100, key="iceberg_display_quantity", on_change=_mark_override, args=("iceberg_display_quantity",))

    st.divider()

with explain_col:
    # -------- Market Data (Top Right) --------
    # Only refresh market data when the user changes the symbol, not on Fill All rerun
    symbol = st.session_state.get("symbol", "AAPL")
    cache_symbol = st.session_state.get("market_data_symbol")
    cache = st.session_state.get("market_data_cache")
    if cache_symbol != symbol or cache is None:
        try:
            data_path = Path(__file__).parent / "data" / "market_snapshot.csv"
            if data_path.exists():
                df = pd.read_csv(data_path)
                market_row = df[df["symbol"] == symbol]
                if not market_row.empty:
                    m = market_row.iloc[0]
                    st.session_state["market_data_cache"] = {
                        "bid": float(m["bid"]), "ask": float(m["ask"]), "ltp": float(m["ltp"]),
                        "spread": float(m["spread"]), "intraday_vol": float(m["intraday_vol"]),
                        "last_trade_size": int(m["last_trade_size"]),
                    }
                    st.session_state["market_data_symbol"] = symbol
                else:
                    st.session_state["market_data_cache"] = None
                    st.session_state["market_data_symbol"] = symbol
            else:
                st.session_state["market_data_cache"] = None
                st.session_state["market_data_symbol"] = symbol
        except Exception:
            st.session_state["market_data_cache"] = None
            st.session_state["market_data_symbol"] = symbol
        cache = st.session_state.get("market_data_cache")
        cache_symbol = st.session_state.get("market_data_symbol")

    st.subheader("🟦 Market Data")
    if cache is not None and cache_symbol == symbol:
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Bid", f"${cache['bid']:.2f}")
            st.metric("Ask", f"${cache['ask']:.2f}")
        with col2:
            st.metric("LTP", f"${cache['ltp']:.2f}")
            st.metric("Spread", f"${cache['spread']:.2f}")
        st.caption(f"Vol: {cache['intraday_vol']:.3f} | Last: {int(cache['last_trade_size'])}")
    else:
        st.info(f"No market data for {symbol}" if cache_symbol == symbol else "Market data unavailable")

    st.divider()

    # -------- SECTION 5 — Explainability Panel (Right / Below) --------
    st.subheader("🟦 Explainability")
    explanations: List[str] = st.session_state.get("explanations", []) or []
    if explanations:
        for e in explanations:
            st.markdown(f"- {e}")
    else:
        st.info("No explanations yet. Click Fill All.")


