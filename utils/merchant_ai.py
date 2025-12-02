# utils/merchant_ai.py
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression


MODELS_DIR = Path("models")
OVERRIDES_PATH = MODELS_DIR / "merchant_overrides.json"

# In-memory ML model
_vectorizer: TfidfVectorizer | None = None
_clf: LogisticRegression | None = None


def load_learned_overrides() -> Dict[str, str]:
    MODELS_DIR.mkdir(exist_ok=True)
    if not OVERRIDES_PATH.exists():
        return {}
    try:
        with open(OVERRIDES_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_overrides(overrides: Dict[str, str]) -> None:
    MODELS_DIR.mkdir(exist_ok=True)
    with open(OVERRIDES_PATH, "w", encoding="utf-8") as f:
        json.dump(overrides, f, indent=2, ensure_ascii=False)


def update_overrides_from_user_input(
    existing: Dict[str, str],
    updates: Dict[str, str],
) -> Dict[str, str]:
    merged = dict(existing)
    merged.update(updates)
    _save_overrides(merged)
    return merged


def train_merchant_model_from_df(df: pd.DataFrame, overrides: Dict[str, str]) -> None:
    """
    Train a simple text classifier (MerchantClean -> Category).
    Uses overrides when present as labels.
    """
    global _vectorizer, _clf

    if df.empty:
        return

    df = df.copy()
    if "Category" not in df.columns:
        return

    # Build labels with overrides priority
    labels = []
    texts = []
    for _, row in df.iterrows():
        merchant = (row.get("MerchantClean") or "").strip()
        if not merchant:
            continue
        cat = overrides.get(merchant) or row.get("Category")
        if not cat:
            continue
        texts.append(merchant)
        labels.append(cat)

    if len(set(labels)) < 2:
        # Not enough diversity to train a model
        return

    vec = TfidfVectorizer(min_df=1, ngram_range=(1, 2))
    X = vec.fit_transform(texts)
    clf = LogisticRegression(max_iter=1000)
    clf.fit(X, labels)

    _vectorizer = vec
    _clf = clf


def apply_ml_categories(df: pd.DataFrame, overrides: Dict[str, str]) -> pd.DataFrame:
    """
    Use the trained model to fill in categories for merchants
    that are currently 'Other' or missing.
    """
    df = df.copy()
    global _vectorizer, _clf

    if _vectorizer is None or _clf is None:
        return df

    if "Category" not in df.columns:
        df["Category"] = "Other"

    mask = df["Category"].isna() | (df["Category"] == "Other")
    to_predict = df.loc[mask, "MerchantClean"].fillna("").astype(str)
    if to_predict.empty:
        return df

    X = _vectorizer.transform(to_predict)
    preds = _clf.predict(X)

    df.loc[mask, "Category"] = preds
    return df


def merge_external_overrides(
    base_overrides: Dict[str, str],
    external: Dict[str, str],
) -> Dict[str, str]:
    merged = base_overrides.copy()
    merged.update(external)
    return merged