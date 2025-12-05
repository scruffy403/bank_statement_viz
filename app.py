from __future__ import annotations

import json
import requests
from pathlib import Path
from typing import Dict

import pandas as pd
import streamlit as st

# ---- Utils Imports ----
from utils.loader import choose_data_source, load_bank_csv
from utils.cleaning import clean_bank_dataframe, add_time_columns, split_income_expense
from utils.categorization import apply_rule_based_categories
from utils.merchant_ai import (
    load_learned_overrides,
    update_overrides_from_user_input,
    train_merchant_model_from_df,
    apply_ml_categories,
)
from utils.subscriptions import detect_subscriptions
from utils.anomalies import detect_amount_anomalies
from utils.budgets import (
    load_budget_history,
    save_budget_history,
    compute_budget_vs_actual,
    update_history_from_ynab,
)
from utils.budget_settings import budget_settings_editor
from utils.forecasting import build_cashflow_timeseries, add_simple_forecast
from utils.charts import (
    fig_balance_over_time,
    fig_monthly_spend_stacked,
    fig_daily_net_cashflow,
    fig_cumulative_cashflow,
    fig_category_trends,
    fig_top_merchants,
    fig_anomalies_scatter,
)
from utils.charts_forecast import fig_forecast_cumulative
from utils.pdf_report import generate_monthly_report_pdf
from utils.ynab_api import (
    fetch_current_month_category_budgets,
    fetch_all_ynab_categories,
    build_payee_category_overrides,
    list_budgets,
)


# Cached YNAB payee overrides for merchant AI
@st.cache_data(show_spinner=False)
def ynab_payee_overrides_cached(token: str, budget_id: str) -> Dict[str, str]:
    data = build_payee_category_overrides(token, budget_id, days_back=90)
    return data.get("payee_to_category", {})


# ---- Streamlit App Config ----
st.set_page_config(page_title="Personal Finance Dashboard", layout="wide")


# ===============================
# Data Loading
# ===============================
@st.cache_data
def load_data_from_source(path: Path) -> pd.DataFrame:
    df_raw = load_bank_csv(path)
    df = clean_bank_dataframe(df_raw)
    return add_time_columns(df)


def sidebar_file_selection() -> pd.DataFrame:
    st.sidebar.header("Data Source")
    uploaded = st.sidebar.file_uploader("Upload Bank CSV", type=["csv"])
    path = choose_data_source(uploaded)

    if path is None:
        st.sidebar.warning("Upload a CSV to begin.")
        st.stop()

    st.sidebar.success(f"Using file: {path.name}")
    return load_data_from_source(path)


def sidebar_ynab_settings():
    st.sidebar.header("YNAB Integration (Optional)")

    # Pull token from sidebar input OR secrets
    token = st.sidebar.text_input("YNAB API Token", type="password") or st.secrets.get("YNAB_TOKEN")
    budget_id = None

    use_payees = False
    use_budgets = False

    if token:
        try:
            budgets = list_budgets(token)
            mapping = {b["name"]: b["id"] for b in budgets}

            selected = st.sidebar.selectbox("Select Budget", list(mapping.keys()))
            budget_id = mapping[selected]

            # store in session_state so other parts can use them
            st.session_state["ynab_token"] = token
            st.session_state["ynab_budget_id"] = budget_id

            st.sidebar.success("Connected to YNAB")

            use_payees = st.sidebar.checkbox("Use YNAB Payees for Categorisation")
            use_budgets = st.sidebar.checkbox("Import YNAB Budgets into history")

        except Exception as e:
            st.sidebar.error(f"YNAB Error: {e}")
    else:
        st.sidebar.info("Enter your YNAB token to enable integration.")

    return token, budget_id, use_payees, use_budgets


# ===============================
# Categorisation
# ===============================
def apply_full_categorisation(df: pd.DataFrame, token, budget_id, use_payees) -> pd.DataFrame:
    overrides = load_learned_overrides()

    ynab_fuzzy = None
    if token and budget_id and use_payees:
        try:
            ynab_fuzzy = build_payee_category_overrides(token, budget_id)
        except Exception as e:
            st.warning(f"YNAB Payee import failed: {e}")

    # We pass both manual overrides and fuzzy structure into the categoriser
    df = apply_rule_based_categories(df, overrides, ynab_fuzzy)
    train_merchant_model_from_df(df, overrides)
    return apply_ml_categories(df, overrides)


# ===============================
# Sidebar Filters
# ===============================
def sidebar_filters(df: pd.DataFrame) -> pd.DataFrame:
    st.sidebar.header("Filters")

    if "Date" in df.columns:
        min_d, max_d = df["Date"].min(), df["Date"].max()
        start, end = st.sidebar.date_input("Date Range", (min_d, max_d))
        df = df[(df["Date"] >= pd.to_datetime(start)) & (df["Date"] <= pd.to_datetime(end))]

    if "Category" in df.columns:
        cats = sorted(df["Category"].dropna().unique())
        chosen = st.sidebar.multiselect("Categories", cats, default=cats)
        df = df[df["Category"].isin(chosen)]

    st.sidebar.write(f"Rows After Filtering: {len(df):,}")
    return df


# ===============================
# Merchant Categorisation Editing
# ===============================
def merchant_editor(df: pd.DataFrame):
    st.subheader("Merchant Categorisation (Auto-Learning)")

    overrides = load_learned_overrides()

    # Merchant list (top 30 by spend)
    merchants = (
        df.groupby("MerchantClean")["Paid out"]
        .sum()
        .sort_values(ascending=False)
        .head(30)
    )

    if merchants.empty:
        st.write("No expense data available to categorise.")
        return

    # Dashboard categories from data
    dashboard_categories = sorted(df["Category"].dropna().unique().tolist())

    # YNAB: token + budget from session
    ynab_token = st.session_state.get("ynab_token")
    ynab_budget_id = st.session_state.get("ynab_budget_id")

    ynab_categories = []
    ynab_payee_map: dict[str, str] = {}

    if ynab_token and ynab_budget_id:
        # 1) Load all YNAB categories for dropdowns
        try:
            ynab_categories = fetch_all_ynab_categories(ynab_token, ynab_budget_id)
        except Exception as e:
            st.warning(f"Could not load YNAB categories: {e}")

        # 2) YNAB payee → category suggestions
        try:
            ynab_payee_map = ynab_payee_overrides_cached(ynab_token, ynab_budget_id)
        except Exception as e:
            st.warning(f"Could not load YNAB payee mappings: {e}")

    # Load globally saved custom categories (for merchant AI only)
    custom_categories_path = Path("models/custom_categories.json")
    if custom_categories_path.exists():
        try:
            with open(custom_categories_path, "r", encoding="utf-8") as f:
                custom_cats = json.load(f)
        except Exception:
            custom_cats = []
    else:
        custom_cats = []

    # Merge all category pools
    all_categories = sorted(set(dashboard_categories + ynab_categories + custom_cats + ["Other"]))

    st.write(
        "Default category priority:\n"
        "1. Saved override\n"
        "2. YNAB fuzzy payee match\n"
        "3. Majority category in your bank data\n"
        "4. Other\n\n"
        "You may also type a *custom* category below any dropdown.\n"
        "Custom categories are saved and appear in dropdowns next time."
    )

    updates = {}
    new_custom_categories = set(custom_cats)

    for merchant, spent in merchants.items():
        merchant_clean = str(merchant)

        # 1) Saved override
        current_cat = overrides.get(merchant_clean)

        # 2) YNAB fuzzy suggestion
        ynab_suggested = ynab_payee_map.get(merchant_clean)

        # 3) Majority category in data
        if current_cat is None:
            cats_for_merchant = (
                df[df["MerchantClean"] == merchant_clean]["Category"]
                .value_counts()
            )
            if not cats_for_merchant.empty:
                current_cat = cats_for_merchant.index[0]

        # 4) If still empty and YNAB has an idea → use it
        if current_cat is None and ynab_suggested:
            current_cat = ynab_suggested

        # 5) Final fallback
        if current_cat is None or current_cat not in all_categories:
            current_cat = "Other"

        hint = f" (YNAB suggests: {ynab_suggested})" if ynab_suggested and ynab_suggested != current_cat else ""
        label = f"{merchant_clean} (Spent £{spent:.2f}){hint}"

        selected_cat = st.selectbox(
            label,
            all_categories,
            index=all_categories.index(current_cat),
            key=f"mc_drop_{merchant_clean}",
        )

        # Optional custom category
        custom_cat = st.text_input(
            f"Custom category for {merchant_clean} (optional)",
            value="",
            key=f"mc_custom_{merchant_clean}",
            placeholder="Leave blank to use dropdown value",
        ).strip()

        if custom_cat:
            updates[merchant_clean] = custom_cat
            new_custom_categories.add(custom_cat)
        else:
            updates[merchant_clean] = selected_cat

    # Save button
    if st.button("Save merchant categories & retrain model"):
        updated_overrides = update_overrides_from_user_input(overrides, updates)

        # Save updated custom categories
        custom_categories_path.parent.mkdir(exist_ok=True)
        with open(custom_categories_path, "w", encoding="utf-8") as f:
            json.dump(sorted(new_custom_categories), f, indent=2, ensure_ascii=False)

        # Retrain model
        train_merchant_model_from_df(df, updated_overrides)

        st.success("Merchant categories saved, custom categories updated, and model retrained.")


# ===============================
# Main App
# ===============================
def main():
    df = sidebar_file_selection()
    token, budget_id, use_payees, use_budget_import = sidebar_ynab_settings()

    df = apply_full_categorisation(df, token, budget_id, use_payees)
    df = sidebar_filters(df)

    st.title("🏦 Personal Finance Dashboard")

    tabs = st.tabs([
        "Overview",
        "Cashflow",
        "Forecast",
        "Categories",
        "Merchants",
        "Anomalies",
        "Budgets",
        "Merchant AI",
        "YNAB API Data",  # <--- NEW TAB
        "Export"
    ])

    income, expense = split_income_expense(df)

    # =======================
    # Tab 1: Overview
    # =======================
    with tabs[0]:
        st.header("Overview")

        st.metric("Total Out", f"£{expense['Paid out'].sum():,.2f}")
        st.metric("Total In", f"£{income['Paid in'].sum():,.2f}")

        st.plotly_chart(fig_balance_over_time(df), use_container_width=True)
        st.plotly_chart(fig_monthly_spend_stacked(df), use_container_width=True)

    # =======================
    # Tab 2: Cashflow
    # =======================
    with tabs[1]:
        st.header("Cashflow")

        daily = build_cashflow_timeseries(df)

        st.subheader("Daily Net Cashflow")
        st.plotly_chart(fig_daily_net_cashflow(daily), use_container_width=True)

        st.subheader("Cumulative Cashflow")
        st.plotly_chart(fig_cumulative_cashflow(daily), use_container_width=True)

    # =======================
    # Tab 3: Forecast
    # =======================
    with tabs[2]:
        st.header("Cashflow Forecast")

        st.markdown(
            "Adjust the forecast horizon and optionally exclude categories or specific "
            "transactions that you know won’t recur (e.g., one-off expenses or cancelled subscriptions)."
        )

        days_ahead = st.slider(
            "Forecast horizon (days)",
            min_value=30,
            max_value=365,
            value=90,
            step=15,
            help="How many days into the future should the model project?",
        )

        # Exclude categories from forecast
        all_cats = sorted(df["Category"].dropna().unique())
        exclude_cats = st.multiselect(
            "Exclude categories from forecast",
            all_cats,
            default=[],
            help=(
                "These categories will be removed from the data used to compute the forecast trend. "
                "Historical charts still include them."
            ),
        )

        # Base dataset for forecasting (category-filtered)
        df_forecast_input = df.copy()
        if exclude_cats:
            df_forecast_input = df_forecast_input[~df_forecast_input["Category"].isin(exclude_cats)]

        # Exclude specific large transactions
        st.markdown("### Exclude specific large expenses (optional)")

        if "excluded_tx_ids" not in st.session_state:
            st.session_state["excluded_tx_ids"] = set()

        candidates = df_forecast_input.copy()
        if "Paid out" in candidates.columns:
            candidates = candidates[candidates["Paid out"] > 0].sort_values("Paid out", ascending=False).head(50)
        else:
            candidates = pd.DataFrame(columns=df_forecast_input.columns)

        if not candidates.empty:
            options = {}
            for idx, row in candidates.iterrows():
                date_str = (
                    row["Date"].date().isoformat()
                    if "Date" in row and pd.notna(row["Date"])
                    else "Unknown date"
                )
                desc = str(row.get("Description", ""))[:40]
                amount = float(row.get("Paid out", 0.0))
                label = f"{date_str} | £{amount:,.2f} | {desc}"
                options[label] = idx

            current_ids = st.session_state["excluded_tx_ids"]
            default_labels = [lbl for lbl, ix in options.items() if ix in current_ids]

            selected_labels = st.multiselect(
                "Transactions to exclude from forecast",
                list(options.keys()),
                default=default_labels,
                help=(
                    "These transactions will be removed from the trend estimation, "
                    "but will remain in the historical charts."
                ),
            )

            st.session_state["excluded_tx_ids"] = {options[lbl] for lbl in selected_labels}

            if st.session_state["excluded_tx_ids"]:
                df_forecast_input = df_forecast_input[
                    ~df_forecast_input.index.isin(st.session_state["excluded_tx_ids"])
                ]
        else:
            st.info("No large outgoing transactions found to exclude.")

        daily_for_forecast = build_cashflow_timeseries(df_forecast_input)

        if daily_for_forecast.empty:
            st.warning("No data available for forecasting after applying filters/exclusions.")
        else:
            forecast_df = add_simple_forecast(daily_for_forecast, days_ahead=days_ahead)
            st.subheader("Cumulative Cashflow Forecast")
            st.plotly_chart(fig_forecast_cumulative(forecast_df), use_container_width=True)

            with st.expander("Show forecast data"):
                st.dataframe(forecast_df)

    # =======================
    # Tab 4: Categories
    # =======================
    with tabs[3]:
        st.header("Category Trends")
        st.plotly_chart(fig_category_trends(df), use_container_width=True)

    # =======================
    # Tab 5: Merchants
    # =======================
    with tabs[4]:
        st.header("Top Merchants")
        st.plotly_chart(fig_top_merchants(expense), use_container_width=True)

        st.subheader("Detected Subscriptions")
        st.dataframe(detect_subscriptions(df))

    # =======================
    # Tab 6: Anomalies
    # =======================
    with tabs[5]:
        st.header("Unusual Transactions")
        anomalies = detect_amount_anomalies(expense)

        st.dataframe(anomalies)
        st.plotly_chart(fig_anomalies_scatter(expense, anomalies), use_container_width=True)

    # =======================
    # Tab 7: Budgets
    # =======================
    with tabs[6]:
        st.header("Budgets vs Actual")

        # Load existing budget history
        budget_history = load_budget_history()

        # Optional: import current-month budgets from YNAB
        if token and budget_id and use_budget_import:
            try:
                st.subheader("YNAB current month budgets (raw)")
                ynab_bud_df = fetch_current_month_category_budgets(token, budget_id)
                st.dataframe(ynab_bud_df)

                # Use the month string from the DataFrame
                year_month = ynab_bud_df["month"].iloc[0]
                budget_history = update_history_from_ynab(budget_history, ynab_bud_df, year_month)
                save_budget_history(budget_history)

                st.success(f"Imported YNAB budgets into history for {year_month}.")
            except Exception as e:
                st.warning(f"YNAB Budget Import Failed: {e}")

        # Budget settings editor (for modes & amounts)
        with st.expander("Configure category budget modes & amounts"):
            budget_history = budget_settings_editor(df, budget_history)
            if st.button("💾 Save budget settings"):
                save_budget_history(budget_history)
                st.success("Budget settings saved.")

        # Now compute Budget vs Actual over the current filtered period
        bv = compute_budget_vs_actual(expense, budget_history)
        if bv.empty:
            st.write("No budget/spend data available for this period.")
        else:
            st.subheader("Budget vs Actual (current filter)")
            st.dataframe(bv)

            st.subheader("Budget vs Actual chart")
            chart_df = bv.set_index("Category")[["Budget", "Actual"]]
            st.bar_chart(chart_df)

    # =======================
    # Tab 8: Merchant AI
    # =======================
    with tabs[7]:
        merchant_editor(df)

    # =======================
    # Tab 9: YNAB API Data
    # =======================
    with tabs[8]:
        st.header("YNAB API – Raw Data Viewer")

        if not token or not budget_id:
            st.info("Connect a YNAB token + select a budget in the sidebar to view raw API data.")
        else:
            st.success("YNAB connected — showing raw API responses")

            from utils.ynab_api import YNABClient
            client = YNABClient(token=token)

            # -------------------- CATEGORY GROUPS --------------------
            st.subheader("Category Groups & Categories")
            try:
                groups = client.get_categories(budget_id)
                with st.expander("Show category groups JSON"):
                    st.json(groups)
            except Exception as e:
                st.error(f"Error fetching categories: {e}")

            # -------------------- CURRENT MONTH CATEGORIES --------------------
            st.subheader("Current Month Categories (budget/activity/balance)")
            try:
                curr_month = client.get_current_month_categories(budget_id)
                with st.expander("Show current month categories JSON"):
                    st.json(curr_month)
            except Exception as e:
                st.error(f"Error fetching current month categories: {e}")

            # -------------------- PAST MONTHS --------------------
            st.subheader("Past Months Metadata")
            try:
                url = f"https://api.youneedabudget.com/v1/budgets/{budget_id}/months"
                resp = requests.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=15)
                resp.raise_for_status()
                months = resp.json().get("data", {}).get("months", [])
                with st.expander("Show months JSON"):
                    st.json(months)
            except Exception as e:
                st.error(f"Error fetching months: {e}")

            # -------------------- PAYEES --------------------
            st.subheader("Payees")
            try:
                payees = client.get_payees(budget_id)
                with st.expander("Show payees JSON"):
                    st.json(payees)
            except Exception as e:
                st.error(f"Error fetching payees: {e}")

            # -------------------- RECENT TRANSACTIONS --------------------
            st.subheader("Recent Transactions (last 90 days)")
            try:
                since_str = (pd.Timestamp.today() - pd.Timedelta(days=90)).date().isoformat()
                txs = client.get_transactions_since(budget_id, since_str)
                with st.expander("Show transactions JSON"):
                    st.json(txs)
            except Exception as e:
                st.error(f"Error fetching transactions: {e}")

    # =======================
    # Tab 10: Export
    # =======================
    with tabs[9]:
        st.header("Export Data")

        st.download_button("Download Filtered CSV", df.to_csv(index=False), "filtered.csv")
        st.download_button("Download PDF Report", generate_monthly_report_pdf(df), "report.pdf")


if __name__ == "__main__":
    main()