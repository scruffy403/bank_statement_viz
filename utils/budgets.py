# utils/budgets.py
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict

import pandas as pd


MODELS_DIR = Path("models")
BUDGETS_PATH = MODELS_DIR / "budgets.json"


def load_budgets() -> Dict[str, float]:
    MODELS_DIR.mkdir(exist_ok=True)
    if not BUDGETS_PATH.exists():
        return {}
    try:
        with open(BUDGETS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {k: float(v) for k, v in data.items()}
    except Exception:
        return {}


def save_budgets(budgets: Dict[str, float]) -> None:
    MODELS_DIR.mkdir(exist_ok=True)
    with open(BUDGETS_PATH, "w", encoding="utf-8") as f:
        json.dump(budgets, f, indent=2)


def compute_budget_vs_actual(expense_df: pd.DataFrame, budgets: Dict[str, float]) -> pd.DataFrame:
    if expense_df.empty or "Category" not in expense_df.columns:
        return pd.DataFrame()

    actual = (
        expense_df.groupby("Category")["Paid out"]
        .sum()
        .reset_index()
        .rename(columns={"Paid out": "Actual"})
    )

    actual["Budget"] = actual["Category"].map(budgets).fillna(0.0)
    actual["Delta"] = actual["Budget"] - actual["Actual"]

    return actual.sort_values("Category")