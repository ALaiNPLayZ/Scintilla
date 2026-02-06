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

import requests
import streamlit as st


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
    """Store AI-suggested value separately (for display/debug)."""
    suggested: Dict[str, Any] = st.session_state.setdefault("suggested", {})
    suggested[key] = value


def _suggested_badge(key: str) -> str:
    """Subtle label suffix to indicate the field can be AI-prefilled."""
    # We keep this subtle (no color blocks), but consistent.
    suggested = st.session_state.get("suggested", {})
    return " • Suggested" if key in suggested else ""


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


st.set_page_config(page_title="SmartOrder AI - Order Ticket", layout="wide")

# Minimal enterprise-neutral tweaks (no external styling frameworks)
st.markdown(
    """
<style>
  /* Make the UI denser (more OMS-like) */
  .block-container { padding-top: 1rem; padding-bottom: 1rem; }
  div[data-testid="stVerticalBlock"] div:has(> div[data-testid="stForm"]) { gap: 0.4rem; }
  /* Slightly reduce label spacing */
  label { margin-bottom: 0.15rem !important; }
  /* Tighten captions */
  .stCaption { margin-top: -0.25rem; }
</style>
""",
    unsafe_allow_html=True,
)

st.title("SmartOrder AI – Intelligent Order Ticket Prefill")
st.caption(
    "Generate AI-prefilled suggestions, then freely override any field. "
    "This is a mock prototype (no external integrations)."
)


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

_ss_get("instructions", "")
_ss_get("flags", [])

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


ticket_col, explain_col = st.columns([3.2, 1.3], gap="large")


with ticket_col:
    status_msg = st.session_state.get("last_prefill_msg")
    status_ok = st.session_state.get("last_prefill_ok")
    if status_msg:
        if status_ok:
            st.success(status_msg)
        else:
            st.warning(status_msg)

    # -------- SECTION 1 — Core Order Entry (Top) --------
    st.subheader("🟦 Core Order Entry")
    st.caption("Compact institutional-style ticket entry. Fields marked “Suggested” may be AI-prefilled.")

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
        st.selectbox(
            f"Order Type{_suggested_badge('order_type')}",
            options=ORDER_TYPES,
            key="order_type",
            on_change=_mark_override,
            args=("order_type",),
        )

    with c6:
        st.number_input(
            f"Limit Price{_suggested_badge('limit_price')}",
            min_value=0.0,
            step=0.01,
            format="%.2f",
            key="limit_price",
            on_change=_mark_override,
            args=("limit_price",),
            help="AI may suggest a passive limit around LTP; you can override any time.",
        )

    with c7:
        st.selectbox(
            f"TIF{_suggested_badge('time_in_force')}",
            options=TIFS,
            key="time_in_force",
            on_change=_mark_override,
            args=("time_in_force",),
        )

    with c8:
        st.number_input(
            f"Display Qty{_suggested_badge('iceberg_display_quantity')}",
            min_value=0,
            step=100,
            key="display_qty_core",
            on_change=_mark_override,
            args=("display_qty_core",),
            help="Optional. For ICEBERG you may prefer using the ICEBERG Display Quantity below.",
        )

    # Prefill action row
    b1, b2, b3, _sp = st.columns([1.2, 1.2, 1.6, 5.0], gap="small")
    with b1:
        generate = st.button("Generate Smart Prefill", type="primary", use_container_width=True)
    with b2:
        clear = st.button("Clear Prefill", use_container_width=True)
    with b3:
        st.number_input(
            "Minutes to Close",
            min_value=0,
            step=5,
            key="time_to_close",
            on_change=_mark_override,
            args=("time_to_close",),
            help="Used by SmartOrder AI to infer urgency and time window.",
        )

    if clear:
        reset_prefill_state()
        st.success("Cleared AI-prefill state. All fields remain as you set them.")

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

    # -------- SECTION 2 — Order Notes & Instructions --------
    st.subheader("🟦 Order Notes & Instructions")
    n1, n2, n3 = st.columns([2.2, 1.2, 1.6], gap="small")
    with n1:
        st.text_area(
            "Order Notes",
            key="notes",
            height=90,
            on_change=_mark_override,
            args=("notes",),
            help='Free text. Keywords like "VWAP", "urgent", "benchmark" can influence suggestions.',
        )
    with n2:
        st.text_input("Instructions (optional)", key="instructions", on_change=_mark_override, args=("instructions",))
    with n3:
        st.multiselect(
            "Flags (optional)",
            options=["Benchmark", "NoCross", "MinImpact", "Urgent", "Careful"],
            key="flags",
            on_change=_mark_override,
            args=("flags",),
        )

    st.divider()

    # -------- SECTION 3 — Algo Selection & Timing --------
    st.subheader("🟦 Algo Selection & Timing")
    a1, a2, a3, a4, a5 = st.columns([1.4, 1.4, 1.0, 1.1, 1.1], gap="small")

    with a1:
        st.text_input("Service", value="SmartOrder AI", disabled=True)

    with a2:
        st.selectbox(
            f"Executor / Algo Type{_suggested_badge('algo_type')}",
            options=ALGOS,
            key="algo_type",
            on_change=_mark_override,
            args=("algo_type",),
        )

    with a3:
        st.selectbox("Hold", options=["No", "Yes"], key="hold", on_change=_mark_override, args=("hold",))

    with a4:
        st.time_input(
            f"Start Time{_suggested_badge('start_time')}",
            key="start_time",
            on_change=_mark_override,
            args=("start_time",),
        )

    with a5:
        st.time_input(
            f"End Time{_suggested_badge('end_time')}",
            key="end_time",
            on_change=_mark_override,
            args=("end_time",),
        )

    st.divider()

    # -------- SECTION 4 — Algo Parameters (Dynamic) --------
    st.subheader("🟦 Algo Parameters (Dynamic)")

    # Shared parameters row
    p_shared1, p_shared2 = st.columns([1.2, 1.2], gap="small")
    with p_shared1:
        st.selectbox(
            f"Aggression Level{_suggested_badge('aggression_level')}",
            options=AGGRESSION_LEVELS,
            key="aggression_level",
            on_change=_mark_override,
            args=("aggression_level",),
        )
    with p_shared2:
        # UX: required in spec; backend already returns urgency_level in context flags
        st.selectbox(
            "Urgency (UI)",
            options=["Auto", "Low", "Medium", "High"],
            key="urgency_ui",
            on_change=_mark_override,
            args=("urgency_ui",),
            help="UI-only. Backend urgency is shown in the explainability panel context flags.",
        )

    chosen_algo_ui = st.session_state.get("algo_type", "VWAP")

    if chosen_algo_ui == "VWAP":
        v1, v2 = st.columns([1.2, 1.2], gap="small")
        with v1:
            st.selectbox(
                f"Volume Curve{_suggested_badge('vwap_volume_curve')}",
                options=VWAP_CURVES,
                key="vwap_volume_curve",
                on_change=_mark_override,
                args=("vwap_volume_curve",),
            )
        with v2:
            st.number_input(
                f"Max % of Volume{_suggested_badge('vwap_max_volume_pct')}",
                min_value=0.0,
                max_value=100.0,
                step=1.0,
                key="vwap_max_volume_pct",
                on_change=_mark_override,
                args=("vwap_max_volume_pct",),
            )

    elif chosen_algo_ui == "POV":
        p1, p2, p3 = st.columns([1.2, 1.2, 1.2], gap="small")
        with p1:
            st.number_input(
                f"Target Participation %{_suggested_badge('pov_participation_rate')}",
                min_value=0.0,
                max_value=1.0,
                step=0.01,
                format="%.2f",
                key="pov_participation_rate",
                on_change=_mark_override,
                args=("pov_participation_rate",),
                help="Expressed as 0.00–1.00 (e.g. 0.10 = 10%).",
            )
        with p2:
            st.number_input(
                f"Min Clip Qty{_suggested_badge('pov_min_clip')}",
                min_value=0,
                step=100,
                key="pov_min_clip",
                on_change=_mark_override,
                args=("pov_min_clip",),
            )
        with p3:
            st.number_input(
                f"Max Clip Qty{_suggested_badge('pov_max_clip')}",
                min_value=0,
                step=100,
                key="pov_max_clip",
                on_change=_mark_override,
                args=("pov_max_clip",),
            )

    elif chosen_algo_ui == "ICEBERG":
        i1, _i2 = st.columns([1.2, 2.4], gap="small")
        with i1:
            st.number_input(
                f"Display Quantity{_suggested_badge('iceberg_display_quantity')}",
                min_value=0,
                step=100,
                key="iceberg_display_quantity",
                on_change=_mark_override,
                args=("iceberg_display_quantity",),
                help="Suggested display size for ICEBERG (still trader-editable).",
            )
        with _i2:
            st.caption(
                "Tip: ICEBERG Display Quantity is separate from the optional top-level Display Qty field."
            )

    st.divider()

    # Optional: show a compact “final ticket” payload preview for debugging (read-only)
    with st.expander("Preview: Current Ticket Values (read-only)", expanded=False):
        preview = {
            "request_payload": {
                "client_id": st.session_state["client_id"],
                "symbol": st.session_state["symbol"],
                "order_size": int(st.session_state["order_size"]),
                "direction": st.session_state["direction"],
                "time_to_close": int(st.session_state["time_to_close"]),
                "notes": st.session_state.get("notes", "") or "",
            },
            "ticket_fields": {
                "order_type": st.session_state.get("order_type"),
                "limit_price": st.session_state.get("limit_price"),
                "time_in_force": st.session_state.get("time_in_force"),
                "algo_type": st.session_state.get("algo_type"),
                "hold": st.session_state.get("hold"),
                "start_time": _time_to_hhmm(st.session_state.get("start_time")),
                "end_time": _time_to_hhmm(st.session_state.get("end_time")),
            },
            "algo_params_ui": {
                "aggression_level": st.session_state.get("aggression_level"),
                "urgency_ui": st.session_state.get("urgency_ui"),
                "vwap": {
                    "volume_curve": st.session_state.get("vwap_volume_curve"),
                    "max_volume_pct": st.session_state.get("vwap_max_volume_pct"),
                },
                "pov": {
                    "participation_rate": st.session_state.get("pov_participation_rate"),
                    "min_clip": st.session_state.get("pov_min_clip"),
                    "max_clip": st.session_state.get("pov_max_clip"),
                },
                "iceberg": {
                    "display_quantity": st.session_state.get("iceberg_display_quantity"),
                },
            },
        }
        st.json(preview)


with explain_col:
    # -------- SECTION 5 — Explainability Panel (Right / Below) --------
    st.subheader("🟦 Explainability")
    st.caption("Read-only: why SmartOrder AI suggested these parameters.")

    explanations: List[str] = st.session_state.get("explanations", []) or []
    if explanations:
        for e in explanations:
            st.markdown(f"- {e}")
    else:
        st.info("No explanations yet. Click “Generate Smart Prefill”.")

    st.divider()

    with st.expander("Context Flags (debug)", expanded=False):
        st.json(st.session_state.get("context_flags", {}) or {})

    with st.expander("AI Suggested Values (debug)", expanded=False):
        st.json(st.session_state.get("suggested", {}) or {})

    with st.expander("Trader Overrides (debug)", expanded=False):
        st.json(st.session_state.get("overrides", {}) or {})

