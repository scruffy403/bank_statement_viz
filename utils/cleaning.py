# utils/cleaning.py
from __future__ import annotations

from typing import Tuple
import re

import pandas as pd


def normalize_merchant(name: str) -> str:
    """
    Normalise merchant / payee names so that:
    - Case is removed
    - Country suffixes like ' GB' / ' UK' are removed
    - Digits and punctuation are stripped
    - Multiple spaces are collapsed
    This is used for BOTH bank CSV merchants and YNAB payees so that
    fuzzy matching has a consistent representation to work from.
    """
    if not name:
        return ""
    name = name.lower()
    name = name.replace(" uk", "").replace(" gb", "")
    name = re.sub(r"\d+", "", name)              # remove numbers
    name = re.sub(r"[^a-z\s]", " ", name)        # punctuation → space
    name = re.sub(r"\s+", " ", name).strip()     # collapse spaces
    return name


def _parse_money(series: pd.Series) -> pd.Series:
    s = (
        series.astype(str)
        .str.replace("£", "", regex=False)
        .str.replace(",", "", regex=False)
        .str.strip()
    )
    s = s.replace({"": "0", "-": "0"})
    return pd.to_numeric(s, errors="coerce").fillna(0.0)


def clean_bank_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize column names, parse numeric columns, build MerchantClean & Net.
    Expected columns (case/space tolerant):
    - Date
    - Transaction type
    - Description
    - Paid out
    - Paid in
    - Balance
    """
    df = df.copy()
    df.columns = [c.strip() for c in df.columns]

    # Ensure required columns exist (create if missing)
    for col in ["Paid out", "Paid in", "Balance"]:
        if col not in df.columns:
            df[col] = 0.0

    # Parse money columns
    df["Paid out"] = _parse_money(df["Paid out"])
    df["Paid in"] = _parse_money(df["Paid in"])
    df["Balance"] = _parse_money(df["Balance"])

    # Clean description / merchant
    if "Description" not in df.columns:
        df["Description"] = ""

    desc = df["Description"].fillna("").astype(str)

    # Use the shared normaliser so this matches YNAB payee cleaning
    df["MerchantClean"] = desc.apply(normalize_merchant)
    df.loc[df["MerchantClean"] == "", "MerchantClean"] = "unknown"

    # Net = paid in - paid out
    df["Net"] = df["Paid in"] - df["Paid out"]

    return df


def add_time_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        df = df.dropna(subset=["Date"])
        df["Year"] = df["Date"].dt.year
        df["Month"] = df["Date"].dt.month
        df["YearMonth"] = df["Date"].dt.to_period("M").dt.to_timestamp()
    return df


def split_income_expense(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Split into income (Paid in > 0) and expense (Paid out > 0).
    """
    income = df[df["Paid in"] > 0].copy()
    expense = df[df["Paid out"] > 0].copy()
    return income, expense