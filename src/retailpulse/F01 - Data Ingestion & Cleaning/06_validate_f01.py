"""
RetailPulse — F01 Data Validation
=================================

Location:
    src/retailpulse/f01_data_pipeline/validate_f01.py

Run from repository root:
    $env:PYTHONPATH = "$PWD\\src"
    .venv\\Scripts\\python.exe -m retailpulse.f01_data_pipeline.validate_f01

Inputs:
    data/raw/*.csv
    data/processed/*.parquet
    data/processed/sales_transactions/part-*.parquet

Outputs:
    reports/f01_validation_report.json
    reports/f01_validation_summary.txt
"""

from __future__ import annotations

import json
import logging
import math
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow.parquet as pq


# ============================================================
# CONFIGURATION
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[3]

RAW_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
REPORT_DIR = PROJECT_ROOT / "reports"

JSON_REPORT = REPORT_DIR / "f01_validation_report.json"
TEXT_REPORT = REPORT_DIR / "f01_validation_summary.txt"

CHUNK_SIZE = 100_000
MONETARY_TOLERANCE = 0.011


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)

logger = logging.getLogger("retailpulse.f01.validation")


# ============================================================
# REQUIRED COLUMNS
# ============================================================

REQUIRED_COLUMNS = {
    "customer_master": {
        "cust_id",
        "registration_date",
    },
    "inventory_snapshot": {
        "store_id",
        "sku_id",
        "stock_on_hand",
        "reorder_point",
        "safety_stock",
    },
    "promotions": {
        "promo_id",
        "start_date",
        "end_date",
        "discount_pct",
    },
    "sales_transactions": {
        "date",
        "receipt_id",
        "store_id",
        "sku_id",
        "customer_id",
        "quantity",
        "unit_price",
        "total_value",
        "discount_pct",
    },
    "sku_inventory_flags": {
        "sku_id",
        "flag",
        "affected_stores",
    },
    "sku_master": {
        "sku_id",
        "unit_price",
        "cost_price",
    },
    "store_master": {
        "store_id",
        "city",
        "opening_date",
    },
}


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def normalize_identifier(series: pd.Series) -> pd.Series:
    """Normalize identifiers for comparisons without modifying source data."""

    normalized = series.astype("string").str.strip()

    missing_markers = {
        "",
        "nan",
        "none",
        "null",
        "<na>",
    }

    return normalized.mask(
        normalized.str.lower().isin(missing_markers)
    )


def numeric_series(series: pd.Series) -> pd.Series:
    """Convert a Series to numeric values, coercing invalid entries to NaN."""

    return pd.to_numeric(series, errors="coerce")


def finite_mask(series: pd.Series) -> pd.Series:
    """Return True for finite, non-null numeric values."""

    numeric = numeric_series(series)

    return numeric.notna() & numeric.map(
        lambda value: math.isfinite(float(value))
        if pd.notna(value)
        else False
    )


def add_check(
    results: list[dict[str, Any]],
    name: str,
    passed: bool,
    details: Any,
) -> None:
    """Append a consistently structured validation result."""

    results.append(
        {
            "check": name,
            "passed": bool(passed),
            "details": details,
        }
    )


# ============================================================
# REQUIRED COLUMN VALIDATION
# ============================================================

def check_required_columns() -> list[dict[str, Any]]:
    """Check required columns in raw CSVs and processed Parquet files."""

    results = []

    logger.info("Checking required columns.")

    for name, required in REQUIRED_COLUMNS.items():
        raw_path = RAW_DIR / f"{name}.csv"

        if name == "sales_transactions":
            processed_path = (
                PROCESSED_DIR
                / "sales_transactions"
                / "part-00000.parquet"
            )
        else:
            processed_path = PROCESSED_DIR / f"{name}.parquet"

        # ----------------------------------------------------
        # Raw dataset
        # ----------------------------------------------------

        if not raw_path.is_file():
            add_check(
                results,
                f"{name}: raw file exists",
                False,
                str(raw_path),
            )

            raw_missing = sorted(required)

        else:
            try:
                raw_columns = set(
                    pd.read_csv(
                        raw_path,
                        nrows=0,
                    ).columns
                )

                raw_missing = sorted(
                    required - raw_columns
                )

                add_check(
                    results,
                    f"{name}: raw required columns",
                    not raw_missing,
                    {
                        "file": str(raw_path),
                        "missing_columns": raw_missing,
                    },
                )

            except Exception as exc:
                raw_missing = sorted(required)

                add_check(
                    results,
                    f"{name}: raw required columns",
                    False,
                    {
                        "file": str(raw_path),
                        "error": f"{type(exc).__name__}: {exc}",
                    },
                )

        # ----------------------------------------------------
        # Processed dataset
        # ----------------------------------------------------

        if name == "sales_transactions":
            processed_files = sorted(
                (
                    PROCESSED_DIR / "sales_transactions"
                ).glob("part-*.parquet")
            )

            if not processed_files:
                add_check(
                    results,
                    f"{name}: processed files exist",
                    False,
                    "No processed sales Parquet parts were found.",
                )
                continue

            missing_by_file = {}

            for path in processed_files:
                try:
                    processed_columns = set(
                        pq.read_schema(path).names
                    )

                    missing = sorted(
                        required - processed_columns
                    )

                    if missing:
                        missing_by_file[path.name] = missing

                except Exception as exc:
                    missing_by_file[path.name] = [
                        f"Unable to read schema: {type(exc).__name__}: {exc}"
                    ]

            add_check(
                results,
                f"{name}: processed required columns",
                not missing_by_file,
                {
                    "files_checked": len(processed_files),
                    "files_with_missing_columns": missing_by_file,
                },
            )

        else:
            if not processed_path.is_file():
                add_check(
                    results,
                    f"{name}: processed file exists",
                    False,
                    str(processed_path),
                )
                continue

            try:
                processed_columns = set(
                    pq.read_schema(processed_path).names
                )

                processed_missing = sorted(
                    required - processed_columns
                )

                add_check(
                    results,
                    f"{name}: processed required columns",
                    not processed_missing,
                    {
                        "file": str(processed_path),
                        "missing_columns": processed_missing,
                    },
                )

            except Exception as exc:
                add_check(
                    results,
                    f"{name}: processed required columns",
                    False,
                    {
                        "file": str(processed_path),
                        "error": f"{type(exc).__name__}: {exc}",
                    },
                )

    return results


# ============================================================
# MASTER KEY VALIDATION
# ============================================================

def check_unique_master_keys() -> list[dict[str, Any]]:
    """Check master-table primary keys and inventory store-SKU pairs."""

    results = []

    tables = {
        "customer_master": ["cust_id"],
        "sku_master": ["sku_id"],
        "store_master": ["store_id"],
        "promotions": ["promo_id"],
    }

    logger.info("Checking master-table key uniqueness.")

    for table, keys in tables.items():
        path = PROCESSED_DIR / f"{table}.parquet"

        if not path.is_file():
            add_check(
                results,
                f"{table}: unique keys",
                False,
                f"Processed dataset not found: {path}",
            )
            continue

        try:
            df = pd.read_parquet(
                path,
                columns=keys,
            )

            normalized = pd.DataFrame(
                {
                    column: normalize_identifier(df[column])
                    for column in keys
                }
            )

            missing_key_rows = int(
                normalized.isna().any(axis=1).sum()
            )

            duplicate_rows = int(
                normalized.dropna(
                    subset=keys
                ).duplicated(
                    subset=keys
                ).sum()
            )

            passed = (
                missing_key_rows == 0
                and duplicate_rows == 0
            )

            add_check(
                results,
                f"{table}: unique keys",
                passed,
                {
                    "key_columns": keys,
                    "row_count": len(df),
                    "missing_key_rows": missing_key_rows,
                    "duplicate_rows": duplicate_rows,
                },
            )

        except Exception as exc:
            add_check(
                results,
                f"{table}: unique keys",
                False,
                f"{type(exc).__name__}: {exc}",
            )

    # Inventory should have one row per store-SKU combination.
    inventory_path = (
        PROCESSED_DIR / "inventory_snapshot.parquet"
    )

    if not inventory_path.is_file():
        add_check(
            results,
            "inventory_snapshot: unique store-SKU pairs",
            False,
            f"Processed dataset not found: {inventory_path}",
        )

    else:
        try:
            inventory = pd.read_parquet(
                inventory_path,
                columns=["store_id", "sku_id"],
            )

            normalized = pd.DataFrame(
                {
                    "store_id": normalize_identifier(
                        inventory["store_id"]
                    ),
                    "sku_id": normalize_identifier(
                        inventory["sku_id"]
                    ),
                }
            )

            missing_key_rows = int(
                normalized.isna().any(axis=1).sum()
            )

            duplicate_pairs = int(
                normalized.dropna(
                    subset=["store_id", "sku_id"]
                ).duplicated(
                    subset=["store_id", "sku_id"]
                ).sum()
            )

            add_check(
                results,
                "inventory_snapshot: unique store-SKU pairs",
                missing_key_rows == 0 and duplicate_pairs == 0,
                {
                    "row_count": len(inventory),
                    "missing_key_rows": missing_key_rows,
                    "duplicate_pairs": duplicate_pairs,
                },
            )

        except Exception as exc:
            add_check(
                results,
                "inventory_snapshot: unique store-SKU pairs",
                False,
                f"{type(exc).__name__}: {exc}",
            )

    return results


# ============================================================
# SALES BUSINESS RULE VALIDATION
# ============================================================

def check_sales_business_rules() -> list[dict[str, Any]]:
    """Validate sales values in batches across all Parquet parts."""

    sales_dir = PROCESSED_DIR / "sales_transactions"

    parquet_files = sorted(
        sales_dir.glob("part-*.parquet")
    )

    if not parquet_files:
        return [
            {
                "check": "sales business rules",
                "passed": False,
                "details": "No processed sales Parquet files found.",
            }
        ]

    results = {
        "files_checked": 0,
        "rows_checked": 0,
        "invalid_quantity": 0,
        "invalid_unit_price": 0,
        "invalid_total_value": 0,
        "invalid_discount_pct": 0,
        "invalid_or_missing_dates": 0,
        "discount_formula_mismatches": 0,
        "rows_with_invalid_numeric_values": 0,
    }

    columns = [
        "date",
        "quantity",
        "unit_price",
        "total_value",
        "discount_pct",
    ]

    logger.info(
        "Checking sales business rules across %s files.",
        f"{len(parquet_files):,}",
    )

    for file_index, path in enumerate(parquet_files, start=1):
        parquet_file = pq.ParquetFile(path)

        missing_columns = sorted(
            set(columns) - set(parquet_file.schema.names)
        )

        if missing_columns:
            return [
                {
                    "check": "sales business rules",
                    "passed": False,
                    "details": {
                        "file": path.name,
                        "missing_columns": missing_columns,
                    },
                }
            ]

        results["files_checked"] += 1

        # Iterate over actual Parquet row groups rather than loading
        # the complete part into memory.
        for batch in parquet_file.iter_batches(
            batch_size=CHUNK_SIZE,
            columns=columns,
        ):
            df = batch.to_pandas()

            results["rows_checked"] += len(df)

            quantity = numeric_series(df["quantity"])
            unit_price = numeric_series(df["unit_price"])
            total_value = numeric_series(df["total_value"])
            discount_pct = numeric_series(df["discount_pct"])

            quantity_finite = finite_mask(quantity)
            price_finite = finite_mask(unit_price)
            total_finite = finite_mask(total_value)
            discount_finite = finite_mask(discount_pct)

            # ------------------------------------------------
            # Quantity
            # ------------------------------------------------

            results["invalid_quantity"] += int(
                (
                    ~quantity_finite
                    | (quantity <= 0).fillna(False)
                ).sum()
            )

            # ------------------------------------------------
            # Unit price
            # ------------------------------------------------

            results["invalid_unit_price"] += int(
                (
                    ~price_finite
                    | (unit_price < 0).fillna(False)
                ).sum()
            )

            # ------------------------------------------------
            # Total value
            # ------------------------------------------------

            results["invalid_total_value"] += int(
                (
                    ~total_finite
                    | (total_value < 0).fillna(False)
                ).sum()
            )

            # ------------------------------------------------
            # Discount percentage
            # ------------------------------------------------

            results["invalid_discount_pct"] += int(
                (
                    ~discount_finite
                    | (discount_pct < 0).fillna(False)
                    | (discount_pct > 100).fillna(False)
                ).sum()
            )

            # ------------------------------------------------
            # Transaction date
            # ------------------------------------------------

            parsed_dates = pd.to_datetime(
                df["date"],
                errors="coerce",
            )

            results["invalid_or_missing_dates"] += int(
                parsed_dates.isna().sum()
            )

            # ------------------------------------------------
            # Discount formula
            # ------------------------------------------------

            valid_pricing = (
                quantity_finite
                & price_finite
                & total_finite
                & discount_finite
                & (quantity > 0)
                & (unit_price >= 0)
                & (total_value >= 0)
                & (discount_pct >= 0)
                & (discount_pct <= 100)
            )

            expected_total = (
                quantity
                * unit_price
                * (1 - discount_pct / 100)
            ).round(2)

            mismatch = (
                valid_pricing
                & (
                    (expected_total - total_value).abs()
                    > MONETARY_TOLERANCE
                )
            )

            results["discount_formula_mismatches"] += int(
                mismatch.sum()
            )

            results["rows_with_invalid_numeric_values"] += int(
                (
                    ~quantity_finite
                    | ~price_finite
                    | ~total_finite
                    | ~discount_finite
                ).sum()
            )

        logger.info(
            "Checked sales file %s/%s: %s",
            file_index,
            len(parquet_files),
            path.name,
        )

    invalid_fields = [
        "invalid_quantity",
        "invalid_unit_price",
        "invalid_total_value",
        "invalid_discount_pct",
        "invalid_or_missing_dates",
        "discount_formula_mismatches",
    ]

    passed = all(
        results[key] == 0
        for key in invalid_fields
    )

    return [
        {
            "check": "sales business rules",
            "passed": passed,
            "details": results,
        }
    ]


# ============================================================
# REPORT GENERATION
# ============================================================

def write_reports(
    checks: list[dict[str, Any]],
    elapsed_seconds: float,
    status: str,
    errors: list[str],
) -> None:
    """Save JSON and plain-text validation reports."""

    REPORT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    passed_count = sum(
        1 for item in checks if item["passed"]
    )

    failed_count = len(checks) - passed_count

    report = {
        "project": "RetailPulse",
        "validation_type": "F01 Data Validation",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "overall_status": status,
        "checks_passed": passed_count,
        "checks_failed": failed_count,
        "elapsed_seconds": elapsed_seconds,
        "checks": checks,
        "errors": errors,
    }

    JSON_REPORT.write_text(
        json.dumps(
            report,
            indent=2,
            ensure_ascii=False,
            default=str,
        )
        + "\n",
        encoding="utf-8",
    )

    lines = [
        "RetailPulse — F01 Data Validation",
        "=" * 65,
        f"Generated at UTC: {report['generated_at_utc']}",
        f"Overall status: {status}",
        f"Checks passed: {passed_count}",
        f"Checks failed: {failed_count}",
        f"Elapsed seconds: {elapsed_seconds}",
        "",
        "VALIDATION RESULTS",
        "-" * 65,
    ]

    for item in checks:
        check_status = "PASS" if item["passed"] else "FAIL"

        lines.append(
            f"[{check_status}] {item['check']}"
        )

        lines.append(
            f"Details: {json.dumps(item['details'], default=str)}"
        )

    if errors:
        lines.extend(
            [
                "",
                "ERRORS",
                "-" * 65,
            ]
        )

        lines.extend(
            f"- {error}"
            for error in errors
        )

    TEXT_REPORT.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


# ============================================================
# MAIN
# ============================================================

def main() -> int:
    """Run F01 validation checks and save reports."""

    started = time.perf_counter()

    checks: list[dict[str, Any]] = []
    errors: list[str] = []

    logger.info("=" * 65)
    logger.info("RETAILPULSE — F01 DATA VALIDATION")
    logger.info("=" * 65)

    try:
        checks.extend(check_required_columns())
        checks.extend(check_unique_master_keys())
        checks.extend(check_sales_business_rules())

    except Exception as exc:
        logger.exception("F01 validation execution failed.")

        errors.append(
            f"{type(exc).__name__}: {exc}"
        )

    passed_count = sum(
        1 for item in checks if item["passed"]
    )

    failed_count = len(checks) - passed_count

    status = (
        "ERROR"
        if errors
        else "PASS"
        if failed_count == 0
        else "FAIL"
    )

    elapsed_seconds = round(
        time.perf_counter() - started,
        2,
    )

    print("\n" + "=" * 65)
    print("RETAILPULSE — F01 DATA VALIDATION")
    print("=" * 65)

    for item in checks:
        check_status = "PASS" if item["passed"] else "FAIL"

        print(
            f"[{check_status}] {item['check']}"
        )

        if not item["passed"]:
            print(f"       Details: {item['details']}")

    for error in errors:
        print(f"[ERROR] {error}")

    print("=" * 65)
    print(f"Checks passed: {passed_count}")
    print(f"Checks failed: {failed_count}")
    print(f"Overall status: {status}")
    print(f"Elapsed seconds: {elapsed_seconds}")
    print("=" * 65)

    try:
        write_reports(
            checks=checks,
            elapsed_seconds=elapsed_seconds,
            status=status,
            errors=errors,
        )

        logger.info("JSON report saved to: %s", JSON_REPORT)
        logger.info("Text report saved to: %s", TEXT_REPORT)

    except Exception:
        logger.exception("Unable to save validation reports.")
        return 1

    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main()) 