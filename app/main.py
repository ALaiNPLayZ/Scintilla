"""
SmartOrder AI - FastAPI application and /recommend pipeline.
Intelligent Order Parameter Prefill Engine: builds full order ticket from context + rules + patterns + scoring.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .models import OrderRequest, RecommendationResponse, CoreOrderFields, AlgoParameters, ContextFlags
from .data_loader import load_all_data, get_historical_data
from .context_builder import build_context
from .rule_engine import apply_rules, RULE_ALGO, RULE_AGGRESSION, RULE_ORDER_TYPE, RULE_REASONS
from .pattern_engine import match_historical
from .scoring_engine import score_algos
from .parameter_engine import build_core_fields, build_algo_parameters
from .explain_engine import build_explanations


app = FastAPI(
    title="SmartOrder AI",
    description="Intelligent Order Parameter Prefill Engine – mock backend for hackathon",
    version="0.1.0",
)

# Allow Streamlit or other frontends to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def run_recommend_pipeline(request: OrderRequest) -> RecommendationResponse:
    """
    Full pipeline:
    1. Load data
    2. Build context
    3. Rule engine -> partial overrides
    4. Pattern engine -> historical algo/aggression
    5. Scoring engine -> final algo
    6. Parameter engine -> core fields + algo parameters
    7. Explain engine -> explanations
    8. Build ContextFlags and return response
    """
    # 1. Load all mock data
    data = load_all_data()

    # 2. Build context (size_vs_adv, urgency, notes_flags, profiles, market)
    context = build_context(request, data)

    # 3. Hard rules (can force algo, aggression, order_type)
    rule_result = apply_rules(context)
    rule_algo = rule_result.get(RULE_ALGO)
    rule_aggression = rule_result.get(RULE_AGGRESSION)
    rule_order_type = rule_result.get(RULE_ORDER_TYPE)
    rule_reasons = rule_result.get(RULE_REASONS, [])

    # 4. Pattern: historical match for algo + aggression
    pattern_algo, pattern_aggression, pattern_reasons = match_historical(
        request.client_id,
        request.symbol,
        context["size_vs_adv"],
        context["volatility_bucket"],
        data,
    )

    # 5. Scoring: choose final algo (rules override, then pattern tie-break, then scores)
    chosen_algo = score_algos(context, rule_algo=rule_algo, pattern_algo=pattern_algo)

    # 6. Core fields and algo parameters
    core_fields = build_core_fields(context, chosen_algo, rule_order_type=rule_order_type)
    algo_params = build_algo_parameters(
        context,
        chosen_algo,
        rule_aggression=rule_aggression,
        pattern_aggression=pattern_aggression,
    )

    # 7. Explanations
    explanations = build_explanations(context, rule_reasons, pattern_reasons, chosen_algo)

    # 8. Context flags for response transparency
    context_flags = ContextFlags(
        urgency_level=context["urgency_level"],
        size_vs_adv=round(context["size_vs_adv"], 2),
        volatility_bucket=context["volatility_bucket"],
        liquidity_bucket=context["liquidity_bucket"],
        spread=context["spread"],
    )

    return RecommendationResponse(
        core_order_fields=core_fields,
        algo_parameters=algo_params,
        context_flags=context_flags,
        explanations=explanations,
    )


@app.post("/recommend", response_model=RecommendationResponse)
def recommend(request: OrderRequest):
    """
    POST /recommend: prefill full order ticket from client, symbol, size, direction, time_to_close, notes.
    Returns core_order_fields, algo_parameters, context_flags, and explanations.
    """
    try:
        return run_recommend_pipeline(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
def health():
    """Health check for deployment."""
    return {"status": "ok", "service": "SmartOrder AI"}
