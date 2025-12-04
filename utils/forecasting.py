# utils/forecasting.py
from __future__ import annotations

import pandas as pd
import numpy as np


def build_cashflow_timeseries(df: pd.DataFrame) -> pd.DataFrame:
    """
    Builds a daily net cashflow timeseries:
    - one row per date
    - net = income - expenses
    """
    if df.empty:
        return pd.DataFrame(columns=["Date", "Net", "Cumulative"])

    daily = (
        df.groupby("Date")["Net"]
        .sum()
        .reset_index()
        .sort_values("Date")
    )

    daily["Cumulative"] = daily["Net"].cumsum()

    return daily


def add_simple_forecast(daily_df: pd.DataFrame, days_ahead: int = 60) -> pd.DataFrame:
    """
    Adds a simple forward-looking forecast using the historical mean daily net flow.
    Returns a new dataframe with future dates appended.
    """

    if daily_df.empty:
        return daily_df

    df = daily_df.copy()

    # Compute average daily net flow (simple model)
    if "Net" not in df.columns:
        raise ValueError("daily_df must contain a 'Net' column")

    mean_net = df["Net"].mean()

    # Start forecasting from last actual date & cumulative total
    last_date = df["Date"].max()
    last_cum = df["Cumulative"].iloc[-1]

    future_rows = []
    current_cum = last_cum

    for i in range(1, days_ahead + 1):
        d = last_date + pd.Timedelta(days=i)
        current_cum += mean_net
        future_rows.append({"Date": d, "Net": mean_net, "Cumulative": current_cum})

    forecast_df = pd.DataFrame(future_rows)
    forecast_df["Type"] = "Forecast"

    df["Type"] = "Actual"

    return pd.concat([df, forecast_df], ignore_index=True)