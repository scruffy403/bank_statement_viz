# utils/loader.py
from __future__ import annotations

import chardet
import streamlit as st
from pathlib import Path

import pandas as pd


def detect_encoding(path):
    """Detects encoding using chardet."""
    with open(path, "rb") as f:
        raw = f.read(50_000)
    result = chardet.detect(raw)
    return result["encoding"] or "utf-8"


def find_header_row(path: Path, encoding: str) -> int | None:
    """
    Return the row index of the first real header line.
    Recognised when the first column (stripped of quotes/whitespace) == 'date'.
    """
    with open(path, "r", encoding=encoding, errors="replace") as f:
        for i, line in enumerate(f):
            cols = [c.strip() for c in line.split(",")]
            if not cols:
                continue
            first = cols[0].strip().strip('"').strip("'").strip()
            if first.lower() == "date":
                return i
    return None


def load_bank_csv(path: Path) -> pd.DataFrame:
    """
    Loads bank CSVs that contain metadata rows before the actual header.
    Handles Windows-1252 pound symbols and auto-detects encoding.
    """
    encoding = detect_encoding(path)

    try:
        header_row = find_header_row(path, encoding)
    except UnicodeDecodeError:
        encoding = "cp1252"
        header_row = find_header_row(path, encoding)

    df = pd.read_csv(
        path,
        skiprows=range(header_row),
        encoding=encoding,
        quotechar='"',
        thousands=",",
        na_values=["", " "],
        engine="python",
    )
    df.columns = [col.strip() for col in df.columns]
    return df


def choose_data_source(uploaded_file):
    """
    Data-source resolution order:

    1. Demo mode  → always returns the bundled synthetic CSV; no uploader shown.
    2. Uploaded   → user's file via the sidebar uploader.
    3. data/*.csv → first CSV found in the data/ folder (original behaviour).
    4. None       → caller is responsible for calling st.stop().

    Import is deferred inside the function to avoid a circular import at
    module load time (demo_mode imports streamlit; loader is imported early).
    """
    from utils.demo_mode import is_demo, demo_data_path  # deferred

    if is_demo():
        path = demo_data_path()
        if path.exists():
            return path
        st.error(
            f"Demo mode is active but the demo CSV was not found at `{path}`. "
            "Run `python scripts/generate_demo_data.py` to generate it."
        )
        st.stop()

    # Normal (non-demo) path
    if uploaded_file is not None:
        temp_path = Path("uploaded_bank_data.csv")
        temp_path.write_bytes(uploaded_file.getvalue())
        return temp_path

    data_dir = Path("data")
    if data_dir.exists():
        csvs = list(data_dir.glob("*.csv"))
        if csvs:
            return csvs[0]

    st.warning("No CSV found. Upload a file or place one in the data/ folder.")
    return None
