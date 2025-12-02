# utils/category_mapping.py
from __future__ import annotations

from typing import Dict

YNAB_TO_DASHBOARD: Dict[str, str] = {
    # Groceries / essentials
    "groceries": "Groceries",
    "supermarket": "Groceries",

    # Eating out
    "restaurants": "Eating Out",
    "eating out": "Eating Out",
    "takeaway": "Eating Out",
    "fast food": "Eating Out",
    "coffee": "Eating Out",

    # Transport
    "fuel": "Transport",
    "petrol": "Transport",
    "diesel": "Transport",
    "transport": "Transport",
    "public transport": "Transport",
    "bus": "Transport",
    "train": "Transport",
    "taxi": "Transport",

    # Bills / utilities / housing
    "rent": "Bills & Utilities",
    "mortgage": "Bills & Utilities",
    "council tax": "Bills & Utilities",
    "electricity": "Bills & Utilities",
    "gas": "Bills & Utilities",
    "water": "Bills & Utilities",
    "internet": "Bills & Utilities",
    "mobile phone": "Bills & Utilities",
    "tv licence": "Bills & Utilities",
    "broadband": "Bills & Utilities",

    # Subscriptions / digital
    "subscriptions": "Subscriptions",
    "netflix": "Subscriptions",
    "spotify": "Subscriptions",
    "prime": "Subscriptions",
    "amazon prime": "Subscriptions",
    "icloud": "Subscriptions",
    "apple services": "Subscriptions",
    "microsoft 365": "Subscriptions",
    "adobe": "Subscriptions",

    # Entertainment / QoL
    "entertainment": "Entertainment",
    "hobbies": "Entertainment",
    "gaming": "Entertainment",
    "games": "Entertainment",
    "cinema": "Entertainment",

    # Health / fitness
    "health": "Health & Fitness",
    "medical": "Health & Fitness",
    "pharmacy": "Health & Fitness",
    "gym": "Health & Fitness",
    "fitness": "Health & Fitness",

    # Shopping / general
    "shopping": "Shopping",
    "clothing": "Clothing",
    "amazon": "Shopping",

    # Income
    "salary": "Income",
    "wages": "Income",
    "pay": "Income",
    "dividends": "Income",
    "interest": "Income",
}

DEFAULT_DASHBOARD_CATEGORY = "Other"


def map_ynab_category_to_dashboard(ynab_name: str) -> str:
    if not ynab_name:
        return DEFAULT_DASHBOARD_CATEGORY

    key = ynab_name.strip().lower()
    if key in YNAB_TO_DASHBOARD:
        return YNAB_TO_DASHBOARD[key]

    for pattern, dash_cat in YNAB_TO_DASHBOARD.items():
        if pattern in key:
            return dash_cat

    return DEFAULT_DASHBOARD_CATEGORY