# utils/categorization.py
from __future__ import annotations

from typing import Dict, Optional

import pandas as pd

from rapidfuzz import process, fuzz
from .cleaning import normalize_merchant


def fuzzy_match_category(
    merchant_clean: str,
    ynab_payees: list[str],
    mapping: Dict[str, str],
    threshold: int,
) -> Optional[str]:
    """
    Returns a YNAB-derived category if fuzzy match meets threshold.
    merchant_clean is expected to already be normalized (see normalize_merchant).
    """
    if not ynab_payees:
        return None

    match, score, _ = process.extractOne(
        merchant_clean,
        ynab_payees,
        scorer=fuzz.partial_ratio,
    )

    if score >= threshold:
        return mapping.get(match)

    return None


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


def apply_rule_based_categories(
    df: pd.DataFrame,
    overrides: Dict[str, str],
    ynab_fuzzy: Optional[Dict] = None,
) -> pd.DataFrame:
    """
    Apply categories in this order:
    1. Manual merchant overrides (from JSON / UI)
    2. Fuzzy-matched YNAB payee categories (if ynab_fuzzy dict is provided)
    3. Simple keyword-based rules
    Returns a new DataFrame with 'Category' column.
    """
    df = df.copy()

    if "Category" not in df.columns:
        df["Category"] = None

    ynab_payees = []
    ynab_mapping: Dict[str, str] = {}
    ynab_threshold = 80

    if ynab_fuzzy:
        ynab_payees = ynab_fuzzy.get("ynab_payees", []) or []
        ynab_mapping = ynab_fuzzy.get("payee_to_category", {}) or {}
        ynab_threshold = int(ynab_fuzzy.get("threshold", 80))

    for idx, row in df.iterrows():
        merchant = (row.get("MerchantClean", "") or "").strip()
        tx_type = row.get("Transaction type", "") or ""
        net = float(row.get("Net", 0.0))

        # 1) Manual overrides take priority
        if merchant in overrides:
            df.at[idx, "Category"] = overrides[merchant]
            continue

        # 2) Fuzzy YNAB mapping if available
        if ynab_payees and merchant:
            ynab_cat = fuzzy_match_category(
                merchant,
                ynab_payees,
                ynab_mapping,
                ynab_threshold,
            )
            if ynab_cat:
                df.at[idx, "Category"] = ynab_cat
                continue

        # 3) Keyword-based fallback
        df.at[idx, "Category"] = _keyword_category(merchant, tx_type, net)

    return df