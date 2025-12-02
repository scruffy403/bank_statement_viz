# utils/loader.py
from __future__ import annotations

import pandas as pd
import chardet
from pathlib import Path
import streamlit as st



def detect_encoding(path):
    """Detects encoding using chardet."""
    with open(path, "rb") as f:
        raw = f.read(50000)  # sample
    result = chardet.detect(raw)
    return result["encoding"] or "utf-8"


def find_header_row(path: Path, encoding: str) -> int | None:
    """
    Return the row index of the first real header line.
    A header line is recognized if the first column, after stripping quotes/whitespace,
    equals 'Date' (case insensitive).
    """
    with open(path, "r", encoding=encoding, errors="replace") as f:
        for i, line in enumerate(f):
            # split CSV row
            cols = [c.strip() for c in line.split(",")]

            if not cols:
                continue

            first = cols[0].strip().strip('"').strip("'").strip()

            # check for header match
            if first.lower() == "date":
                return i

    return None


def load_bank_csv(path):
    """
    Loads bank CSVs that contain metadata rows before the actual header.
    Handles Windows-1252 pound symbols and auto-detects encoding.
    """

    # Detect encoding
    encoding = detect_encoding(path)

    # Try reading the first few lines with fallback encoding
    try:
        header_row = find_header_row(path, encoding)
    except UnicodeDecodeError:
        # Try common fallback for UK banks
        encoding = "cp1252"
        header_row = find_header_row(path, encoding)

    # Now safely load with the detected encoding
    df = pd.read_csv(
        path,
        skiprows=range(header_row),
        encoding=encoding,
        quotechar='"',
        thousands=",",
        na_values=["", " "],
        engine="python",
    )

    # Clean up weird column names
    df.columns = [col.strip() for col in df.columns]

    return df

def choose_data_source(uploaded_file):
    """
    If the user uploads a CSV via Streamlit, use that.
    Otherwise look for a CSV in ./data/
    """

    # 1. Use uploaded CSV if available
    if uploaded_file is not None:
        # Convert to a temporary file path for consistent loading
        temp_path = Path("uploaded_bank_data.csv")
        temp_path.write_bytes(uploaded_file.getvalue())
        return temp_path

    # 2. Otherwise look in ./data folder
    data_dir = Path("data")
    if data_dir.exists():
        csvs = list(data_dir.glob("*.csv"))
        if csvs:
            return csvs[0]  # Pick the first CSV found

    # 3. No CSV found anywhere
    st.warning("No CSV found. Upload a file or place one in the data/ folder.")
    return None