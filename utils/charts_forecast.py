# utils/charts_forecast.py
from __future__ import annotations
import pandas as pd
import plotly.graph_objects as go


def fig_forecast_cumulative(
    df: pd.DataFrame,
    actual_df: pd.DataFrame | None = None,
    scenario_date: str | None = None
):
    """
    Build a cumulative cashflow chart that:
      • Shows actual past data (solid blue)
      • Shows forecasted future data (dotted orange)
      • Optionally overlays actual performance since scenario_date
      • Optionally shows a vertical line marking when scenario was created
    """

    fig = go.Figure()

    # Ensure Date is datetime
    df = df.copy()
    df["Date"] = pd.to_datetime(df["Date"])

    # Split actual vs forecast from forecast_df
    actual = df[df["Type"] == "Actual"]
    forecast = df[df["Type"] == "Forecast"]

    # ----------------------------
    # Actual historical cumulative
    # ----------------------------
    fig.add_trace(go.Scatter(
        x=actual["Date"],
        y=actual["Cumulative"],
        mode="lines",
        name="Actual (historical)",
        line=dict(color="royalblue", width=3)
    ))

    # ----------------------------
    # Forecast cumulative (dotted)
    # ----------------------------
    fig.add_trace(go.Scatter(
        x=forecast["Date"],
        y=forecast["Cumulative"],
        mode="lines",
        name="Forecast",
        line=dict(color="orange", width=3, dash="dot")
    ))

    # ----------------------------
    # Scenario comparison overlay
    # ----------------------------
    if scenario_date and actual_df is not None:
        try:
            sdate = pd.to_datetime(scenario_date)

            # Filter actual_df to dates *after* the scenario point
            actual_df = actual_df.copy()
            actual_df["Date"] = pd.to_datetime(actual_df["Date"])
            post_scenario = actual_df[actual_df["Date"] >= sdate]

            if not post_scenario.empty:
                fig.add_trace(go.Scatter(
                    x=post_scenario["Date"],
                    y=post_scenario["Cumulative"],
                    mode="lines",
                    name="Actual since scenario",
                    line=dict(color="green", width=3)
                ))

            # Add vertical line at scenario date
            fig.add_vline(
                x=sdate,
                line_width=2,
                line_dash="dash",
                line_color="purple",
                annotation_text="Scenario created",
                annotation_position="top right"
            )
        except Exception:
            pass  # Fail silently if scenario_date can't be parsed

    # ----------------------------
    # Layout
    # ----------------------------
    fig.update_layout(
        title="Cumulative Cashflow (Actual vs Forecast)",
        xaxis_title="Date",
        yaxis_title="Cumulative £",
        legend=dict(orientation="h"),
        hovermode="x unified",
        template="plotly_white"
    )

    return fig