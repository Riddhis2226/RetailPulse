"""
RetailPulse — Data Validation
=============================

Location:
    src/retailpulse/f01_data_pipeline/validate_data.py

Run from the repository root:
    $env:PYTHONPATH = "$PWD\\src"
    .venv\\Scripts\\python.exe -m retailpulse.f01_data_pipeline.validate_data

Dataset source:
    Hugging Face: RS2226/RetailPulse

Reports:
    reports/data_validation_report.json
    reports/data_validation_summary.txt

Important:
- Source datasets are not modified.
- Sales transactions are validated in chunks.
- Duplicate sales rows are counted within chunks only.
- Missing promotion IDs are allowed and are not automatically errors.
- Monetary validation compares totals against quantity, price, and discount.
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
from huggingface_hub import hf_hub_download


# ============================================================
# CONFIGURATION
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[3]

REPO_ID = "RS2226/RetailPulse"
REPO_TYPE = "dataset"

CHUNK_SIZE = 200_000

REPORT_DIR = PROJECT_ROOT / "reports"
JSON_REPORT = REPORT_DIR / "data_validation_report.json"
TEXT_REPORT = REPORT_DIR / "data_validation_summary.txt"

CUSTOMER_FILE = "customer_master.csv"
PRODUCT_FILE = "sku_master.csv"
STORE_FILE = "store_master.csv"
PROMOTION_FILE = "promotions.csv"
INVENTORY_FILE = "inventory_snapshot.csv"
SALES_FILE = "sales_transactions.csv"


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)

logger = logging.getLogger("retailpulse.f01.data_validation")


# ============================================================
# HELPERS
# ============================================================

def download_dataset(filename: str) -> Path:
    """Download or retrieve a cached dataset from Hugging Face."""

    logger.info("Retrieving dataset: %s", filename)

    path = hf_hub_download(
        repo_id=REPO_ID,
        filename=filename,
        repo_type=REPO_TYPE,
    )

    file_path = Path(path)

    if not file_path.is_file():
        raise FileNotFoundError(
            f"Dataset file not found after download: {file_path}"
        )

    return file_path


def load_small(filename: str) -> pd.DataFrame:
    """Load a reference dataset into memory."""

    path = download_dataset(filename)

    logger.info("Loading reference dataset: %s", filename)

    return pd.read_csv(path, low_memory=False)


def normalize_identifier(series: pd.Series) -> pd.Series:
    """
    Normalize identifiers for comparison without modifying source data.

    Empty strings and textual null markers are treated as missing.
    """

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


def get_identifier_set(
    df: pd.DataFrame,
    column: str,
    dataset_name: str,
) -> set[str]:
    """Validate an identifier column and return its normalized values."""

    if column not in df.columns:
        raise KeyError(
            f"Required column '{column}' is missing from {dataset_name}."
        )

    normalized = normalize_identifier(df[column])

    return set(normalized.dropna().tolist())


def require_columns(
    df: pd.DataFrame,
    required_columns: list[str],
    dataset_name: str,
) -> None:
    """Raise an informative error when required columns are missing."""

    missing = [
        column
        for column in required_columns
        if column not in df.columns
    ]

    if missing:
        raise KeyError(
            f"{dataset_name} is missing required columns: {missing}"
        )


def json_safe(value: Any) -> Any:
    """Convert common Python and Pandas values into JSON-safe values."""

    if value is None or value is pd.NA or value is pd.NaT:
        return None

    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()

    if hasattr(value, "item"):
        try:
            converted = value.item()

            if converted is not value:
                return json_safe(converted)

        except (ValueError, TypeError):
            pass

    if isinstance(value, float):
        return value if math.isfinite(value) else None

    if isinstance(value, (str, int, bool)):
        return value

    try:
        missing = pd.isna(value)

        if isinstance(missing, bool) and missing:
            return None

    except (TypeError, ValueError):
        pass

    return str(value)


def write_reports(report: dict[str, Any]) -> None:
    """Write the validation report in JSON and plain-text formats."""

    REPORT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    JSON_REPORT.write_text(
        json.dumps(
            report,
            indent=2,
            ensure_ascii=False,
            default=json_safe,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )

    lines = [
        "RetailPulse — Data Validation Summary",
        "=" * 72,
        f"Generated at UTC: {report['generated_at_utc']}",
        f"Dataset repository: {REPO_ID}",
        f"Overall status: {report['status'].upper()}",
        "",
        "REFERENCE TABLE CHECKS",
        "-" * 72,
    ]

    for name, result in report.get("reference_checks", {}).items():
        lines.append(
            f"{name}: {'PASS' if result['passed'] else 'FAIL'}"
        )

        lines.append(f"  Details: {result['details']}")

    lines.extend(
        [
            "",
            "INVENTORY CHECKS",
            "-" * 72,
        ]
    )

    for name, value in report.get("inventory_checks", {}).items():
        lines.append(f"{name}: {value}")

    lines.extend(
        [
            "",
            "SALES VALIDATION",
            "-" * 72,
        ]
    )

    for name, value in report.get("sales_checks", {}).items():
        lines.append(f"{name}: {value}")

    lines.extend(
        [
            "",
            "LIMITATIONS",
            "-" * 72,
        ]
    )

    for limitation in report.get("limitations", []):
        lines.append(f"- {limitation}")

    if report.get("errors"):
        lines.extend(
            [
                "",
                "ERRORS",
                "-" * 72,
            ]
        )

        for error in report["errors"]:
            lines.append(f"- {error}")

    lines.append("")

    TEXT_REPORT.write_text(
        "\n".join(lines),
        encoding="utf-8",
    )


# ============================================================
# REFERENCE TABLE VALIDATION
# ============================================================

def validate_reference_tables() -> dict[str, Any]:
    """Validate reference-table identifiers and inventory keys."""

    logger.info("Loading reference tables.")

    customers = load_small(CUSTOMER_FILE)
    products = load_small(PRODUCT_FILE)
    stores = load_small(STORE_FILE)
    promotions = load_small(PROMOTION_FILE)
    inventory = load_small(INVENTORY_FILE)

    require_columns(
        customers,
        ["cust_id"],
        CUSTOMER_FILE,
    )

    require_columns(
        products,
        ["sku_id"],
        PRODUCT_FILE,
    )

    require_columns(
        stores,
        ["store_id"],
        STORE_FILE,
    )

    require_columns(
        promotions,
        ["promo_id"],
        PROMOTION_FILE,
    )

    require_columns(
        inventory,
        ["store_id", "sku_id"],
        INVENTORY_FILE,
    )

    reference_tables = {
        "Customer IDs": (customers, "cust_id"),
        "SKU IDs": (products, "sku_id"),
        "Store IDs": (stores, "store_id"),
        "Promotion IDs": (promotions, "promo_id"),
    }

    reference_checks: dict[str, Any] = {}
    identifier_sets: dict[str, set[str]] = {}

    for name, (df, column) in reference_tables.items():
        normalized = normalize_identifier(df[column])

        missing_count = int(normalized.isna().sum())

        duplicate_count = int(
            normalized.dropna().duplicated().sum()
        )

        # The original uniqueness check used is_unique. This stricter
        # check also detects duplicates after identifier normalization.
        passed = (
            missing_count == 0
            and duplicate_count == 0
        )

        reference_checks[name] = {
            "passed": passed,
            "details": (
                f"rows={len(df):,}, "
                f"missing_ids={missing_count:,}, "
                f"duplicate_ids={duplicate_count:,}"
            ),
            "row_count": int(len(df)),
            "missing_ids": missing_count,
            "duplicate_ids": duplicate_count,
        }

        identifier_sets[name] = set(
            normalized.dropna().tolist()
        )

    inventory_duplicate_keys = int(
        inventory.assign(
            store_id=normalize_identifier(inventory["store_id"]),
            sku_id=normalize_identifier(inventory["sku_id"]),
        ).duplicated(
            subset=["store_id", "sku_id"]
        ).sum()
    )

    inventory_missing_keys = int(
        (
            normalize_identifier(inventory["store_id"]).isna()
            | normalize_identifier(inventory["sku_id"]).isna()
        ).sum()
    )

    inventory_checks = {
        "inventory_rows": int(len(inventory)),
        "duplicate_store_sku_combinations": inventory_duplicate_keys,
        "inventory_rows_with_missing_keys": inventory_missing_keys,
    }

    return {
        "reference_checks": reference_checks,
        "inventory_checks": inventory_checks,
        "identifier_sets": {
            "customers": get_identifier_set(
                customers,
                "cust_id",
                CUSTOMER_FILE,
            ),
            "products": get_identifier_set(
                products,
                "sku_id",
                PRODUCT_FILE,
            ),
            "stores": get_identifier_set(
                stores,
                "store_id",
                STORE_FILE,
            ),
            "promotions": get_identifier_set(
                promotions,
                "promo_id",
                PROMOTION_FILE,
            ),
        },
    }


# ============================================================
# SALES TRANSACTION VALIDATION
# ============================================================

def validate_sales_transactions(
    identifier_sets: dict[str, set[str]],
) -> dict[str, Any]:
    """Validate sales transactions in chunks."""

    sales_path = download_dataset(SALES_FILE)

    logger.info(
        "Validating sales transactions in chunks of %s rows.",
        f"{CHUNK_SIZE:,}",
    )

    total_rows = 0
    duplicate_rows_within_chunks = 0

    missing_customer_ids = 0
    unknown_customer_ids = 0

    missing_skus = 0
    unknown_skus = 0

    missing_stores = 0
    unknown_stores = 0

    missing_promotions = 0
    unknown_promotions = 0

    invalid_quantities = 0
    invalid_prices = 0
    invalid_totals = 0
    invalid_discounts = 0

    inconsistent_gross_totals = 0
    inconsistent_discounted_totals = 0

    invalid_dates = 0

    min_date: pd.Timestamp | None = None
    max_date: pd.Timestamp | None = None

    required_columns = [
        "customer_id",
        "sku_id",
        "store_id",
        "promo_id",
        "quantity",
        "unit_price",
        "total_value",
        "date",
    ]

    for chunk_number, chunk in enumerate(
        pd.read_csv(
            sales_path,
            chunksize=CHUNK_SIZE,
            low_memory=False,
        ),
        start=1,
    ):
        require_columns(
            chunk,
            required_columns,
            SALES_FILE,
        )

        total_rows += len(chunk)

        # Duplicate rows are counted within this chunk only.
        duplicate_rows_within_chunks += int(
            chunk.duplicated().sum()
        )

        # ----------------------------------------------------
        # Customer reference validation
        # ----------------------------------------------------

        customer_col = normalize_identifier(
            chunk["customer_id"]
        )

        customer_missing = customer_col.isna()

        missing_customer_ids += int(
            customer_missing.sum()
        )

        unknown_customer_ids += int(
            (
                ~customer_missing
                & ~customer_col.isin(
                    identifier_sets["customers"]
                )
            ).sum()
        )

        # ----------------------------------------------------
        # Product reference validation
        # ----------------------------------------------------

        sku_col = normalize_identifier(
            chunk["sku_id"]
        )

        sku_missing = sku_col.isna()

        missing_skus += int(sku_missing.sum())

        unknown_skus += int(
            (
                ~sku_missing
                & ~sku_col.isin(identifier_sets["products"])
            ).sum()
        )

        # ----------------------------------------------------
        # Store reference validation
        # ----------------------------------------------------

        store_col = normalize_identifier(
            chunk["store_id"]
        )

        store_missing = store_col.isna()

        missing_stores += int(store_missing.sum())

        unknown_stores += int(
            (
                ~store_missing
                & ~store_col.isin(identifier_sets["stores"])
            ).sum()
        )

        # ----------------------------------------------------
        # Promotion reference validation
        # ----------------------------------------------------

        promo_col = normalize_identifier(
            chunk["promo_id"]
        )

        promo_missing = promo_col.isna()

        missing_promotions += int(
            promo_missing.sum()
        )

        unknown_promotions += int(
            (
                ~promo_missing
                & ~promo_col.isin(identifier_sets["promotions"])
            ).sum()
        )

        # ----------------------------------------------------
        # Numeric validation
        # ----------------------------------------------------

        quantity = pd.to_numeric(
            chunk["quantity"],
            errors="coerce",
        )

        unit_price = pd.to_numeric(
            chunk["unit_price"],
            errors="coerce",
        )

        total_value = pd.to_numeric(
            chunk["total_value"],
            errors="coerce",
        )

        invalid_quantities += int(
            (
                quantity.isna()
                | ~quantity.map(
                    lambda value: (
                        pd.isna(value)
                        or math.isfinite(float(value))
                    )
                )
                | (quantity <= 0)
            ).sum()
        )

        invalid_prices += int(
            (
                unit_price.isna()
                | ~unit_price.map(
                    lambda value: (
                        pd.isna(value)
                        or math.isfinite(float(value))
                    )
                )
                | (unit_price < 0)
            ).sum()
        )

        invalid_totals += int(
            (
                total_value.isna()
                | ~total_value.map(
                    lambda value: (
                        pd.isna(value)
                        or math.isfinite(float(value))
                    )
                )
                | (total_value < 0)
            ).sum()
        )

        # ----------------------------------------------------
        # Discount validation
        # ----------------------------------------------------

        if "discount_pct" in chunk.columns:
            discount_pct = pd.to_numeric(
                chunk["discount_pct"],
                errors="coerce",
            )

            invalid_discounts += int(
                (
                    discount_pct.isna()
                    | ~discount_pct.map(
                        lambda value: (
                            pd.isna(value)
                            or math.isfinite(float(value))
                        )
                    )
                    | (discount_pct < 0)
                    | (discount_pct > 100)
                ).sum()
            )

            # Monetary comparisons are meaningful only where all
            # required numeric values are finite and valid.
            valid_money = (
                quantity.notna()
                & unit_price.notna()
                & total_value.notna()
                & discount_pct.notna()
                & quantity.map(
                    lambda value: (
                        pd.notna(value)
                        and math.isfinite(float(value))
                    )
                )
                & unit_price.map(
                    lambda value: (
                        pd.notna(value)
                        and math.isfinite(float(value))
                    )
                )
                & total_value.map(
                    lambda value: (
                        pd.notna(value)
                        and math.isfinite(float(value))
                    )
                )
                & discount_pct.map(
                    lambda value: (
                        pd.notna(value)
                        and math.isfinite(float(value))
                    )
                )
                & (quantity > 0)
                & (unit_price >= 0)
                & (total_value >= 0)
                & (discount_pct >= 0)
                & (discount_pct <= 100)
            )

            expected_discounted_total = (
                quantity
                * unit_price
                * (1 - discount_pct / 100)
            ).round(2)

            expected_gross_total = (
                quantity * unit_price
            ).round(2)

            inconsistent_gross_totals += int(
                (
                    valid_money
                    & (
                        (total_value - expected_gross_total).abs()
                        > 0.02
                    )
                ).sum()
            )

            inconsistent_discounted_totals += int(
                (
                    valid_money
                    & (
                        (
                            total_value
                            - expected_discounted_total
                        ).abs()
                        > 0.02
                    )
                ).sum()
            )

        else:
            logger.warning(
                "'discount_pct' is absent. "
                "Discounted-total validation cannot be performed."
            )

            inconsistent_gross_totals += int(
                (
                    quantity.notna()
                    & unit_price.notna()
                    & total_value.notna()
                    & (
                        (
                            total_value
                            - quantity * unit_price
                        ).abs()
                        > 0.02
                    )
                ).sum()
            )

            inconsistent_discounted_totals = -1

        # ----------------------------------------------------
        # Date validation
        # ----------------------------------------------------

        dates = pd.to_datetime(
            chunk["date"],
            errors="coerce",
        )

        invalid_dates += int(dates.isna().sum())

        valid_dates = dates.dropna()

        if not valid_dates.empty:
            chunk_min = valid_dates.min()
            chunk_max = valid_dates.max()

            min_date = (
                chunk_min
                if min_date is None
                else min(min_date, chunk_min)
            )

            max_date = (
                chunk_max
                if max_date is None
                else max(max_date, chunk_max)
            )

        if chunk_number % 10 == 0:
            logger.info(
                "Processed %s sales rows.",
                f"{total_rows:,}",
            )

    return {
        "total_sales_rows": total_rows,
        "duplicate_rows_within_chunks": duplicate_rows_within_chunks,
        "missing_customer_ids": missing_customer_ids,
        "unknown_customer_ids": unknown_customer_ids,
        "missing_sku_ids": missing_skus,
        "unknown_sku_ids": unknown_skus,
        "missing_store_ids": missing_stores,
        "unknown_store_ids": unknown_stores,
        "missing_promotion_ids": missing_promotions,
        "unknown_promotion_ids": unknown_promotions,
        "invalid_quantities": invalid_quantities,
        "invalid_unit_prices": invalid_prices,
        "invalid_total_values": invalid_totals,
        "invalid_discount_percentages": invalid_discounts,
        "inconsistent_gross_totals": inconsistent_gross_totals,
        "inconsistent_discounted_totals": inconsistent_discounted_totals,
        "invalid_dates": invalid_dates,
        "earliest_transaction_date": (
            min_date.isoformat() if min_date is not None else None
        ),
        "latest_transaction_date": (
            max_date.isoformat() if max_date is not None else None
        ),
    }


# ============================================================
# MAIN
# ============================================================

def main() -> int:
    """Run reference and sales validation, then save reports."""

    started = time.perf_counter()

    report: dict[str, Any] = {
        "project": "RetailPulse",
        "analysis": "Data validation",
        "repository_id": REPO_ID,
        "repository_type": REPO_TYPE,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "running",
        "reference_checks": {},
        "inventory_checks": {},
        "sales_checks": {},
        "limitations": [
            "Sales duplicate counts are calculated within chunks only.",
            "Duplicates spanning different chunks are not detected.",
            "Missing promotion IDs are treated as optional references.",
            "Reference identifiers are normalized for comparison only.",
            "Monetary checks use a tolerance of 0.02.",
        ],
        "errors": [],
    }

    logger.info("=" * 70)
    logger.info("RETAILPULSE DATA VALIDATION")
    logger.info("=" * 70)

    try:
        reference_results = validate_reference_tables()

        report["reference_checks"] = (
            reference_results["reference_checks"]
        )

        report["inventory_checks"] = (
            reference_results["inventory_checks"]
        )

        report["sales_checks"] = validate_sales_transactions(
            reference_results["identifier_sets"]
        )

        reference_failures = [
            name
            for name, result in report["reference_checks"].items()
            if not result["passed"]
        ]

        inventory_checks = report["inventory_checks"]

        inventory_failures = (
            inventory_checks["duplicate_store_sku_combinations"] > 0
            or inventory_checks["inventory_rows_with_missing_keys"] > 0
        )

        sales_checks = report["sales_checks"]

        # These counts indicate detected issues, not necessarily
        # business-rule violations. Thresholds can be configured later.
        report["status"] = (
            "completed_with_findings"
            if reference_failures or inventory_failures
            else "completed"
        )

        print("\n" + "=" * 70)
        print("RETAILPULSE DATA VALIDATION RESULTS")
        print("=" * 70)

        print("\n1. REFERENCE TABLE UNIQUENESS")

        for name, result in report["reference_checks"].items():
            print(
                f"{name}: "
                f"{'PASS' if result['passed'] else 'FAIL'} "
                f"({result['details']})"
            )

        print("\n2. INVENTORY KEY CHECKS")

        for name, value in inventory_checks.items():
            print(f"{name}: {value:,}")

        print("\n3. SALES TRANSACTION VALIDATION")

        for name, value in sales_checks.items():
            print(f"{name}: {value}")

        print("\n4. COMPLETED")

    except Exception as error:
        report["status"] = "failed"

        report["errors"].append(
            f"{type(error).__name__}: {error}"
        )

        logger.exception("Data validation failed.")

    finally:
        report["elapsed_seconds"] = round(
            time.perf_counter() - started,
            2,
        )

        try:
            write_reports(report)

            logger.info(
                "JSON report: %s",
                JSON_REPORT,
            )

            logger.info(
                "Text report: %s",
                TEXT_REPORT,
            )

        except Exception:
            logger.exception(
                "Failed to save validation reports."
            )
            return 1

    return 1 if report["status"] == "failed" else 0


if __name__ == "__main__":
    sys.exit(main())