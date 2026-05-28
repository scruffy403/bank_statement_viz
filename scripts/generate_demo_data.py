"""
generate_demo_data.py
---------------------
Run once locally to produce data/demo_transactions.csv in the exact
format expected by utils/loader.py (the Halifax FlexDirect layout).

Usage:
    python scripts/generate_demo_data.py

Output:
    data/demo_transactions.csv
"""

from __future__ import annotations

import random
from pathlib import Path
from datetime import date, timedelta

import pandas as pd
import numpy as np

# ── Reproducibility ────────────────────────────────────────────────────────────
SEED = 42
random.seed(SEED)
np.random.seed(SEED)

# ── Date range ─────────────────────────────────────────────────────────────────
# 14 months back from a fixed anchor so the demo data never looks stale relative
# to "today" in the dashboard.  We use a fixed end date so the CSV is stable
# across regenerations.
END_DATE   = date(2025, 11, 30)
START_DATE = END_DATE - timedelta(days=14 * 30)

# ── Opening balance ────────────────────────────────────────────────────────────
OPENING_BALANCE = 8_500.00

# ── Merchant catalogue ─────────────────────────────────────────────────────────
# Each entry: (description_as_it_appears_in_csv, category_hint, amount_fn)
# Amounts are positive (the CSV has separate Paid out / Paid in columns).

def _fixed(amount: float):
    return lambda: round(amount, 2)

def _uniform(lo: float, hi: float):
    return lambda: round(random.uniform(lo, hi), 2)

def _normal(mu: float, sigma: float, lo: float = 0.5):
    return lambda: round(max(lo, np.random.normal(mu, sigma)), 2)


MONTHLY_EXPENSES = [
    # (description, tx_type, amount_fn, day_of_month, category_for_comment)
    ("HALIFAX MORTGAGE",           "Direct Debit", _fixed(1_285.00), 1,  "Mortgage"),
    ("OCTOPUS ENERGY",             "Direct Debit", _fixed(148.00),   3,  "Electric"),
    ("AFFINITY WATER CCP WEB",     "Direct Debit", _fixed(32.50),    5,  "Water"),
    ("WOKING BOROUGH COU",         "Direct Debit", _fixed(195.00),   8,  "Council Tax"),
    ("L G INSURANCE MI",           "Direct Debit", _fixed(42.00),    10, "Life insurance"),
    ("SMARTY CO MAIDENHEAD",       "Direct Debit", _fixed(15.00),    12, "Cell Phones"),
    ("HARLANDS",                   "Direct Debit", _fixed(38.00),    15, "Swimming Lessons"),
    ("GOCARDLESS",                 "Direct Debit", _fixed(45.00),    20, "Music lessons"),
    ("PET HEALTH CLUB",            "Direct Debit", _fixed(22.00),    22, "Pets"),
    ("SCRIPTURE UNION MILTON KEYNES","Direct Debit",_fixed(350.00),  1,  "Daycare"),
]

SUBSCRIPTIONS = [
    ("NETFLIX.COM",         "Direct Debit", _fixed(17.99),  14),
    ("SPOTIFY AB",          "Direct Debit", _fixed(11.99),  14),
    ("AMAZON PRIME",        "Direct Debit", _fixed(8.99),   21),
    ("ICLOUD.COM",          "Direct Debit", _fixed(2.99),   7),
    ("TIMES NEWSPAPERS LTD","Direct Debit", _fixed(26.00),  28),
]

# Groceries — 3-5 visits per week at various supermarkets
GROCERIES = [
    "SAINSBURYS S MKTS BROOKWOOD",
    "SAINSBURYS CO UK",
    "W M MORRISON STORE WOKING",
    "MORECO CAMBERLEY",
    "TESCO STORES WOKING",
    "ALDI STORES LTD WOKING",
    "LIDL GB GUILDFORD",
]

# Eating out — ~2× per week
EATING_OUT = [
    "COSTA COFFEE WOKING",
    "STARBUCKS WOKING",
    "MCDONALDS WOKING",
    "WAGAMAMA GUILDFORD",
    "NANDOS WOKING",
    "ITSU LONDON",
    "PRET A MANGER LONDON",
    "HONEST BURGERS GUILDFORD",
    "FIVE GUYS GUILDFORD",
    "DELIVEROO",
    "UBER EATS",
    "JUST EAT",
]

# Transport
TRANSPORT = [
    "UBER",
    "SOUTH WEST TRAINS",
    "STAGECOACH WOKING PIRBRIGHT",
    "TFL CONTACTLESS",
    "BP PETROL WOKING",
    "SHELL PETROL CAMBERLEY",
    "ESSO BYFLEET",
]

# Shopping / general retail
SHOPPING = [
    "AMAZON MARKETPLACE",
    "JOHN LEWIS GUILDFORD",
    "BOOTS PHARMACY WOKING",
    "ARGOS LTD WOKING",
    "HOBBYCRAFT WOKING",
    "NEXT RETAIL LTD",
    "MARKS AND SPENCER",
    "TKMAXX GUILDFORD",
]

# Medical / personal care
MEDICAL = [
    "PALMER CHIROPRACTIC WOKING APPLEPAY",
    "JOSHUA ROYLE",               # counselling
    "BUPA HEALTH WOKING",
    "LLOYDS PHARMACY WOKING",
]

# Giving
GIVING = [
    "PARISH GIVING SCHE",
    "CANCER RESEARCH UK",
    "OXFAM GB",
]

# Pets
PETS = [
    "PETS AT HOME LTD WOKING",
    "VET4PETS WOKING",
]

# Kids
KIDS = [
    "VMS IPAYIMPACT CO UK EDINBURGH",  # school snacks
    "HOBBYCRAFT WOKING",
    "WWW ROCKANDPOPFOUNDATI ALDERSHOT",
]

# USAA equivalent in UK context → car insurance
CAR_INSURANCE = [
    "ADMIRAL INSURANCE",
    "DIRECT LINE INSURANCE",
]

# Home maintenance (one-off, a few times a year)
HOME_MAINTENANCE = [
    "NIALLS PLUMBING",
    "B AND Q WOKING",
    "WICKES WOKING",
    "SCREWFIX DIRECT GUILDFORD",
]

# ── Income ─────────────────────────────────────────────────────────────────────
SALARY_DESC   = "SALARY PAYMENT EMPLOYER"
SALARY_AMOUNT = 3_850.00   # monthly net take-home
SALARY_DAY    = 25


# ── Helper ────────────────────────────────────────────────────────────────────

def all_dates(start: date, end: date):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def jitter_day(base_day: int, days: int = 2) -> int:
    """Return base_day ± up to `days`, clamped to 1-28."""
    return min(28, max(1, base_day + random.randint(-days, days)))


# ── Transaction builder ────────────────────────────────────────────────────────

def build_transactions() -> list[dict]:
    rows: list[dict] = []

    # Months in the range
    months: list[date] = []
    cur = START_DATE.replace(day=1)
    while cur <= END_DATE:
        months.append(cur)
        # advance one month
        if cur.month == 12:
            cur = cur.replace(year=cur.year + 1, month=1)
        else:
            cur = cur.replace(month=cur.month + 1)

    def add(d: date, tx_type: str, desc: str, paid_out: float = 0.0, paid_in: float = 0.0):
        rows.append({"Date": d, "Transaction type": tx_type,
                     "Description": desc,
                     "Paid out": paid_out if paid_out else "",
                     "Paid in":  paid_in  if paid_in  else ""})

    for m in months:
        year, month = m.year, m.month

        def clamp(day: int) -> date:
            # avoid invalid dates like Feb 31
            import calendar
            last = calendar.monthrange(year, month)[1]
            return date(year, month, min(day, last))

        # ── Salary ──
        add(clamp(SALARY_DAY), "Credit", SALARY_DESC, paid_in=SALARY_AMOUNT)

        # ── Fixed monthly direct debits ──
        for desc, tx_type, amt_fn, day, _ in MONTHLY_EXPENSES:
            add(clamp(jitter_day(day, 1)), tx_type, desc, paid_out=amt_fn())

        # ── Subscriptions ──
        for desc, tx_type, amt_fn, day in SUBSCRIPTIONS:
            add(clamp(jitter_day(day, 1)), tx_type, desc, paid_out=amt_fn())

        # ── Car insurance (annual-ish, split into monthly DD) ──
        ci_desc = random.choice(CAR_INSURANCE)
        add(clamp(18), "Direct Debit", ci_desc, paid_out=round(np.random.normal(58, 3), 2))

        # ── Groceries: 3–5 visits per week ──
        days_in_month = (clamp(28) - m).days + 28
        for week_start in range(0, days_in_month, 7):
            visits = random.randint(3, 5)
            for _ in range(visits):
                day_offset = week_start + random.randint(0, 6)
                d = m + timedelta(days=min(day_offset, days_in_month - 1))
                if d > END_DATE or d < START_DATE:
                    continue
                add(d, "Card payment",
                    random.choice(GROCERIES),
                    paid_out=_normal(52, 18, 8)())

        # ── Eating out: ~8 times a month ──
        for _ in range(random.randint(6, 10)):
            day_offset = random.randint(0, 27)
            d = m + timedelta(days=day_offset)
            if d > END_DATE or d < START_DATE:
                continue
            add(d, "Card payment",
                random.choice(EATING_OUT),
                paid_out=_normal(18, 9, 3)())

        # ── Transport: ~6 times a month ──
        for _ in range(random.randint(4, 8)):
            day_offset = random.randint(0, 27)
            d = m + timedelta(days=day_offset)
            if d > END_DATE or d < START_DATE:
                continue
            add(d, "Card payment",
                random.choice(TRANSPORT),
                paid_out=_normal(14, 8, 2)())

        # ── Shopping: ~4 times a month ──
        for _ in range(random.randint(2, 5)):
            day_offset = random.randint(0, 27)
            d = m + timedelta(days=day_offset)
            if d > END_DATE or d < START_DATE:
                continue
            add(d, "Card payment",
                random.choice(SHOPPING),
                paid_out=_normal(38, 22, 5)())

        # ── Medical: ~1 per month ──
        if random.random() < 0.7:
            d = m + timedelta(days=random.randint(0, 27))
            if START_DATE <= d <= END_DATE:
                add(d, "Card payment",
                    random.choice(MEDICAL),
                    paid_out=_normal(55, 20, 15)())

        # ── Giving: ~2 per month ──
        for _ in range(random.randint(1, 3)):
            d = m + timedelta(days=random.randint(0, 27))
            if START_DATE <= d <= END_DATE:
                add(d, "Direct Debit",
                    random.choice(GIVING),
                    paid_out=_normal(25, 10, 5)())

        # ── Pets: ~1 per month ──
        if random.random() < 0.6:
            d = m + timedelta(days=random.randint(0, 27))
            if START_DATE <= d <= END_DATE:
                add(d, "Card payment",
                    random.choice(PETS),
                    paid_out=_normal(42, 18, 8)())

        # ── Kids: ~2 per month ──
        for _ in range(random.randint(1, 3)):
            d = m + timedelta(days=random.randint(0, 27))
            if START_DATE <= d <= END_DATE:
                add(d, "Card payment",
                    random.choice(KIDS),
                    paid_out=_normal(22, 10, 3)())

        # ── Home maintenance: ~once every 3 months ──
        if random.random() < 0.33:
            d = m + timedelta(days=random.randint(0, 27))
            if START_DATE <= d <= END_DATE:
                add(d, "Card payment",
                    random.choice(HOME_MAINTENANCE),
                    paid_out=_normal(180, 90, 30)())

    # ── A few deliberate anomalies (large one-off transactions) ──
    anomaly_dates = [
        date(2025, 3, 14),
        date(2025, 7, 22),
        date(2025, 10, 5),
    ]
    anomaly_txs = [
        ("JOHN LEWIS GUILDFORD",   "Card payment", 428.00),
        ("BOOKING.COM AMSTERDAM",  "Card payment", 612.50),
        ("DVLA NVXNR",             "Direct Debit", 195.00),
    ]
    for d, (desc, tx_type, amt) in zip(anomaly_dates, anomaly_txs):
        if START_DATE <= d <= END_DATE:
            rows.append({"Date": d, "Transaction type": tx_type,
                         "Description": desc, "Paid out": amt, "Paid in": ""})

    return rows


# ── Assemble DataFrame ─────────────────────────────────────────────────────────

def build_csv(output_path: Path):
    rows = build_transactions()

    df = pd.DataFrame(rows)
    df["Date"] = pd.to_datetime(df["Date"])
    df = df.sort_values("Date").reset_index(drop=True)

    # Compute running balance
    balance = OPENING_BALANCE
    balances = []
    for _, row in df.iterrows():
        paid_out = float(row["Paid out"]) if row["Paid out"] != "" else 0.0
        paid_in  = float(row["Paid in"])  if row["Paid in"]  != "" else 0.0
        balance  = balance - paid_out + paid_in
        balances.append(round(balance, 2))
    df["Balance"] = balances

    # Format Date as DD/MM/YYYY (Halifax format)
    df["Date"] = df["Date"].dt.strftime("%d/%m/%Y")

    # Halifax CSV has 3 metadata rows before the real header
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        # Metadata header rows that load_bank_csv skips
        f.write('"Account Name:","Demo Current Account ****00000"\n')
        f.write('"Account Balance:","£{:,.2f}"\n'.format(balances[-1]))
        f.write('"Available Balance: ","£{:,.2f}"\n'.format(balances[-1]))
        # Real header
        f.write('"Date","Transaction type","Description","Paid out","Paid in","Balance"\n')
        # Rows
        for _, row in df.iterrows():
            paid_out = f'"{row["Paid out"]}"' if row["Paid out"] != "" else '""'
            paid_in  = f'"{row["Paid in"]}"'  if row["Paid in"]  != "" else '""'
            f.write(
                f'"{row["Date"]}","{row["Transaction type"]}","{row["Description"]}",'
                f'{paid_out},{paid_in},"{row["Balance"]}"\n'
            )

    print(f"✅  Written {len(df):,} transactions → {output_path}")
    print(f"    Date range: {df['Date'].iloc[0]}  →  {df['Date'].iloc[-1]}")
    print(f"    Closing balance: £{balances[-1]:,.2f}")


if __name__ == "__main__":
    out = Path(__file__).parent.parent / "data" / "demo_transactions.csv"
    build_csv(out)
