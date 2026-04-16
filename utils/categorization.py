# utils/categorization.py
from __future__ import annotations
from typing import Dict, Optional
import pandas as pd
from rapidfuzz import process, fuzz

from payee_normalizer import normalize_payee


def fuzzy_match_category(
    merchant_clean: str,
    ynab_payees: list[str],
    mapping: Dict[str, str],
    threshold: int,
) -> Optional[str]:
    if not ynab_payees or not merchant_clean:
        return None

    merchant_clean = merchant_clean.lower()
    ynab_payees_norm = [p.lower() for p in ynab_payees]

    match, score, _ = process.extractOne(
        merchant_clean,
        ynab_payees_norm,
        scorer=fuzz.partial_ratio,
    )

    if score >= threshold:
        return mapping.get(match)

    return None


def _keyword_category(merchant: str, tx_type: str, net: float) -> str:
    m = merchant.lower()
    t = (tx_type or "").lower()

    if net > 0 or "credit" in t:
        return "Income"

    if any(k in m for k in ["sainsbury", "tesco", "asda", "aldi", "lidl", "morrisons"]):
        return "Groceries"

    if any(k in m for k in ["restaurant", "coffee", "cafe", "starbucks", "kfc", "mcdonald"]):
        return "Eating Out"

    if any(k in m for k in ["uber", "bolt", "bus", "rail", "train", "fuel", "petrol"]):
        return "Transport"

    if any(k in m for k in ["netflix", "prime", "spotify", "disney", "icloud"]):
        return "Subscriptions"

    if any(k in m for k in ["vodafone", "o2", "ee", "bt ", "water", "gas"]):
        return "Bills & Utilities"

    if "amazon" in m:
        return "Shopping"

    return "Other"


def apply_rule_based_categories(
    df: pd.DataFrame,
    overrides: Dict[str, str],
    ynab_fuzzy: Optional[Dict] = None,
) -> pd.DataFrame:
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
        merchant_raw = (row.get("MerchantClean") or "").strip()
        merchant_clean = normalize_payee(merchant_raw)

        tx_type = row.get("Transaction type", "")
        net = float(row.get("Net", 0))

        # 1️⃣ Manual override
        if merchant_clean in overrides:
            df.at[idx, "Category"] = overrides[merchant_clean]
            continue

        # 2️⃣ YNAB fuzzy mapping
        if ynab_payees and merchant_clean:
            matched = fuzzy_match_category(
                merchant_clean,
                ynab_payees,
                ynab_mapping,
                ynab_threshold,
            )
            if matched:
                df.at[idx, "Category"] = matched
                continue

        # 3️⃣ Keyword fallback
        df.at[idx, "Category"] = _keyword_category(merchant_clean, tx_type, net)

    return df