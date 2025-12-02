from __future__ import annotations
import streamlit as st
import pandas as pd


from utils.loader import choose_data_source, load_bank_csv
from utils.cleaning import clean_bank_dataframe, add_time_columns, split_income_expense
from utils.categorization import apply_rule_based_categories
from utils.merchant_ai import (
    load_learned_overrides, update_overrides_from_user_input,
    train_merchant_model_from_df, apply_ml_categories, merge_external_overrides
)
from utils.subscriptions import detect_subscriptions
from utils.anomalies import detect_amount_anomalies
from utils.budgets import load_budgets, save_budgets, compute_budget_vs_actual
from utils.forecasting import build_cashflow_timeseries, add_simple_forecast
from utils.charts import (
    fig_balance_over_time, fig_monthly_spend_stacked,
    fig_daily_net_cashflow, fig_cumulative_cashflow, fig_forecast_cumulative,
    fig_category_trends, fig_top_merchants, fig_anomalies_scatter
)
from utils.pdf_report import generate_monthly_report_pdf
from utils.ynab_api import fetch_current_month_category_budgets, build_payee_category_overrides, list_budgets


st.set_page_config(page_title="Personal Finance Dashboard", layout="wide")


@st.cache_data
def load_data_from_source(path):
    df_raw = load_bank_csv(path)
    df = clean_bank_dataframe(df_raw)
    return add_time_columns(df)


def sidebar_file_selection():
    st.sidebar.header("Data Source")
    uploaded = st.sidebar.file_uploader("Upload CSV", type=["csv"])
    path = choose_data_source(uploaded)

    if path is None:
        st.sidebar.warning("Upload a CSV to continue.")
        st.stop()

    st.sidebar.success(f"Using file: {path.name}")
    return load_data_from_source(path)


def sidebar_ynab_settings():
    st.sidebar.header("YNAB Integration (optional)")

    token = st.sidebar.text_input("YNAB API Token", type="password") or st.secrets.get("YNAB_TOKEN")

    budget_id = None
    if token:
        try:
            budgets = list_budgets(token)
            names = [b["name"] for b in budgets]
            mapping = {b["name"]: b["id"] for b in budgets}

            selected = st.sidebar.selectbox("Select Budget", names)
            budget_id = mapping[selected]

            st.sidebar.success("Connected to YNAB")
        except Exception as e:
            st.sidebar.error(f"YNAB failed: {e}")

    use_payee_map = st.sidebar.checkbox("Use YNAB Payees for categorisation")
    use_budget_import = st.sidebar.checkbox("Import YNAB Budgets")

    return token, budget_id, use_payee_map, use_budget_import


def apply_full_categorisation(df, token, budget_id, use_payees):
    overrides = load_learned_overrides()

    ynab_overrides = {}
    if token and budget_id and use_payees:
        try:
            ynab_overrides = build_payee_category_overrides(token, budget_id)
        except Exception as e:
            st.warning(f"YNAB Payee import failed: {e}")

    merged = merge_external_overrides(overrides, ynab_overrides)

    df = apply_rule_based_categories(df, merged)
    train_merchant_model_from_df(df, merged)
    return apply_ml_categories(df, merged)


def sidebar_filters(df):
    st.sidebar.header("Filters")

    if "Date" in df.columns:
        min_d, max_d = df["Date"].min(), df["Date"].max()
        start, end = st.sidebar.date_input("Date Range", (min_d, max_d))
        df = df[(df["Date"] >= pd.to_datetime(start)) & (df["Date"] <= pd.to_datetime(end))]

    if "Category" in df.columns:
        cats = sorted(df["Category"].unique())
        chosen = st.sidebar.multiselect("Categories", cats, default=cats)
        df = df[df["Category"].isin(chosen)]

    st.sidebar.write(f"Rows after filtering: {len(df):,}")
    return df


def merchant_editor(df):
    st.subheader("Merchant Categorisation (Auto-Learning)")

    overrides = load_learned_overrides()
    merchants = df.groupby("MerchantClean")["Paid out"].sum().sort_values(ascending=False).head(30)

    cats = sorted(df["Category"].unique())
    cats.append("Other")

    updates = {}
    for merchant, spent in merchants.items():
        default_cat = overrides.get(merchant, "Other")
        selection = st.selectbox(
            f"{merchant} (Spent £{spent:.2f})",
            cats,
            index=cats.index(default_cat),
            key=f"mc_{merchant}"
        )
        updates[merchant] = selection

    if st.button("Save & Retrain Model"):
        update_overrides_from_user_input(overrides, updates)
        train_merchant_model_from_df(df, overrides)
        st.success("Saved.")


def main():
    df = sidebar_file_selection()

    token, budget_id, use_payees, use_budget_import = sidebar_ynab_settings()

    df = apply_full_categorisation(df, token, budget_id, use_payees)
    df = sidebar_filters(df)

    st.title("🏦 Personal Finance Dashboard")

    tabs = st.tabs([
        "Overview",
        "Cashflow",
        "Categories",
        "Merchants",
        "Anomalies",
        "Budgets",
        "Merchant AI",
        "Export"
    ])

    income, expense = split_income_expense(df)

    # ----- Overview -----
    with tabs[0]:
        st.header("Overview")
        st.metric("Total Out", f"£{expense['Paid out'].sum():,.2f}")
        st.metric("Total In", f"£{income['Paid in'].sum():,.2f}")

        st.plotly_chart(fig_balance_over_time(df), use_container_width=True)
        st.plotly_chart(fig_monthly_spend_stacked(df), use_container_width=True)

    # ----- Cashflow -----
    with tabs[1]:
        daily = build_cashflow_timeseries(df)
        st.plotly_chart(fig_daily_net_cashflow(daily), use_container_width=True)
        st.plotly_chart(fig_cumulative_cashflow(daily), use_container_width=True)
        st.plotly_chart(fig_forecast_cumulative(add_simple_forecast(daily)), use_container_width=True)

    # ----- Categories -----
    with tabs[2]:
        st.plotly_chart(fig_category_trends(df), use_container_width=True)

    # ----- Merchants -----
    with tabs[3]:
        st.plotly_chart(fig_top_merchants(expense), use_container_width=True)
        st.dataframe(detect_subscriptions(df))

    # ----- Anomalies -----
    with tabs[4]:
        anomalies = detect_amount_anomalies(expense)
        st.dataframe(anomalies)
        st.plotly_chart(fig_anomalies_scatter(expense, anomalies), use_container_width=True)

    # ----- Budgets -----
    with tabs[5]:
        if token and budget_id and use_budget_import:
            try:
                bud_df = fetch_current_month_category_budgets(token, budget_id)
                st.dataframe(bud_df)
                save_budgets({
                    row["dashboard_category"]: row["budgeted"]
                    for _, row in bud_df.iterrows()
                })
            except Exception as e:
                st.warning(f"YNAB budget import failed: {e}")

        st.dataframe(compute_budget_vs_actual(expense, load_budgets()))

    # ----- Merchant AI -----
    with tabs[6]:
        merchant_editor(df)

    # ----- Export -----
    with tabs[7]:
        st.download_button("Download CSV", df.to_csv(index=False), "filtered.csv")
        st.download_button("PDF Report", generate_monthly_report_pdf(df), "report.pdf")


if __name__ == "__main__":
    main()