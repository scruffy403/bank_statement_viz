# utils/anomalies.py
from __future__ import annotations

import pandas as pd


def detect_amount_anomalies(df: pd.DataFrame) -> pd.DataFrame:
    """
    Detect unusually large expenses per merchant using IQR.
    """
    if df.empty or "Paid out" not in df.columns:
        return pd.DataFrame()

    df = df.copy()
    if "MerchantClean" not in df.columns:
        df["MerchantClean"] = "unknown"

    grp = df.groupby("MerchantClean")["Paid out"]
    q1 = grp.transform(lambda x: x.quantile(0.25))
    q3 = grp.transform(lambda x: x.quantile(0.75))
    iqr = q3 - q1
    upper = q3 + 1.5 * iqr

    df["Anomaly"] = df["Paid out"] > upper
    anomalies = df[df["Anomaly"]].copy()
    return anomalies.sort_values("Paid out", ascending=False)