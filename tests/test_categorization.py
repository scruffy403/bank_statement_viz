# tests/test_categorization.py
import pandas as pd

from utils.categorization import apply_rule_based_categories


def test_apply_rule_based_categories_manual_override_wins():
    df = pd.DataFrame(
        [
            {
                "MerchantClean": "Milk And More",
                "Transaction type": "Visa Debit",
                "Net": -10.0,
            }
        ]
    )

    overrides = {"Milk And More": "Groceries"}
    result = apply_rule_based_categories(df, overrides, ynab_fuzzy=None)

    assert result.loc[0, "Category"] == "Groceries"


def test_apply_rule_based_categories_ynab_fuzzy_used_when_no_override():
    df = pd.DataFrame(
        [
            {
                "MerchantClean": "Milk & More",
                "Transaction type": "Visa Debit",
                "Net": -12.0,
            }
        ]
    )

    # Simulate YNAB fuzzy mapping
    ynab_fuzzy = {
        "ynab_payees": ["milk and more"],  # target corpus
        "payee_to_category": {"milk and more": "Groceries (YNAB)"},
        "threshold": 70,
    }

    overrides = {}  # no manual override
    result = apply_rule_based_categories(df, overrides, ynab_fuzzy=ynab_fuzzy)

    assert result.loc[0, "Category"] == "Groceries (YNAB)"


def test_apply_rule_based_categories_keyword_fallbacks():
    df = pd.DataFrame(
        [
            {"MerchantClean": "Tesco Superstore", "Transaction type": "Visa Debit", "Net": -30.0},
            {"MerchantClean": "Uber London", "Transaction type": "Visa Debit", "Net": -15.0},
            {"MerchantClean": "Random Income", "Transaction type": "Credit", "Net": 100.0},
            {"MerchantClean": "Some Unknown Shop", "Transaction type": "Visa Debit", "Net": -5.0},
        ]
    )

    result = apply_rule_based_categories(df, overrides={}, ynab_fuzzy=None)

    rows = result.set_index("MerchantClean")

    assert rows.loc["Tesco Superstore", "Category"] == "Groceries"
    assert rows.loc["Uber London", "Category"] == "Transport"
    assert rows.loc["Random Income", "Category"] == "Income"
    # Unknown should fall to "Other" (given current keyword rules)
    assert rows.loc["Some Unknown Shop", "Category"] == "Other"