# utils/merchant_ai.py
"""
Merchant AI — rule learning + lightweight ML categorisation.

In demo mode all filesystem writes are silently skipped so the app
works correctly on Streamlit Community Cloud (ephemeral filesystem,
read-only repo data).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

OVERRIDES_PATH = Path("models/merchant_overrides.json")
MODEL_CACHE: dict = {}   # in-memory model cache


# ── Persistence helpers ────────────────────────────────────────────────────────

def _demo_active() -> bool:
    """Lightweight check — avoids importing streamlit at module load time."""
    try:
        from utils.demo_mode import is_demo
        return is_demo()
    except Exception:
        return False


def load_learned_overrides() -> Dict[str, str]:
    """Load merchant → category overrides from disk."""
    if OVERRIDES_PATH.exists():
        try:
            with open(OVERRIDES_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_overrides(overrides: Dict[str, str]):
    """Write overrides to disk — skipped silently in demo mode."""
    if _demo_active():
        return
    OVERRIDES_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OVERRIDES_PATH, "w", encoding="utf-8") as f:
        json.dump(overrides, f, indent=2, ensure_ascii=False)


def update_overrides_from_user_input(
    existing: Dict[str, str],
    updates: Dict[str, str],
) -> Dict[str, str]:
    """Merge user edits into the existing overrides dict and persist."""
    merged = {**existing, **updates}
    _save_overrides(merged)
    return merged


# ── Model training ─────────────────────────────────────────────────────────────

def train_merchant_model_from_df(
    df: pd.DataFrame,
    overrides: Dict[str, str],
) -> None:
    """
    Train (or retrain) a TF-IDF + Logistic Regression classifier from the
    current DataFrame + known overrides.  The fitted pipeline is stored in
    the module-level MODEL_CACHE so it survives re-runs in the same session.
    """
    global MODEL_CACHE

    # Build training corpus: overrides take precedence over inferred categories
    rows = []
    if "MerchantClean" in df.columns and "Category" in df.columns:
        for _, row in df.iterrows():
            merchant = str(row.get("MerchantClean") or "").strip()
            category = str(row.get("Category") or "").strip()
            if merchant and category and category != "Other":
                rows.append((merchant, category))

    # Inject manual overrides (may expand training set)
    for merchant, category in overrides.items():
        rows.append((merchant, category))

    if len(rows) < 5:
        # Not enough data to train
        return

    texts, labels = zip(*rows)

    pipeline = Pipeline([
        ("tfidf", TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), max_features=8000)),
        ("clf",   LogisticRegression(max_iter=500, C=1.0, solver="lbfgs")),
    ])

    try:
        pipeline.fit(list(texts), list(labels))
        MODEL_CACHE["pipeline"] = pipeline
    except Exception:
        pass  # graceful — ML is enhancement, not critical path


def apply_ml_categories(
    df: pd.DataFrame,
    overrides: Dict[str, str],
) -> pd.DataFrame:
    """
    Apply the trained ML model to rows still labelled 'Other'.
    Falls back to the existing label if no model is available.
    """
    pipeline = MODEL_CACHE.get("pipeline")
    if pipeline is None or "MerchantClean" not in df.columns:
        return df

    df = df.copy()
    mask = df["Category"] == "Other"
    if not mask.any():
        return df

    merchants = df.loc[mask, "MerchantClean"].fillna("").astype(str).tolist()
    try:
        predictions = pipeline.predict(merchants)
        df.loc[mask, "Category"] = predictions
    except Exception:
        pass

    return df
