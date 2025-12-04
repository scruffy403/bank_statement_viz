# utils/ynab_api.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import List, Dict

import requests
import pandas as pd

from .category_mapping import map_ynab_category_to_dashboard

from rapidfuzz import process, fuzz
from .cleaning import normalize_merchant


YNAB_BASE_URL = "https://api.youneedabudget.com/v1"


@dataclass
class YNABClient:
    token: str

    def _headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}

    def list_budgets(self) -> List[Dict]:
        resp = requests.get(f"{YNAB_BASE_URL}/budgets", headers=self._headers(), timeout=15)
        resp.raise_for_status()
        return resp.json()["data"]["budgets"]

    def get_categories(self, budget_id: str) -> List[Dict]:
        resp = requests.get(
            f"{YNAB_BASE_URL}/budgets/{budget_id}/categories",
            headers=self._headers(),
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()["data"]["category_groups"]

    def get_current_month_categories(self, budget_id: str) -> List[Dict]:
        resp = requests.get(
            f"{YNAB_BASE_URL}/budgets/{budget_id}/months/current",
            headers=self._headers(),
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()["data"]["month"]["categories"]

    def get_payees(self, budget_id: str) -> List[Dict]:
        resp = requests.get(
            f"{YNAB_BASE_URL}/budgets/{budget_id}/payees",
            headers=self._headers(),
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()["data"]["payees"]

    def get_transactions_since(self, budget_id: str, since_date: str) -> List[Dict]:
        resp = requests.get(
            f"{YNAB_BASE_URL}/budgets/{budget_id}/transactions",
            headers=self._headers(),
            params={"since_date": since_date},
            timeout=20,
        )
        resp.raise_for_status()
        return resp.json()["data"]["transactions"]


def list_budgets(token: str) -> List[Dict]:
    client = YNABClient(token=token)
    return client.list_budgets()


def _milli_to_units(amount_milli: int) -> float:
    return amount_milli / 1000.0


def fetch_current_month_category_budgets(token: str, budget_id: str) -> pd.DataFrame:
    client = YNABClient(token=token)

    groups = client.get_categories(budget_id)
    id_to_group = {}
    id_to_name = {}

    for g in groups:
        gname = g["name"]
        for c in g["categories"]:
            cid = c["id"]
            id_to_group[cid] = gname
            id_to_name[cid] = c["name"]

    month_cats = client.get_current_month_categories(budget_id)

    rows = []
    for c in month_cats:
        cid = c["id"]
        cname = id_to_name.get(cid, c["name"])
        gname = id_to_group.get(cid, "")

        rows.append({
            "category_id": cid,
            "category_name": cname,
            "group_name": gname,
            "budgeted": _milli_to_units(c.get("budgeted", 0)),
            "activity": _milli_to_units(c.get("activity", 0)),
            "balance": _milli_to_units(c.get("balance", 0)),
            "dashboard_category": map_ynab_category_to_dashboard(cname),
        })

    return pd.DataFrame(rows)


def build_payee_category_overrides(
    token: str,
    budget_id: str,
    days_back: int = 90,
    threshold: int = 80,
):
    """
    Create a mapping:
        normalized_merchant → dashboard_category
    using fuzzy matching between bank merchant names and YNAB payee names.

    threshold: fuzzy match % required to accept a match (0–100)
    """
    client = YNABClient(token=token)

    # Get YNAB transactions
    since_date = (date.today() - timedelta(days_back)).isoformat()
    ynab_transactions = client.get_transactions_since(budget_id, since_date)

    # Get YNAB category ID → name map
    cat_groups = client.get_categories(budget_id)
    cat_id_to_name = {}
    for g in cat_groups:
        for cat in g["categories"]:
            cat_id_to_name[cat["id"]] = cat["name"]

    # Build normalized payee list + categories
    ynab_payees = []
    payee_to_category = {}

    for tx in ynab_transactions:
        payee = tx.get("payee_name") or ""
        cat_id = tx.get("category_id")

        if not payee or not cat_id:
            continue

        cat_name = cat_id_to_name.get(cat_id, None)
        if not cat_name:
            continue

        dash_cat = map_ynab_category_to_dashboard(cat_name)

        clean_payee = normalize_merchant(payee)

        ynab_payees.append(clean_payee)
        payee_to_category[clean_payee] = dash_cat

    # Remove duplicates
    ynab_payees = list(set(ynab_payees))

    # Returns a dict we will later merge with rule-based categories
    return {
        "ynab_payees": ynab_payees,
        "payee_to_category": payee_to_category,
        "threshold": threshold,
    }


def fetch_all_ynab_categories(token: str, budget_id: str) -> list[str]:
    """
    Returns a flat list of ALL category names inside the chosen YNAB budget.
    Subcategories only (the actual actionable categories).
    """
    client = YNABClient(token=token)
    groups = client.get_categories(budget_id)

    categories = []

    for g in groups:
        for cat in g.get("categories", []):
            name = cat.get("name")
            # Skip internal categories like "Category Group" or "Uncategorized"
            if name and not cat.get("hidden", False):
                categories.append(name)

    return sorted(categories)