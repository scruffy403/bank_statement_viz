# utils/budget_settings.py
from __future__ import annotations

from typing import Dict, Any

import streamlit as st
import pandas as pd

from .budgets import _get_or_create_category  # internal helper is ok here


def budget_settings_editor(
    df: pd.DataFrame,
    history: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Streamlit UI for editing per-category budget configuration.

    For each category:
      - mode: 'manual', 'stable', or 'ynab'
      - amount: monthly budget amount (applied across months in range)

    Returns the updated history dict (not yet saved to disk).
    """
    history = history.copy()
    cats_cfg = history.setdefault("categories", {})

    st.markdown(
        """
        ### Budget Settings

        For each category, choose how its budget should be handled:

        - **manual** – you provide a monthly budget amount.
        - **stable** – a fixed monthly amount that rarely changes (e.g. mortgage).
        - **ynab** – amount is typically imported from the current YNAB month, but can be overridden.

        The monthly amount is multiplied by the number of months in the currently
        filtered data when computing total Budget vs Actual.
        """
    )

    if df.empty:
        st.info("No data available to configure budgets.")
        return history

    categories = sorted(df["Category"].dropna().unique().tolist())
    if not categories:
        st.info("No categories found in the data.")
        return history

    st.markdown("#### Category Budget Modes & Amounts")

    cols = st.columns([2, 1, 1])  # header row
    cols[0].markdown("**Category**")
    cols[1].markdown("**Mode**")
    cols[2].markdown("**Monthly Amount (£)**")

    for cat in categories:
        cfg = _get_or_create_category(history, cat, default_mode="manual")
        mode = cfg.get("mode", "manual")
        amount = float(cfg.get("amount") or 0.0)

        c1, c2, c3 = st.columns([2, 1, 1])

        c1.write(cat)

        mode_sel = c2.selectbox(
            f"Mode for {cat}",
            options=["manual", "stable", "ynab"],
            index=["manual", "stable", "ynab"].index(mode) if mode in ["manual", "stable", "ynab"] else 0,
            key=f"mode_{cat}",
        )

        # Help text hint for YNAB mode
        if mode_sel == "ynab":
            amt_help = "Typically imported from YNAB current month; you can override here if needed."
        elif mode_sel == "stable":
            amt_help = "Fixed monthly amount (e.g. mortgage or council tax)."
        else:
            amt_help = "Manually-chosen monthly budget amount."

        amt_val = c3.number_input(
            f"Monthly amount for {cat}",
            min_value=0.0,
            step=10.0,
            value=amount,
            key=f"amount_{cat}",
            help=amt_help,
        )

        cfg["mode"] = mode_sel
        cfg["amount"] = float(amt_val)

    return history