"""
SmartOrder AI - Pydantic models for request/response and internal structures.
All types used by the REST API and the prefill pipeline.
"""

from typing import Optional, List
from pydantic import BaseModel, Field


# -----------------------------------------------------------------------------
# Request model (incoming from Streamlit or API client)
# -----------------------------------------------------------------------------


class OrderRequest(BaseModel):
    """Incoming order request: client, symbol, size, direction, and timing."""

    client_id: str = Field(..., description="Client identifier")
    symbol: str = Field(..., description="Instrument symbol")
    order_size: int = Field(..., gt=0, description="Order quantity (shares)")
    direction: str = Field(..., description="Buy or Sell")
    time_to_close: int = Field(..., ge=0, description="Minutes until market close (or target end)")
    notes: Optional[str] = Field(None, description="Free-text notes (e.g. VWAP, urgent, benchmark)")


# -----------------------------------------------------------------------------
# Response models: core order fields and algo parameters
# -----------------------------------------------------------------------------


class CoreOrderFields(BaseModel):
    """Prefilled core order ticket fields."""

    order_type: str = Field(..., description="Market or Limit")
    limit_price: Optional[float] = Field(None, description="Limit price if order_type=Limit")
    direction: str = Field(..., description="Buy or Sell")
    time_in_force: str = Field(..., description="DAY, IOC, etc.")
    start_time: str = Field(..., description="Start time for algo (e.g. 09:45)")
    end_time: str = Field(..., description="End time for algo (e.g. 14:30)")
    algo_type: str = Field(..., description="VWAP, POV, ICEBERG, etc.")


class AlgoParameters(BaseModel):
    """Algorithm-specific parameters (POV, VWAP, ICEBERG)."""

    participation_rate: Optional[float] = Field(None, description="POV participation rate (0–1)")
    min_clip_size: Optional[int] = Field(None, description="POV min clip size")
    max_clip_size: Optional[int] = Field(None, description="POV max clip size")
    volume_curve: Optional[str] = Field(None, description="VWAP: Historical, Front-loaded, etc.")
    max_volume_pct: Optional[float] = Field(None, description="VWAP max volume %")
    display_quantity: Optional[int] = Field(None, description="ICEBERG display size")
    aggression_level: str = Field(..., description="Low, Medium, High")


class ContextFlags(BaseModel):
    """Context used for the recommendation (for transparency)."""

    urgency_level: str = Field(..., description="Low, Medium, High")
    size_vs_adv: float = Field(..., description="Order size / ADV ratio")
    volatility_bucket: str = Field(..., description="Low, Medium, High")
    liquidity_bucket: str = Field(..., description="Low, Medium, High")
    spread: float = Field(..., description="Current bid-ask spread")
    intraday_vol: Optional[float] = Field(
        None, description="Numeric intraday volatility used for market-aware decisions"
    )
    avg_trade_size: Optional[float] = Field(
        None, description="Average trade size proxy from synthetic market data"
    )
    liquidity_score: Optional[float] = Field(
        None, description="Synthetic liquidity proxy combining ADV, spread, and trade size"
    )
    time_to_close_request: Optional[int] = Field(
        None, description="Minutes to close supplied in the order request"
    )
    time_to_close_system: Optional[int] = Field(
        None, description="Minutes to close derived from the system clock"
    )
    effective_time_to_close: Optional[int] = Field(
        None, description="Effective time to close used in decision logic (min of request/system)"
    )
    fat_finger_flag: Optional[bool] = Field(
        None, description="True if order size breaches historical size tolerance heuristic"
    )


class RecommendationResponse(BaseModel):
    """Full API response: prefilled ticket + context + explanations."""

    core_order_fields: CoreOrderFields
    algo_parameters: AlgoParameters
    context_flags: ContextFlags
    explanations: List[str] = Field(default_factory=list, description="Human-readable reasons")
