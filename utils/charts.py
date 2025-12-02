# utils/charts.py
from __future__ import annotations

import pandas as pd
import plotly.express as px


def fig_balance_over_time(df: pd.DataFrame):
    if df.empty:
        return px.line(title="Balance over time")

    daily = (
        df.groupby("Date")["Net"]
        .sum()
        .sort_index()
        .reset_index()
    )
    daily["Cumulative"] = daily["Net"].cumsum()
    return px.line(daily, x="Date", y="Cumulative", title="Cumulative Net Balance")


def fig_monthly_spend_stacked(df: pd.DataFrame):
    if df.empty or "Paid out" not in df.columns:
        return px.bar(title="Monthly spending")

    tmp = df.copy()
    tmp["YearMonth"] = tmp["Date"].dt.to_period("M").dt.to_timestamp()
    monthly = (
        tmp.groupby(["YearMonth", "Category"])["Paid out"]
        .sum()
        .reset_index()
    )

    return px.bar(
        monthly,
        x="YearMonth",
        y="Paid out",
        color="Category",
        title="Monthly Spending by Category",
        barmode="stack",
    )


def fig_daily_net_cashflow(daily: pd.DataFrame):
    if daily.empty:
        return px.bar(title="Daily net cashflow")

    return px.bar(daily, x="Date", y="Net", title="Daily Net Cashflow")


def fig_cumulative_cashflow(daily: pd.DataFrame):
    if daily.empty:
        return px.line(title="Cumulative cashflow")

    return px.line(daily, x="Date", y="Cumulative", title="Cumulative Cashflow")


def fig_forecast_cumulative(combined: pd.DataFrame):
    if combined.empty:
        return px.line(title="Forecast cumulative cashflow")

    return px.line(
        combined,
        x="Date",
        y="Cumulative",
        color="IsForecast",
        title="Actual vs Forecast Cumulative Cashflow",
    )


def fig_category_trends(df: pd.DataFrame):
    if df.empty or "Paid out" not in df.columns:
        return px.line(title="Category trends")

    tmp = df.copy()
    tmp["YearMonth"] = tmp["Date"].dt.to_period("M").dt.to_timestamp()
    monthly = (
        tmp.groupby(["YearMonth", "Category"])["Paid out"]
        .sum()
        .reset_index()
    )

    return px.line(
        monthly,
        x="YearMonth",
        y="Paid out",
        color="Category",
        title="Spending Trends by Category",
    )


def fig_top_merchants(expense_df: pd.DataFrame, top_n: int = 15):
    if expense_df.empty or "Paid out" not in expense_df.columns:
        return px.bar(title="Top merchants")

    top = (
        expense_df.groupby("MerchantClean")["Paid out"]
        .sum()
        .sort_values(ascending=False)
        .head(top_n)
        .reset_index()
    )
    return px.bar(
        top,
        x="MerchantClean",
        y="Paid out",
        title=f"Top {top_n} Merchants by Spend",
    )


def fig_anomalies_scatter(expense_df: pd.DataFrame, anomalies: pd.DataFrame):
    if expense_df.empty:
        return px.scatter(title="Anomalies")

    base = expense_df.copy()
    base["IsAnomaly"] = False

    if not anomalies.empty:
        base.loc[anomalies.index, "IsAnomaly"] = True

    return px.scatter(
        base,
        x="Date",
        y="Paid out",
        color="IsAnomaly",
        title="Spending with Anomalies Highlighted",
        hover_data=["MerchantClean", "Category"],
    )