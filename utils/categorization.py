# utils/categorization.py
from __future__ import annotations

from typing import Dict

import pandas as pd


def _keyword_category(merchant: str, tx_type: str, net: float) -> str:
    m = merchant.lower()
    t = (tx_type or "").lower()

    # Income first
    if net > 0 or "credit" in t:
        return "Income"

    # Groceries
    if any(k in m for k in ["sainsbury", "tesco", "asda", "aldi", "lidl", "morrisons", "co op"]):
        return "Groceries"

    # Eating out
    if any(k in m for k in ["restaurant", "coffee", "cafe", "starbucks", "mcdonald", "kfc", "burger king"]):
        return "Eating Out"

    # Transport
    if any(k in m for k in ["uber", "bolt", "tfl", "trainline", "rail", "bus", "petrol", "fuel", "shell", "esso"]):
        return "Transport"

    # Subscriptions / digital
    if any(k in m for k in ["netflix", "spotify", "disney", "prime", "icloud", "microsoft", "adobe"]):
        return "Subscriptions"

    # Bills & Utilities
    if any(k in m for k in ["bt ", "vodafone", "o2", "ee ", "talktalk", "thames water", "british gas"]):
        return "Bills & Utilities"

    # Shopping generic
    if any(k in m for k in ["amazon", "argos", "currys"]):
        return "Shopping"

    return "Other"


def apply_rule_based_categories(df: pd.DataFrame, overrides: Dict[str, str]) -> pd.DataFrame:
    """
    Apply rule-based categories first, then merchant overrides.
    Returns a new DataFrame with 'Category' column.
    """
    df = df.copy()

    if "Category" not in df.columns:
        df["Category"] = None

    for idx, row in df.iterrows():
        merchant = row.get("MerchantClean", "") or ""
        tx_type = row.get("Transaction type", "") or ""
        net = float(row.get("Net", 0.0))

        # Overrides first
        if merchant in overrides:
            df.at[idx, "Category"] = overrides[merchant]
        else:
            df.at[idx, "Category"] = _keyword_category(merchant, tx_type, net)

    return df