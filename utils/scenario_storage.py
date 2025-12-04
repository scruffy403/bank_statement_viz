# utils/scenario_storage.py
from __future__ import annotations

from pathlib import Path
from datetime import date
from typing import Dict, Any
import json

MODELS_DIR = Path("models")
SCENARIOS_PATH = MODELS_DIR / "forecast_scenarios.json"


def load_scenarios() -> Dict[str, dict]:
    """
    Load saved forecast scenarios from disk.

    Returns a mapping:
        scenario_name -> {
            "created_at": "YYYY-MM-DD",
            "days_ahead": int,
            "exclude_cats": [str, ...],
            "exclude_tx_ids": [int, ...],
        }

    Older files without these fields are auto-upgraded in-memory.
    """
    if not SCENARIOS_PATH.exists():
        return {}

    try:
        with open(SCENARIOS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return {}

    if not isinstance(data, dict):
        return {}

    today_str = date.today().isoformat()

    for name, s in list(data.items()):
        if not isinstance(s, dict):
            # Malformed entry – replace with minimal default
            data[name] = {
                "created_at": today_str,
                "days_ahead": 90,
                "exclude_cats": [],
                "exclude_tx_ids": [],
            }
            continue

        # created_at: prefer existing string, otherwise fallback
        created = s.get("created_at") or s.get("created")
        if isinstance(created, str):
            s["created_at"] = created
        else:
            s["created_at"] = today_str

        # days_ahead
        if not isinstance(s.get("days_ahead"), int):
            s["days_ahead"] = 90

        # exclude_cats
        ec = s.get("exclude_cats")
        if not isinstance(ec, list):
            s["exclude_cats"] = []
        else:
            # ensure all are strings
            s["exclude_cats"] = [str(x) for x in ec]

        # exclude_tx_ids
        et = s.get("exclude_tx_ids")
        if not isinstance(et, list):
            s["exclude_tx_ids"] = []
        else:
            # ensure ints (indices)
            s["exclude_tx_ids"] = [int(x) for x in et]

        # clean legacy key
        s.pop("created", None)

    return data


def save_scenarios(scenarios: Dict[str, dict]) -> None:
    """
    Save scenarios in a JSON-serializable format.
    """
    MODELS_DIR.mkdir(exist_ok=True)

    today_str = date.today().isoformat()
    serializable: Dict[str, Any] = {}

    for name, s in scenarios.items():
        if not isinstance(s, dict):
            continue

        s = dict(s)  # shallow copy

        created = s.get("created_at") or s.get("created")
        if not isinstance(created, str):
            created = today_str

        s["created_at"] = created
        s.pop("created", None)

        # Normalise lists
        ec = s.get("exclude_cats", [])
        if not isinstance(ec, list):
            ec = list(ec) if ec is not None else []
        s["exclude_cats"] = [str(x) for x in ec]

        et = s.get("exclude_tx_ids", [])
        if not isinstance(et, list):
            et = list(et) if et is not None else []
        s["exclude_tx_ids"] = [int(x) for x in et]

        # days_ahead
        if not isinstance(s.get("days_ahead"), int):
            s["days_ahead"] = 90

        serializable[name] = s

    with open(SCENARIOS_PATH, "w", encoding="utf-8") as f:
        json.dump(serializable, f, indent=2, ensure_ascii=False)