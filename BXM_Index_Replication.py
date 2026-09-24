"""
BXM Index Replication

Reads the supplied BXM input workbook and calculates the daily BXM index level.

Methodology implemented:

Non-roll date:
    1 + R_t = (S_t + Div_t - C_t) / (S_{t-1} - C_{t-1})

Roll date:
    1 + R_t = (1 + R_a)(1 + R_b)(1 + R_c)

where:

    R_a = (SSOQ_t + Div_t - CSettle) / (S_{t-1} - C_{t-1}) - 1
    R_b = SVWAV / SSOQ_t - 1
    R_c = (S_t - C_t) / (SVWAV - CVWAP) - 1

The input workbook is expected to contain:

date, expr_Date, spx_10am, soq, settle, k, vwap, spx_vwap,
spx_close, div, bid, ask, mid, retA, retB, retC, ret, Index close
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
import argparse

import pandas as pd


ROLL_WEEKDAY = 4  # Friday
INITIAL_BXM_CLOSE = 2517.98  # 2026-08-20 anchor


def _as_number(value):
    """Convert a value to float, returning None for invalid/missing values."""
    if pd.isna(value) or isinstance(value, str):
        return None
    return float(value)


def _third_friday(year: int, month: int) -> date:
    """Return the third Friday of a given month."""
    year = int(year)
    month = int(month)

    first = date(year, month, 1)

    days_to_friday = (ROLL_WEEKDAY - first.weekday()) % 7

    return first.fromordinal(
        first.toordinal() + days_to_friday + 14
    )


def _roll_date(
    year: int,
    month: int,
    business_days: set[date] | None = None,
) -> date:
    """
    Return the third Friday of the month, moved to the preceding
    business day if the Friday is an exchange holiday.
    """

    d = _third_friday(year, month)

    business_days = business_days or set()

    if business_days and d not in business_days:
        while d not in business_days:
            d = date.fromordinal(d.toordinal() - 1)

    return d


def calculate_bxm(
    input_file: str | Path,
    output_file: str | Path,
    initial_index_level: float = INITIAL_BXM_CLOSE,
) -> pd.DataFrame:
    """
    Calculate the BXM index replication from the supplied input workbook.

    Parameters
    ----------
    input_file:
        Path to the input Excel workbook.

    output_file:
        Path where the calculated replication workbook will be written.

    initial_index_level:
        Starting BXM index level used as the anchor for the first row.

    Returns
    -------
    pd.DataFrame
        DataFrame containing the input data and calculated BXM returns
        and index levels.
    """

    # ---------------------------------------------------------
    # Read input workbook
    # ---------------------------------------------------------

    df = pd.read_excel(input_file)

    required = {
        "date",
        "spx_10am",
        "soq",
        "settle",
        "k",
        "vwap",
        "spx_vwap",
        "spx_close",
        "div",
        "bid",
        "ask",
        "mid",
    }

    missing = required.difference(df.columns)

    if missing:
        raise ValueError(
            f"Missing required columns: {sorted(missing)}"
        )

    # ---------------------------------------------------------
    # Clean and sort dates
    # ---------------------------------------------------------

    df["date"] = pd.to_datetime(
        df["date"],
        errors="coerce",
    )

    df = (
        df.dropna(subset=["date"])
        .sort_values("date")
        .reset_index(drop=True)
    )

    # ---------------------------------------------------------
    # Initialize output columns
    # ---------------------------------------------------------

    df["expr_date"] = pd.NaT
    df["expr_date"] = pd.to_datetime(df["expr_date"])

    df["retA"] = pd.NA
    df["retB"] = pd.NA
    df["retC"] = pd.NA
    df["ret"] = pd.NA
    df["Index close"] = pd.NA

    # ---------------------------------------------------------
    # Determine option expiration attached to each row
    # ---------------------------------------------------------

    for i, timestamp in enumerate(df["date"]):

        current_date = timestamp.date()

        year = int(current_date.year)
        month = int(current_date.month)

        this_roll = _third_friday(year, month)

        if current_date <= this_roll:
            expiry = this_roll
        else:
            if month == 12:
                expiry = _third_friday(year + 1, 1)
            else:
                expiry = _third_friday(year, month + 1)

        df.at[i, "expr_date"] = pd.Timestamp(expiry)

    # ---------------------------------------------------------
    # Initialize index
    # ---------------------------------------------------------

    index_level = float(initial_index_level)

    # First row is the supplied index anchor
    if len(df):
        df.at[0, "ret"] = 0.0
        df.at[0, "Index close"] = index_level

    # ---------------------------------------------------------
    # Calculate daily returns
    # ---------------------------------------------------------

    for i in range(1, len(df)):

        prev = df.iloc[i - 1]
        row = df.iloc[i]

        prev_spx = _as_number(prev["spx_close"])
        prev_mid = _as_number(prev["mid"])

        spx_close = _as_number(row["spx_close"])
        mid = _as_number(row["mid"])

        div = _as_number(row["div"]) or 0.0

        # -----------------------------------------------------
        # Determine whether this is a roll date
        # -----------------------------------------------------

        roll_fields = ["soq", "settle", "vwap", "spx_vwap"]

        is_roll = all(
            pd.notna(row[col])
            and str(row[col]).strip().upper() != "NA"
            for col in roll_fields
        )

        # -----------------------------------------------------
        # Roll calculation
        # -----------------------------------------------------

        if is_roll:

            soq = _as_number(row["soq"])
            settle = _as_number(row["settle"])
            vwap = _as_number(row["vwap"])
            spx_vwap = _as_number(row["spx_vwap"])

            if None in (
                prev_spx,
                prev_mid,
                soq,
                settle,
                vwap,
                spx_vwap,
                spx_close,
                mid,
            ):
                raise ValueError(
                    f"Missing numeric value required for roll calculation "
                    f"on {row['date'].date()}"
                )

            ra = (
                (soq + div - settle)
                / (prev_spx - prev_mid)
                - 1.0
            )

            rb = (
                spx_vwap / soq
                - 1.0
            )

            rc = (
                (spx_close - mid)
                / (spx_vwap - vwap)
                - 1.0
            )

            ret = (
                (1.0 + ra)
                * (1.0 + rb)
                * (1.0 + rc)
                - 1.0
            )

            df.at[i, "retA"] = ra
            df.at[i, "retB"] = rb
            df.at[i, "retC"] = rc

        # -----------------------------------------------------
        # Non-roll calculation
        # -----------------------------------------------------

        else:

            if None in (
                prev_spx,
                prev_mid,
                spx_close,
                mid,
            ):
                raise ValueError(
                    f"Missing numeric value required for return calculation "
                    f"on {row['date'].date()}"
                )

            ret = (
                (spx_close + div - mid)
                / (prev_spx - prev_mid)
                - 1.0
            )

        # -----------------------------------------------------
        # Update index
        # -----------------------------------------------------

        index_level *= 1.0 + ret

        df.at[i, "ret"] = ret
        df.at[i, "Index close"] = index_level

    # ---------------------------------------------------------
    # Write output workbook
    # ---------------------------------------------------------

    df.to_excel(
        output_file,
        index=False,
    )

    return df


# =============================================================
# Main
# =============================================================

if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description="Replicate the BXM index from an input Excel workbook."
    )

    parser.add_argument(
        "--input",
        default="BXM.xlsx",
        help="Path to the BXM input workbook.",
    )

    parser.add_argument(
        "--output",
        default="BXM_replication_output.xlsx",
        help="Path for the replication output workbook.",
    )

    parser.add_argument(
        "--initial-index",
        type=float,
        default=INITIAL_BXM_CLOSE,
        help="Initial BXM index level.",
    )

    args = parser.parse_args()

    result = calculate_bxm(
        input_file=args.input,
        output_file=args.output,
        initial_index_level=args.initial_index,
    )

    print(
        result[
            ["date", "expr_date", "ret", "Index close"]
        ].to_string(index=False)
    )