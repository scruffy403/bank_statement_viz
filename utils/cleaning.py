# utils/cleaning.py
from __future__ import annotations
import pandas as pd
from datetime import datetime
from payee_normalizer import normalize_payee


def clean_bank_dataframe(df_raw: pd.DataFrame) -> pd.DataFrame:
    """
    Cleans raw bank CSV data and produces a consistent format including:
      - Date (datetime64)
      - MerchantClean (normalized payee)
      - Paid in, Paid out, Net
    """
    df = df_raw.copy()

    # ---- Standardize column names ----
    df.columns = [c.strip() for c in df.columns]

    # ---- Date parsing ----
    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"], dayfirst=True, errors="coerce")
    else:
        raise ValueError("Expected a 'Date' column in input CSV.")

    # ---- Normalize merchant/payee string ----
    if "Description" in df.columns:
        df["MerchantClean"] = df["Description"].astype(str).map(normalize_payee)
    else:
        df["MerchantClean"] = ""

    # ---- Monetary fields ----
    df["Paid in"] = (
        df.get("Paid in", 0)
        .fillna(0)  # ← handles NaN from empty CSV cells
        .replace("", 0)
        .astype(str)
        .str.replace("£", "")
        .str.replace(",", "")
        .astype(float)
    )

    df["Paid out"] = (
        df.get("Paid out", 0)
        .fillna(0)  # ← handles NaN from empty CSV cells
        .replace("", 0)
        .astype(str)
        .str.replace("£", "")
        .str.replace(",", "")
        .astype(float)
    )

    df["Net"] = df["Paid in"] - df["Paid out"]

    return df


def add_time_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Adds year, month, week, and day fields."""
    df = df.copy()
    df["Year"] = df["Date"].dt.year
    df["Month"] = df["Date"].dt.to_period("M")
    df["Week"] = df["Date"].dt.isocalendar().week
    df["Day"] = df["Date"].dt.date
    return df


def split_income_expense(df: pd.DataFrame):
    """Returns (income_df, expense_df)."""
    income = df[df["Paid in"] > 0]
    expense = df[df["Paid out"] > 0]
    return income, expense