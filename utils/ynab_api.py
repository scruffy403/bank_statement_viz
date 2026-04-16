# utils/ynab_api.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import List, Dict, Any

import requests
import pandas as pd

from .category_mapping import map_ynab_category_to_dashboard
# from .cleaning import normalize_merchant
from payee_normalizer import normalize_payee

YNAB_BASE_URL = "https://api.youneedabudget.com/v1"


@dataclass
class YNABClient:
    token: str

    def _headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}

    # -----------------------------
    # Budgets
    # -----------------------------
    def list_budgets(self) -> List[Dict[str, Any]]:
        resp = requests.get(
            f"{YNAB_BASE_URL}/budgets",
            headers=self._headers(),
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json().get("data", {})
        return data.get("budgets", [])

    # -----------------------------
    # Categories
    # -----------------------------
    def get_categories(self, budget_id: str) -> List[Dict[str, Any]]:
        """
        Returns a list of category groups, each with 'categories'.
        """
        resp = requests.get(
            f"{YNAB_BASE_URL}/budgets/{budget_id}/categories",
            headers=self._headers(),
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json().get("data", {})
        return data.get("category_groups", [])

    def get_current_month_categories(self, budget_id: str) -> List[Dict[str, Any]]:
        """
        Returns the current month object, which contains categories with
        budget/activity/available in milliunits.
        """
        resp = requests.get(
            f"{YNAB_BASE_URL}/budgets/{budget_id}/months/current",
            headers=self._headers(),
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json().get("data", {})
        month = data.get("month", {})
        return month.get("categories", [])

    # -----------------------------
    # Payees & Transactions
    # -----------------------------
    def get_payees(self, budget_id: str) -> List[Dict[str, Any]]:
        resp = requests.get(
            f"{YNAB_BASE_URL}/budgets/{budget_id}/payees",
            headers=self._headers(),
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json().get("data", {})
        return data.get("payees", [])

    def get_transactions_since(self, budget_id: str, since_date: str) -> List[Dict[str, Any]]:
        """
        since_date: 'YYYY-MM-DD'
        """
        resp = requests.get(
            f"{YNAB_BASE_URL}/budgets/{budget_id}/transactions",
            headers=self._headers(),
            params={"since_date": since_date},
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json().get("data", {})
        return data.get("transactions", [])


# Convenience wrapper
def list_budgets(token: str) -> List[Dict[str, Any]]:
    client = YNABClient(token=token)
    return client.list_budgets()


def _milli_to_units(amount_milli: int) -> float:
    # YNAB amounts are in milliunits (e.g. 123450 = 123.45)
    return amount_milli / 1000.0


def fetch_current_month_category_budgets(token: str, budget_id: str) -> pd.DataFrame:
    """
    Returns a DataFrame with YNAB category budgets for the current month.

    Columns:
        - category_id
        - category_name
        - group_name
        - budgeted
        - activity
        - balance
        - dashboard_category
        - month (YYYY-MM)
    """
    client = YNABClient(token=token)

    # 1) Category groups → ID -> (group_name, category_name)
    groups = client.get_categories(budget_id)
    id_to_group: Dict[str, str] = {}
    id_to_name: Dict[str, str] = {}

    for g in groups:
        gname = g.get("name", "")
        for c in g.get("categories", []):
            cid = c.get("id")
            cname = c.get("name", "")
            if not cid:
                continue
            id_to_group[cid] = gname
            id_to_name[cid] = cname

    # 2) Current month categories with budget numbers
    month_cats = client.get_current_month_categories(budget_id)
    rows = []

    # We get the current month from one of the category entries if present
    # or fallback to today's year-month.
    current_month_str = None

    for c in month_cats:
        cid = c.get("id")
        if not cid:
            continue

        cname = id_to_name.get(cid, c.get("name", ""))
        gname = id_to_group.get(cid, "")

        budgeted = _milli_to_units(c.get("budgeted", 0))
        activity = _milli_to_units(c.get("activity", 0))
        balance = _milli_to_units(c.get("balance", 0))

        dash_cat = map_ynab_category_to_dashboard(cname)

        month = c.get("month")
        if month and not current_month_str:
            # YNAB month field is usually 'YYYY-MM-DD'; we simplify to 'YYYY-MM'
            current_month_str = str(month)[:7]

        rows.append(
            {
                "category_id": cid,
                "category_name": cname,
                "group_name": gname,
                "budgeted": budgeted,
                "activity": activity,
                "balance": balance,
                "dashboard_category": dash_cat,
            }
        )

    df = pd.DataFrame(rows)

    if current_month_str is None:
        # Fallback to today's year-month
        current_month_str = date.today().strftime("%Y-%m")

    df["month"] = current_month_str
    return df


def build_payee_category_overrides(
    token: str,
    budget_id: str,
    days_back: int = 90,
    threshold: int = 80,
):
    """
    Build a structure used for fuzzy matching:

    Returns:
        {
          "ynab_payees": [normalized_name, ...],
          "payee_to_category": {normalized_name: dashboard_category},
          "threshold": threshold,
        }
    """
    client = YNABClient(token=token)

    since = date.today() - timedelta(days=days_back)
    since_str = since.isoformat()

    txs = client.get_transactions_since(budget_id, since_str)
    if not txs:
        return {
            "ynab_payees": [],
            "payee_to_category": {},
            "threshold": threshold,
        }

    # Build map category_id -> category_name
    cat_groups = client.get_categories(budget_id)
    cat_id_to_name: Dict[str, str] = {}
    for g in cat_groups:
        for cat in g.get("categories", []):
            cid = cat.get("id")
            cname = cat.get("name", "")
            if cid:
                cat_id_to_name[cid] = cname

    ynab_payees = []
    payee_to_category: Dict[str, str] = {}

    for t in txs:
        cat_id = t.get("category_id")
        payee_name = t.get("payee_name") or ""
        if not cat_id or not payee_name:
            continue

        ynab_cat_name = cat_id_to_name.get(cat_id, "")
        if not ynab_cat_name:
            continue

        dash_cat = map_ynab_category_to_dashboard(ynab_cat_name)

        clean_payee = normalize_payee(payee_name)
        if not clean_payee:
            continue

        ynab_payees.append(clean_payee)
        payee_to_category[clean_payee] = dash_cat

    ynab_payees = list(set(ynab_payees))

    return {
        "ynab_payees": ynab_payees,
        "payee_to_category": payee_to_category,
        "threshold": threshold,
    }


def fetch_all_ynab_categories(token: str, budget_id: str) -> list[str]:
    """
    Returns a flat list of ALL visible category names in the given budget.
    """
    client = YNABClient(token=token)
    groups = client.get_categories(budget_id)

    categories: list[str] = []
    for g in groups:
        for cat in g.get("categories", []):
            name = cat.get("name")
            if name and not cat.get("hidden", False):
                categories.append(name)

    return sorted(categories)