# tests/test_cleaning.py
import pandas as pd

from utils.cleaning import clean_bank_dataframe
from payee_normalizer import normalize_payee


def test_clean_bank_dataframe_basic():
    raw = pd.DataFrame(
        [
            {
                "Date": "02 Sep 2024",
                "Transaction type": "Visa Credit",
                "Description": "MILK AND MORE CAMBERLEY GB",
                "Paid out": "",
                "Paid in": "£2.50",
                "Balance": "£17030.43",
            },
            {
                "Date": "03 Sep 2024",
                "Transaction type": "Visa Debit",
                "Description": "ATM Withdrawal SAINSBURYS BANK 2024-04-15",
                "Paid out": "£50.00",
                "Paid in": "",
                "Balance": "£16980.43",
            },
        ]
    )

    df = clean_bank_dataframe(raw)

    # Date parsed
    assert "Date" in df.columns
    assert pd.api.types.is_datetime64_any_dtype(df["Date"])
    assert df["Date"].isna().sum() == 0

    # MerchantClean present + uses normalize_payee on Description
    assert "MerchantClean" in df.columns
    expected0 = normalize_payee("MILK AND MORE CAMBERLEY GB")
    expected1 = normalize_payee("ATM Withdrawal SAINSBURYS BANK 2024-04-15")

    assert df.loc[0, "MerchantClean"] == expected0
    assert df.loc[1, "MerchantClean"] == expected1

    # Money columns numeric and Net = Paid in - Paid out
    for col in ("Paid in", "Paid out", "Net"):
        assert col in df.columns
        assert pd.api.types.is_float_dtype(df[col])

    # row 0: 2.50 in, 0 out
    assert df.loc[0, "Paid in"] == 2.50
    assert df.loc[0, "Paid out"] == 0.0
    assert df.loc[0, "Net"] == 2.50

    # row 1: 0 in, 50 out
    assert df.loc[1, "Paid in"] == 0.0
    assert df.loc[1, "Paid out"] == 50.0
    assert df.loc[1, "Net"] == -50.0