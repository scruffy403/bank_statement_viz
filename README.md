# Personal Finance Dashboard (Prototype)

A Streamlit app for visualising and analysing personal bank statements, with optional [YNAB](https://www.youneedabudget.com/) integration.

## Features

- **Overview** — balance over time and monthly spend broken down by category
- **Cashflow** — daily net and cumulative cashflow charts
- **Forecast** — linear cashflow projection with adjustable horizon (30–365 days); exclude categories or one-off transactions
- **Categories** — spending trends by category over time
- **Merchants** — top merchants by spend; automatic subscription detection
- **Anomalies** — statistical detection of unusual transactions
- **Budgets** — budget vs. actual comparison, manually configurable or imported from YNAB
- **Merchant AI** — auto-learning categorisation using rule-based matching + a trained ML model; supports custom categories and YNAB payee suggestions
- **YNAB API Data** — raw viewer for YNAB category groups, monthly budgets, payees, and recent transactions
- **Export** — download filtered data as CSV or a PDF report

## Getting Started

### Prerequisites

- Python 3.10+
- Install dependencies:

```bash
pip install -r requirements.txt
```

### Running the app

```bash
streamlit run app.py
```

### Data input

Upload a bank statement CSV via the sidebar. The CSV is expected to contain at minimum `Date`, `Description`, `Paid out`, and `Paid in` columns (standard UK bank export format).

## YNAB Integration (optional)

Enter your YNAB Personal Access Token in the sidebar to:

- Import your budget categories and payees for smarter transaction categorisation
- Sync current-month budget targets into the Budgets tab
- Browse raw YNAB API responses in the YNAB API Data tab

You can also store your token in a Streamlit secrets file to avoid entering it each time:

```toml
# .streamlit/secrets.toml
YNAB_TOKEN = "your-token-here"
```

## Project Structure

```
app.py                  # Main Streamlit application
utils/
  loader.py             # CSV loading and data source selection
  cleaning.py           # Data cleaning and time column generation
  categorization.py     # Rule-based transaction categorisation
  merchant_ai.py        # ML-based merchant categorisation and override learning
  subscriptions.py      # Recurring/subscription detection
  anomalies.py          # Anomaly detection
  budgets.py            # Budget history load/save and YNAB budget import
  budget_settings.py    # Budget settings editor UI
  forecasting.py        # Cashflow time series and simple forecast
  charts.py             # Plotly chart builders
  charts_forecast.py    # Forecast chart builder
  pdf_report.py         # PDF report generation
  ynab_api.py           # YNAB API client
models/                 # Saved ML model artefacts and custom categories
```