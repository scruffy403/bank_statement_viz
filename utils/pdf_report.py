# utils/pdf_report.py
from __future__ import annotations

from io import BytesIO

import pandas as pd
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas


def generate_monthly_report_pdf(df: pd.DataFrame) -> bytes:
    """
    Simple 1-page summary PDF: totals + top categories.
    """
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4

    c.setTitle("Monthly Finance Report")

    y = height - 30 * mm
    c.setFont("Helvetica-Bold", 16)
    c.drawString(20 * mm, y, "Monthly Finance Report")

    y -= 15 * mm
    c.setFont("Helvetica", 10)

    if not df.empty:
        total_out = df["Paid out"].sum()
        total_in = df["Paid in"].sum()
        net = df["Net"].sum()

        c.drawString(20 * mm, y, f"Total Paid Out: £{total_out:,.2f}")
        y -= 6 * mm
        c.drawString(20 * mm, y, f"Total Paid In:  £{total_in:,.2f}")
        y -= 6 * mm
        c.drawString(20 * mm, y, f"Net:            £{net:,.2f}")
        y -= 10 * mm

        if "Category" in df.columns:
            cat_spend = (
                df.groupby("Category")["Paid out"]
                .sum()
                .sort_values(ascending=False)
                .head(10)
                .reset_index()
            )
            c.setFont("Helvetica-Bold", 12)
            c.drawString(20 * mm, y, "Top Categories by Spend")
            y -= 8 * mm
            c.setFont("Helvetica", 10)
            for _, row in cat_spend.iterrows():
                c.drawString(
                    22 * mm,
                    y,
                    f"{row['Category']}: £{row['Paid out']:,.2f}",
                )
                y -= 6 * mm
                if y < 20 * mm:
                    break
    else:
        c.drawString(20 * mm, y, "No data available for this period.")

    c.showPage()
    c.save()
    buf.seek(0)
    return buf.read()