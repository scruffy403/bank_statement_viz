# utils/forecasting.py
from __future__ import annotations

from datetime import timedelta

import pandas as pd


def build_cashflow_timeseries(df: pd.DataFrame) -> pd.DataFrame:
    """
    Build a daily net & cumulative net series.
    """
    if df.empty:
        return pd.DataFrame(columns=["Date", "Net", "Cumulative"])

    daily = (
        df.groupby("Date")["Net"]
        .sum()
        .sort_index()
        .reset_index()
    )
    daily["Cumulative"] = daily["Net"].cumsum()
    return daily


def add_simple_forecast(daily: pd.DataFrame, days_ahead: int = 60) -> pd.DataFrame:
    """
    Extend the cumulative series by assuming average daily net continues.
    """
    if daily.empty:
        return daily

    daily = daily.copy()
    daily["IsForecast"] = False

    avg_net = daily["Net"].mean()
    last_date = daily["Date"].max()
    last_cum = daily["Cumulative"].iloc[-1]

    future_rows = []
    for i in range(1, days_ahead + 1):
        d = last_date + timedelta(days=i)
        c = last_cum + avg_net * i
        future_rows.append({"Date": d, "Net": avg_net, "Cumulative": c, "IsForecast": True})

    future = pd.DataFrame(future_rows)
    combined = pd.concat([daily, future], ignore_index=True)
    return combined