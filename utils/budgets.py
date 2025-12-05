# utils/budgets.py
from __future__ import annotations

from pathlib import Path
from typing import Dict, Any

import json
from datetime import datetime

import pandas as pd

BUDGET_HISTORY_PATH = Path("models/budgets_history.json")


def _empty_history() -> Dict[str, Any]:
    return {
        "categories": {},
        "metadata": {
            "last_updated": None,
        },
    }


def load_budget_history() -> Dict[str, Any]:
    """
    Load the budget history JSON from disk, or return a default structure.
    """
    if not BUDGET_HISTORY_PATH.exists():
        return _empty_history()

    try:
        with open(BUDGET_HISTORY_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return _empty_history()

    # Ensure required keys
    if "categories" not in data:
        data["categories"] = {}
    if "metadata" not in data:
        data["metadata"] = {"last_updated": None}

    return data


def save_budget_history(history: Dict[str, Any]) -> None:
    """
    Save the budget history JSON to disk.
    """
    BUDGET_HISTORY_PATH.parent.mkdir(exist_ok=True)
    history.setdefault("metadata", {})
    history["metadata"]["last_updated"] = datetime.utcnow().isoformat()

    with open(BUDGET_HISTORY_PATH, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)


def _get_or_create_category(history: Dict[str, Any], category: str, default_mode: str = "manual") -> Dict[str, Any]:
    cats = history.setdefault("categories", {})
    if category not in cats:
        cats[category] = {
            "mode": default_mode,
            "amount": 0.0,  # monthly budget amount
        }
    return cats[category]


def update_history_from_ynab(
    history: Dict[str, Any],
    ynab_df: pd.DataFrame,
    year_month: str,
) -> Dict[str, Any]:
    """
    Merge current-month YNAB category budgets into our budget history.

    For each YNAB row:
      - 'dashboard_category' is used as our dashboard category name
      - 'budgeted' is the monthly budget amount for that month

    For Option D, we treat YNAB as a convenient way to populate "amount"
    for categories whose mode is 'ynab' or which have no configuration yet.
    """
    history = history.copy()
    cats = history.setdefault("categories", {})

    if ynab_df.empty:
        return history

    for _, row in ynab_df.iterrows():
        dash_cat = row.get("dashboard_category")
        if not dash_cat:
            continue

        budgeted = float(row.get("budgeted") or 0.0)

        cfg = _get_or_create_category(history, dash_cat, default_mode="ynab")

        # If category is explicitly 'manual' or 'stable', we respect the user's mode
        # and only update amount if it is currently zero.
        mode = cfg.get("mode", "manual")
        if mode == "ynab" or (mode in {"manual", "stable"} and float(cfg.get("amount") or 0.0) == 0.0):
            cfg["amount"] = budgeted

    return history


def compute_budget_vs_actual(
    expense_df: pd.DataFrame,
    history: Dict[str, Any],
) -> pd.DataFrame:
    """
    Compute Budget vs Actual for each category over the period covered by expense_df.

    - expense_df: filtered expense data (Paid out > 0), with 'Date' and 'Category'.
    - history: budget history JSON loaded via load_budget_history().

    For now, each category has a SINGLE monthly 'amount' applied across
    the number of months in the current filtered window.

    Returns a DataFrame with columns:
        Category, Actual, Budget, Delta, PercentOver
    """
    if expense_df.empty:
        return pd.DataFrame(columns=["Category", "Actual", "Budget", "Delta", "PercentOver"])

    df = expense_df.copy()
    if "Date" not in df.columns:
        raise ValueError("compute_budget_vs_actual expects a 'Date' column in expense_df")

    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date"])

    # Determine the months in the current window
    periods = df["Date"].dt.to_period("M").unique()
    num_months = len(periods)
    if num_months == 0:
        return pd.DataFrame(columns=["Category", "Actual", "Budget", "Delta", "PercentOver"])

    cats_cfg = history.get("categories", {})

    records = []

    for cat in sorted(df["Category"].dropna().unique()):
        df_cat = df[df["Category"] == cat]
        actual = float(df_cat["Paid out"].sum())

        cfg = cats_cfg.get(cat, {"mode": "manual", "amount": 0.0})
        mode = cfg.get("mode", "manual")
        amount = float(cfg.get("amount") or 0.0)

        # For now, treat 'manual', 'stable' and 'ynab' as "amount per month"
        budget_total = amount * num_months

        delta = actual - budget_total
        percent_over = (delta / budget_total * 100.0) if budget_total > 0 else None

        records.append(
            {
                "Category": cat,
                "Actual": round(actual, 2),
                "Budget": round(budget_total, 2),
                "Delta": round(delta, 2),
                "PercentOver": round(percent_over, 1) if percent_over is not None else None,
                "Mode": mode,
            }
        )

    return pd.DataFrame(records)


# ------------------------------------------------------------------
# Backwards-compat wrappers (for older code that used simple dicts)
# ------------------------------------------------------------------

def load_budgets() -> Dict[str, Any]:
    """
    Backwards-compat shim. Returns the full history.
    """
    return load_budget_history()


def save_budgets(history: Dict[str, Any]) -> None:
    """
    Backwards-compat shim. Persists the full history.
    """
    save_budget_history(history)