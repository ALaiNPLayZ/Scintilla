# SmartOrder AI – Intelligent Order Parameter Prefill Engine

Hackathon prototype backend that simulates an AI assistant to **prefill a full trading order ticket** using:

- Client behavior
- Instrument characteristics
- Market conditions
- Historical execution patterns

**Mock data only.** No external integrations. REST API ready to connect to a Streamlit UI.

## Tech stack

- **Language:** Python 3.10+
- **Backend:** FastAPI + Pydantic
- **Frontend:** Streamlit
- **Data:** Pandas + local CSV files (no database)

## Setup (recommended with virtualenv)

From the `smartorder_ai/` directory:

```bash
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt   # Windows
```

> You can also use `python3` / `source .venv/bin/activate` on macOS/Linux.

## Run the backend API

From the `smartorder_ai/` directory:

```bash
.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8001
```

API base URL (used by the Streamlit UI): **http://127.0.0.1:8001**

- **POST `/recommend`** – send order request, get prefilled ticket + explanations  
- **GET `/health`** – health check  
- **GET `/docs`** – Swagger UI

## Run the Streamlit frontend

In a second terminal, from `smartorder_ai/`:

```bash
.venv\Scripts\python -m streamlit run streamlit_app.py
```

Then open the URL printed in the console (typically `http://localhost:8501`).

## Example request

```bash
curl -X POST "http://127.0.0.1:8001/recommend" \
  -H "Content-Type: application/json" \
  -d '{"client_id":"CLT001","symbol":"AAPL","order_size":15000000,"direction":"Buy","time_to_close":120,"notes":"VWAP benchmark"}'
```

## Example response

```json
{
  "core_order_fields": {
    "order_type": "Limit",
    "limit_price": 152.24,
    "direction": "Buy",
    "time_in_force": "DAY",
    "start_time": "09:45",
    "end_time": "14:30",
    "algo_type": "VWAP"
  },
  "algo_parameters": {
    "participation_rate": null,
    "min_clip_size": null,
    "max_clip_size": null,
    "volume_curve": "Historical",
    "max_volume_pct": 15,
    "display_quantity": null,
    "aggression_level": "Medium"
  },
  "context_flags": {
    "urgency_level": "Medium",
    "size_vs_adv": 0.18,
    "volatility_bucket": "Low",
    "liquidity_bucket": "High",
    "spread": 0.05
  },
  "explanations": [
    "Order size is 18% of ADV",
    "Low volatility favors VWAP strategy",
    "Notes specify VWAP; algo set to VWAP"
  ]
}
```

## Project layout

```
smartorder_ai/
├── app/
│   ├── main.py          # FastAPI app + /recommend pipeline
│   ├── models.py        # Pydantic request/response models
│   ├── data_loader.py   # Load CSVs, get client/instrument/market/history
│   ├── context_builder.py  # Build context (size_vs_adv, urgency, notes flags)
│   ├── rule_engine.py   # Hard rules (VWAP from notes, EOD → POV, etc.)
│   ├── pattern_engine.py   # Match history → preferred algo/aggression
│   ├── scoring_engine.py   # Score VWAP/POV/ICEBERG → choose algo
│   ├── parameter_engine.py # Core fields + algo parameters
│   ├── explain_engine.py   # Human-readable explanations
│   └── utils.py         # Paths, constants
├── data/
│   ├── clients.csv
│   ├── instruments.csv
│   ├── historical_orders.csv
│   └── market_snapshot.csv
├── streamlit_app.py     # Streamlit OMS-style order ticket UI
├── requirements.txt
└── README.md
```

## Pipeline summary

1. **Load data** – clients, instruments, market snapshot, historical orders (CSV).
2. **Context** – size vs ADV, volatility/liquidity buckets, urgency from `time_to_close`, notes flags (vwap, urgent, close, benchmark).
3. **Rules** – e.g. notes say VWAP → algo VWAP; time_to_close &lt; 15 → aggression High; order &gt; 25% ADV → Limit; EOD urgency → prefer POV.
4. **Patterns** – match history by client + size bucket + volatility → most frequent algo and aggression.
5. **Scoring** – score VWAP, POV, ICEBERG from context; apply rule overrides and pattern tie-break.
6. **Parameters** – core order fields (type, limit, times, TIF, algo) and algo-specific params (POV/VWAP/ICEBERG).
7. **Explain** – collect reasons from rules, scoring, and history into `explanations`.

This is a **modular AI decision-support system** that pre-fills order tickets and exposes:

- A **FastAPI backend** (`/recommend`) for programmatic access.
- A **Streamlit frontend** (`streamlit_app.py`) that looks and behaves like a professional OMS/EMS ticket, with AI-prefilled but fully overridable fields and an explainability panel.
