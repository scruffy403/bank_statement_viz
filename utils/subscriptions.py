# utils/subscriptions.py
from __future__ import annotations

import pandas as pd


def detect_subscriptions(df: pd.DataFrame) -> pd.DataFrame:
    """
    Heuristic: merchants with >=3 charges with low relative std on Paid out
    = likely subscriptions.
    """
    if df.empty or "Paid out" not in df.columns:
        return pd.DataFrame()

    expenses = df[df["Paid out"] > 0].copy()

    grp = expenses.groupby("MerchantClean")["Paid out"]
    stats = grp.agg(["count", "mean", "std"]).reset_index()
    stats = stats.rename(
        columns={"count": "Tx count", "mean": "Avg amount", "std": "Std dev"}
    )

    stats = stats[stats["Tx count"] >= 3].copy()
    stats["Rel std"] = stats["Std dev"] / stats["Avg amount"].replace(0, pd.NA)

    # Low variability -> likely subscription
    subs = stats[stats["Rel std"] < 0.2].sort_values("Tx count", ascending=False)
    return subs.reset_index(drop=True)