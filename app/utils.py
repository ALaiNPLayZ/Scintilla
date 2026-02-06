"""
SmartOrder AI - Shared utilities (paths, constants, helpers).
"""

import os
from pathlib import Path

# Project root: parent of 'app'
APP_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = APP_DIR.parent
DATA_DIR = PROJECT_ROOT / "data"

# CSV file names
CLIENTS_CSV = "clients.csv"
INSTRUMENTS_CSV = "instruments.csv"
HISTORICAL_ORDERS_CSV = "historical_orders.csv"
MARKET_SNAPSHOT_CSV = "market_snapshot.csv"


def get_data_path(filename: str) -> Path:
    """Return full path to a file in data/."""
    return DATA_DIR / filename


def ensure_data_dir() -> None:
    """Ensure data directory exists (for robustness)."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
