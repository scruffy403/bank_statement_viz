# utils/demo_mode.py
"""
Demo mode support for the public Streamlit Community Cloud deployment.

Activate by setting the env var or Streamlit secret:
    DEMO_MODE = "true"

In demo mode the app:
  - Always loads data/demo_transactions.csv (no file uploader shown)
  - Hides YNAB sidebar inputs (no real credentials needed)
  - Makes all model writes (merchant_overrides, custom_categories) no-ops
  - Shows a prominent banner so visitors know they're seeing synthetic data
"""
from __future__ import annotations

import os
from pathlib import Path

import streamlit as st


def is_demo() -> bool:
    """Return True when DEMO_MODE is truthy in secrets or env vars."""
    # Check Streamlit secrets first (works on Community Cloud)
    try:
        val = st.secrets.get("DEMO_MODE", "")
    except Exception:
        val = ""
    if str(val).lower() in ("1", "true", "yes"):
        return True
    # Fallback to OS env var (useful for local testing)
    return os.environ.get("DEMO_MODE", "").lower() in ("1", "true", "yes")


def demo_banner():
    """Render a visible banner at the top of the page in demo mode."""
    st.info(
        "🎭 **Demo mode** — all data shown is entirely synthetic. "
        "No real financial information is used.",
        icon="ℹ️",
    )


def demo_data_path() -> Path:
    """Return the path to the bundled synthetic CSV."""
    return Path("data") / "demo_transactions.csv"


def demo_model_dir() -> Path:
    """Return the models/ directory path (used to guard writes)."""
    return Path("models")
