"""
generate_demo_data.py
---------------------
Run once locally to produce data/demo_transactions.csv in the exact
format expected by utils/loader.py (Halifax FlexDirect layout).

Usage:
    python scripts/generate_demo_data.py

Output:
    data/demo_transactions.csv
"""
from __future__ import annotations

import calendar
import random
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

# ── Reproducibility ────────────────────────────────────────────────────────────
SEED = 42
random.seed(SEED)
np.random.seed(SEED)

# ── Date range — full clean months ────────────────────────────────────────────
START_DATE     = date(2024, 1, 1)
END_DATE       = date(2025, 11, 30)
OPENING_BALANCE = 8_500.00

# ── Income ─────────────────────────────────────────────────────────────────────
SALARY_DESC   = "SALARY PAYMENT EMPLOYER"
SALARY_AMOUNT = 3_850.00
SALARY_DAY    = 25

# ── Amount helpers ─────────────────────────────────────────────────────────────
def _fixed(a):
    return lambda: round(float(a), 2)

def _normal(mu, sigma, lo=0.5):
    return lambda: round(float(max(lo, np.random.normal(mu, sigma))), 2)

# ── Monthly fixed costs ────────────────────────────────────────────────────────
# (description, tx_type, amount_fn, target_day_of_month)
MONTHLY_EXPENSES = [
    ("HALIFAX MORTGAGE",             "Direct Debit", _fixed(1_285.00),  1),
    ("OCTOPUS ENERGY",               "Direct Debit", _fixed(148.00),    3),
    ("AFFINITY WATER CCP WEB",       "Direct Debit", _fixed(32.50),     5),
    ("WOKING BOROUGH COU",           "Direct Debit", _fixed(195.00),    8),
    ("L G INSURANCE MI",             "Direct Debit", _fixed(42.00),    10),
    ("SMARTY CO MAIDENHEAD",         "Direct Debit", _fixed(15.00),    12),
    ("HARLANDS",                     "Direct Debit", _fixed(38.00),    15),
    ("GOCARDLESS",                   "Direct Debit", _fixed(45.00),    20),
    ("PET HEALTH CLUB",              "Direct Debit", _fixed(22.00),    22),
    ("SCRIPTURE UNION MILTON KEYNES","Direct Debit", _fixed(350.00),    2),
    ("NETFLIX.COM",                  "Direct Debit", _fixed(17.99),    14),
    ("SPOTIFY AB",                   "Direct Debit", _fixed(11.99),    14),
    ("AMAZON PRIME",                 "Direct Debit", _fixed(8.99),     21),
    ("ICLOUD.COM",                   "Direct Debit", _fixed(2.99),      7),
    ("TIMES NEWSPAPERS LTD",         "Direct Debit", _fixed(26.00),    28),
    ("ADMIRAL INSURANCE",            "Direct Debit", _normal(58, 3),   18),
]

# ── Variable merchants by category ────────────────────────────────────────────
GROCERIES = [
    "SAINSBURYS S MKTS BROOKWOOD", "SAINSBURYS CO UK",
    "W M MORRISON STORE WOKING", "MORECO CAMBERLEY",
    "TESCO STORES WOKING", "ALDI STORES LTD WOKING", "LIDL GB GUILDFORD",
]
EATING_OUT = [
    "COSTA COFFEE WOKING", "STARBUCKS WOKING", "MCDONALDS WOKING",
    "WAGAMAMA GUILDFORD", "NANDOS WOKING", "DELIVEROO",
    "UBER EATS", "JUST EAT", "PRET A MANGER LONDON",
]
TRANSPORT = [
    "UBER", "SOUTH WEST TRAINS", "STAGECOACH WOKING PIRBRIGHT",
    "TFL CONTACTLESS", "BP PETROL WOKING", "SHELL PETROL CAMBERLEY",
]
SHOPPING = [
    "AMAZON MARKETPLACE", "JOHN LEWIS GUILDFORD", "BOOTS PHARMACY WOKING",
    "ARGOS LTD WOKING", "NEXT RETAIL LTD", "MARKS AND SPENCER", "TKMAXX GUILDFORD",
]
MEDICAL = [
    "PALMER CHIROPRACTIC WOKING APPLEPAY", "JOSHUA ROYLE", "LLOYDS PHARMACY WOKING",
]
GIVING = ["PARISH GIVING SCHE", "CANCER RESEARCH UK", "OXFAM GB"]
PETS   = ["PETS AT HOME LTD WOKING", "VET4PETS WOKING"]
KIDS   = ["VMS IPAYIMPACT CO UK EDINBURGH", "WWW ROCKANDPOPFOUNDATI ALDERSHOT"]
HOME   = ["NIALLS PLUMBING", "B AND Q WOKING", "SCREWFIX DIRECT GUILDFORD"]


# ── Helpers ────────────────────────────────────────────────────────────────────
def jitter(day: int, n: int = 2) -> int:
    return min(28, max(1, day + random.randint(-n, n)))


def safe_date(year: int, month: int, day: int) -> date:
    last = calendar.monthrange(year, month)[1]
    return date(year, month, min(day, last))


def month_sequence(start: date, end: date) -> list[date]:
    months = []
    cur = start.replace(day=1)
    while cur <= end:
        months.append(cur)
        cur = (cur.replace(month=cur.month + 1)
               if cur.month < 12
               else cur.replace(year=cur.year + 1, month=1))
    return months


# ── Transaction builder ────────────────────────────────────────────────────────
def build_transactions() -> list[dict]:
    rows: list[dict] = []

    def add(d: date, tx_type: str, desc: str,
            paid_out: float = 0.0, paid_in: float = 0.0):
        rows.append({
            "Date": d,
            "Transaction type": tx_type,
            "Description": desc,
            "Paid out": paid_out,
            "Paid in":  paid_in,
        })

    for m in month_sequence(START_DATE, END_DATE):
        y, mo = m.year, m.month
        dim = calendar.monthrange(y, mo)[1]   # correct days-in-month

        # Salary
        add(safe_date(y, mo, jitter(SALARY_DAY, 1)),
            "Credit", SALARY_DESC, paid_in=SALARY_AMOUNT)

        # Fixed direct debits
        for desc, tx_type, amt_fn, day in MONTHLY_EXPENSES:
            add(safe_date(y, mo, jitter(day, 1)), tx_type, desc,
                paid_out=amt_fn())

        # Groceries — 3-4 visits per week
        for week_start in range(0, dim, 7):
            for _ in range(random.randint(3, 4)):
                d = safe_date(y, mo, week_start + random.randint(1, min(7, dim - week_start)))
                add(d, "Card payment", random.choice(GROCERIES),
                    paid_out=_normal(52, 18, 8)())

        # Eating out — 6-10 times/month
        for _ in range(random.randint(6, 10)):
            add(safe_date(y, mo, random.randint(1, dim)),
                "Card payment", random.choice(EATING_OUT),
                paid_out=_normal(18, 9, 3)())

        # Transport — 4-8 times/month
        for _ in range(random.randint(4, 8)):
            add(safe_date(y, mo, random.randint(1, dim)),
                "Card payment", random.choice(TRANSPORT),
                paid_out=_normal(14, 8, 2)())

        # Shopping — 2-5 times/month
        for _ in range(random.randint(2, 5)):
            add(safe_date(y, mo, random.randint(1, dim)),
                "Card payment", random.choice(SHOPPING),
                paid_out=_normal(38, 22, 5)())

        # Medical — ~70% chance per month
        if random.random() < 0.7:
            add(safe_date(y, mo, random.randint(1, dim)),
                "Card payment", random.choice(MEDICAL),
                paid_out=_normal(55, 20, 15)())

        # Giving — 1-3 times/month
        for _ in range(random.randint(1, 3)):
            add(safe_date(y, mo, random.randint(1, dim)),
                "Direct Debit", random.choice(GIVING),
                paid_out=_normal(25, 10, 5)())

        # Pets — 60% chance
        if random.random() < 0.6:
            add(safe_date(y, mo, random.randint(1, dim)),
                "Card payment", random.choice(PETS),
                paid_out=_normal(42, 18, 8)())

        # Kids — 1-3 times/month
        for _ in range(random.randint(1, 3)):
            add(safe_date(y, mo, random.randint(1, dim)),
                "Card payment", random.choice(KIDS),
                paid_out=_normal(22, 10, 3)())

        # Home maintenance — ~25% chance per month
        if random.random() < 0.25:
            add(safe_date(y, mo, random.randint(1, dim)),
                "Card payment", random.choice(HOME),
                paid_out=_normal(180, 90, 30)())

    # Deliberate anomalies for the Anomalies tab to flag
    anomalies = [
        (date(2024, 3, 14), "JOHN LEWIS GUILDFORD",    "Card payment", 428.00),
        (date(2024, 7, 22), "BOOKING.COM AMSTERDAM",   "Card payment", 612.50),
        (date(2024, 10, 5), "DVLA NVXNR",              "Direct Debit", 195.00),
        (date(2025, 2, 18), "ARGOS LTD WOKING",         "Card payment", 389.00),
        (date(2025, 8, 3),  "SCREWFIX DIRECT GUILDFORD","Card payment", 245.00),
    ]
    for d, desc, tx_type, amt in anomalies:
        rows.append({"Date": d, "Transaction type": tx_type,
                     "Description": desc, "Paid out": amt, "Paid in": 0.0})

    return rows


# ── Assemble and write CSV ─────────────────────────────────────────────────────
def build_csv(output_path: Path):
    rows = build_transactions()
    df = pd.DataFrame(rows)
    df["Date"] = pd.to_datetime(df["Date"])
    df = df.sort_values("Date").reset_index(drop=True)

    # Running balance
    balance = OPENING_BALANCE
    balances = []
    for _, row in df.iterrows():
        balance = balance - float(row["Paid out"]) + float(row["Paid in"])
        balances.append(round(balance, 2))
    df["Balance"] = balances

    # Format date as DD/MM/YYYY (Halifax format)
    df["Date"] = df["Date"].dt.strftime("%d/%m/%Y")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    closing = balances[-1]

    with open(output_path, "w", encoding="utf-8") as f:
        f.write('"Account Name:","Demo Current Account ****00000"\n')
        f.write(f'"Account Balance:","£{closing:,.2f}"\n')
        f.write(f'"Available Balance: ","£{closing:,.2f}"\n')
        f.write('"Date","Transaction type","Description","Paid out","Paid in","Balance"\n')
        for _, row in df.iterrows():
            po = f'"{row["Paid out"]}"' if float(row["Paid out"]) != 0.0 else '""'
            pi = f'"{row["Paid in"]}"'  if float(row["Paid in"])  != 0.0 else '""'
            f.write(
                f'"{row["Date"]}","{row["Transaction type"]}","{row["Description"]}",'
                f'{po},{pi},"{row["Balance"]}"\n'
            )

    total_in  = df["Paid in"].sum()
    total_out = df["Paid out"].sum()
    print(f"✅  Written {len(df):,} transactions → {output_path}")
    print(f"    Date range  : {df['Date'].iloc[0]}  →  {df['Date'].iloc[-1]}")
    print(f"    Total in    : £{total_in:,.2f}")
    print(f"    Total out   : £{total_out:,.2f}")
    print(f"    Net         : £{total_in - total_out:,.2f}")
    print(f"    Closing bal : £{closing:,.2f}")


if __name__ == "__main__":
    out = Path(__file__).parent.parent / "data" / "demo_transactions.csv"
    build_csv(out)