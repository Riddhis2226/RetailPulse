"""
RetailPulse — Data Cleaning
===========================

Applies conservative, reusable cleaning to RetailPulse datasets.

Responsibilities:
1. Trim leading and trailing whitespace from text columns.
2. Convert configured date columns to datetime values.
3. Preserve missing values without arbitrary imputation.
4. Preserve all rows and columns.
5. Avoid modifying the original DataFrame.

Important:
- Invalid date values are converted to NaT and counted in the
  cleaning report.
- Existing missing values are not automatically filled.
- No records are deleted.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pandas as pd


# ============================================================
# CONFIGURATION
# ============================================================

DATE_COLUMNS: dict[str, list[str]] = {
    "customer_master.csv": ["registration_date"],
    "inventory_snapshot.csv": ["last_restock_date"],
    "promotions.csv": ["start_date", "end_date"],
    "sales_transactions.csv": ["date"],
    "sku_inventory_flags.csv": ["window_start", "window_end"],
    "sku_master.csv": [],
    "store_master.csv": ["opening_date"],
}

logger = logging.getLogger("retailpulse.cleaning")


# ============================================================
# CLEANING
# ============================================================

def clean_dataframe(
    df: pd.DataFrame,
    filename: str,
) -> pd.DataFrame:
    """
    Clean a DataFrame conservatively.

    Args:
        df: Source DataFrame.
        filename: Dataset filename, such as 'customer_master.csv'.

    Returns:
        A cleaned copy of the input DataFrame.

    Notes:
        - Does not delete rows or columns.
        - Does not impute missing values.
        - Converts invalid configured date values to NaT.
        - Logs changes to text and date columns.
    """

    if not isinstance(df, pd.DataFrame):
        raise TypeError(
            f"Expected pandas DataFrame, received {type(df).__name__}."
        )

    if not isinstance(filename, str) or not filename.strip():
        raise ValueError("filename must be a non-empty string.")

    # Support both a filename and a full path.
    dataset_name = Path(filename).name

    cleaned_df = df.copy(deep=True)

    original_rows = len(cleaned_df)
    original_columns = list(cleaned_df.columns)

    logger.info(
        "Cleaning %s: %s rows, %s columns",
        dataset_name,
        f"{original_rows:,}",
        len(original_columns),
    )

    # --------------------------------------------------------
    # 1. NORMALIZE TEXT WHITESPACE
    # --------------------------------------------------------

    text_columns = cleaned_df.select_dtypes(
        include=["object", "string"]
    ).columns

    for column in text_columns:
        try:
            cleaned_df[column] = cleaned_df[column].str.strip()
        except (AttributeError, TypeError) as exc:
            logger.warning(
                "Could not normalize text column '%s' in %s: %s",
                column,
                dataset_name,
                exc,
            )

    # --------------------------------------------------------
    # 2. CONVERT CONFIGURED DATE COLUMNS
    # --------------------------------------------------------

    configured_dates = DATE_COLUMNS.get(dataset_name, [])

    for column in configured_dates:
        if column not in cleaned_df.columns:
            logger.warning(
                "Configured date column '%s' is missing from %s.",
                column,
                dataset_name,
            )
            continue

        original_non_null = cleaned_df[column].notna()

        converted = pd.to_datetime(
            cleaned_df[column],
            errors="coerce",
        )

        # Count non-null source values that became NaT.
        invalid_dates = int(
            (original_non_null & converted.isna()).sum()
        )

        cleaned_df[column] = converted

        if invalid_dates:
            logger.warning(
                "%s: %s invalid date value(s) converted to NaT "
                "in column '%s'.",
                dataset_name,
                f"{invalid_dates:,}",
                column,
            )
        else:
            logger.info(
                "%s: converted date column '%s'.",
                dataset_name,
                column,
            )

    # --------------------------------------------------------
    # 3. VERIFY STRUCTURAL INTEGRITY
    # --------------------------------------------------------

    if len(cleaned_df) != original_rows:
        raise RuntimeError(
            f"Row count changed while cleaning {dataset_name}: "
            f"{original_rows} -> {len(cleaned_df)}."
        )

    if list(cleaned_df.columns) != original_columns:
        raise RuntimeError(
            f"Column structure changed while cleaning {dataset_name}."
        )

    logger.info(
        "Cleaning completed for %s. No rows were deleted.",
        dataset_name,
    )

    return cleaned_df


# ============================================================
# OPTIONAL CLEANING SUMMARY
# ============================================================

def get_cleaning_summary(
    original_df: pd.DataFrame,
    cleaned_df: pd.DataFrame,
    filename: str,
) -> dict[str, Any]:
    """
    Summarize the input and output DataFrames.

    This function reports structural changes and missing-value counts.
    It does not modify either DataFrame.
    """

    if not isinstance(original_df, pd.DataFrame):
        raise TypeError("original_df must be a pandas DataFrame.")

    if not isinstance(cleaned_df, pd.DataFrame):
        raise TypeError("cleaned_df must be a pandas DataFrame.")

    original_missing = int(original_df.isna().sum().sum())
    cleaned_missing = int(cleaned_df.isna().sum().sum())

    return {
        "dataset": Path(filename).name,
        "original_rows": len(original_df),
        "cleaned_rows": len(cleaned_df),
        "rows_deleted": len(original_df) - len(cleaned_df),
        "original_columns": len(original_df.columns),
        "cleaned_columns": len(cleaned_df.columns),
        "original_missing_cells": original_missing,
        "cleaned_missing_cells": cleaned_missing,
        "row_count_preserved": len(original_df) == len(cleaned_df),
        "column_names_preserved": (
            list(original_df.columns) == list(cleaned_df.columns)
        ),
    } 