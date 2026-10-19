"""
RetailPulse — Referential Integrity Validation
================================================

Location:
    src/retailpulse/f01_data_pipeline/validate_referential_integrity.py

Run from repository root:
    $env:PYTHONPATH = "$PWD\\src"
    .venv\\Scripts\\python.exe -m retailpulse.f01_data_pipeline.validate_referential_integrity

Inputs:
    data/processed/customer_master.parquet
    data/processed/sku_master.parquet
    data/processed/store_master.parquet
    data/processed/promotions.parquet
    data/processed/inventory_snapshot.parquet
    data/processed/sku_inventory_flags.parquet
    data/processed/sales_transactions/part-*.parquet

Outputs:
    reports/referential_integrity_report.json
    reports/referential_integrity_summary.txt
"""

from __future__ import annotations

import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


# ============================================================
# CONFIGURATION
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[3]

PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
REPORT_DIR = PROJECT_ROOT / "reports"

JSON_REPORT = REPORT_DIR / "referential_integrity_report.json"
TEXT_REPORT = REPORT_DIR / "referential_integrity_summary.txt"

CHUNK_SIZE = 100_000


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)

logger = logging.getLogger("retailpulse.f01.referential_integrity")


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def normalize_identifier(series: pd.Series) -> pd.Series:
    """
    Normalize identifiers for comparisons.

    Treat nulls, empty strings, and common textual null markers
    as missing. The original datasets remain unchanged.
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


def load_reference_keys() -> dict[str, set[str]]:
    """
    Load valid identifiers from the reference datasets.

    Master tables are assumed to be small enough to fit in memory.
    """

    logger.info("Loading reference tables.")

    reference_files = {
        "customer_id": (
            "customer_master.parquet",
            "cust_id",
        ),
        "sku_id": (
            "sku_master.parquet",
            "sku_id",
        ),
        "store_id": (
            "store_master.parquet",
            "store_id",
        ),
        "promo_id": (
            "promotions.parquet",
            "promo_id",
        ),
    }

    reference_keys: dict[str, set[str]] = {}

    for reference_name, (filename, column) in reference_files.items():
        path = PROCESSED_DIR / filename

        if not path.is_file():
            raise FileNotFoundError(
                f"Reference dataset not found: {path}"
            )

        df = pd.read_parquet(
            path,
            columns=[column],
        )

        normalized = normalize_identifier(df[column])

        reference_keys[reference_name] = set(
            normalized.dropna().tolist()
        )

        logger.info(
            "Loaded %s unique %s values.",
            f"{len(reference_keys[reference_name]):,}",
            reference_name,
        )

    return reference_keys


# ============================================================
# SALES RELATIONSHIP VALIDATION
# ============================================================

def validate_sales_relationships(
    reference_keys: dict[str, set[str]],
) -> dict[str, Any]:
    """
    Validate sales references against customer, SKU, store,
    and promotion master datasets.

    Each Parquet file is loaded individually and then processed
    in batches.
    """

    sales_dir = PROCESSED_DIR / "sales_transactions"

    parquet_files = sorted(
        sales_dir.glob("part-*.parquet")
    )

    if not parquet_files:
        raise FileNotFoundError(
            f"No sales Parquet files found in {sales_dir}"
        )

    results = {
        "rows_checked": 0,
        "parquet_files_checked": 0,
        "missing_customer_ids": 0,
        "unknown_customer_ids": 0,
        "missing_sku_ids": 0,
        "unknown_sku_ids": 0,
        "missing_store_ids": 0,
        "unknown_store_ids": 0,
        "missing_promotion_ids": 0,
        "unknown_promotion_ids": 0,
    }

    columns = [
        "customer_id",
        "sku_id",
        "store_id",
        "promo_id",
    ]

    logger.info(
        "Validating sales relationships across %s Parquet files.",
        f"{len(parquet_files):,}",
    )

    for file_index, path in enumerate(parquet_files, start=1):
        sales_part = pd.read_parquet(
            path,
            columns=columns,
        )

        results["parquet_files_checked"] += 1

        for start in range(0, len(sales_part), CHUNK_SIZE):
            chunk = sales_part.iloc[
                start:start + CHUNK_SIZE
            ]

            results["rows_checked"] += len(chunk)

            # ------------------------------------------------
            # CUSTOMER REFERENCES
            # ------------------------------------------------

            customer_ids = normalize_identifier(
                chunk["customer_id"]
            )

            missing = customer_ids.isna()

            results["missing_customer_ids"] += int(
                missing.sum()
            )

            results["unknown_customer_ids"] += int(
                (
                    ~missing
                    & ~customer_ids.isin(
                        reference_keys["customer_id"]
                    )
                ).sum()
            )

            # ------------------------------------------------
            # SKU REFERENCES
            # ------------------------------------------------

            sku_ids = normalize_identifier(
                chunk["sku_id"]
            )

            missing = sku_ids.isna()

            results["missing_sku_ids"] += int(
                missing.sum()
            )

            results["unknown_sku_ids"] += int(
                (
                    ~missing
                    & ~sku_ids.isin(
                        reference_keys["sku_id"]
                    )
                ).sum()
            )

            # ------------------------------------------------
            # STORE REFERENCES
            # ------------------------------------------------

            store_ids = normalize_identifier(
                chunk["store_id"]
            )

            missing = store_ids.isna()

            results["missing_store_ids"] += int(
                missing.sum()
            )

            results["unknown_store_ids"] += int(
                (
                    ~missing
                    & ~store_ids.isin(
                        reference_keys["store_id"]
                    )
                ).sum()
            )

            # ------------------------------------------------
            # PROMOTION REFERENCES
            # ------------------------------------------------

            promo_ids = normalize_identifier(
                chunk["promo_id"]
            )

            missing = promo_ids.isna()

            # Missing promotions are allowed.
            results["missing_promotion_ids"] += int(
                missing.sum()
            )

            results["unknown_promotion_ids"] += int(
                (
                    ~missing
                    & ~promo_ids.isin(
                        reference_keys["promo_id"]
                    )
                ).sum()
            )

        logger.info(
            "Checked file %s/%s: %s",
            file_index,
            len(parquet_files),
            path.name,
        )

        del sales_part

    return results


# ============================================================
# INVENTORY RELATIONSHIP VALIDATION
# ============================================================

def validate_inventory_relationships(
    reference_keys: dict[str, set[str]],
) -> dict[str, Any]:
    """Validate inventory store and SKU references."""

    path = PROCESSED_DIR / "inventory_snapshot.parquet"

    if not path.is_file():
        raise FileNotFoundError(
            f"Inventory dataset not found: {path}"
        )

    inventory = pd.read_parquet(
        path,
        columns=["store_id", "sku_id"],
    )

    store_ids = normalize_identifier(
        inventory["store_id"]
    )

    sku_ids = normalize_identifier(
        inventory["sku_id"]
    )

    missing_store = store_ids.isna()
    missing_sku = sku_ids.isna()

    unknown_store = (
        ~missing_store
        & ~store_ids.isin(reference_keys["store_id"])
    )

    unknown_sku = (
        ~missing_sku
        & ~sku_ids.isin(reference_keys["sku_id"])
    )

    return {
        "rows_checked": int(len(inventory)),
        "missing_store_ids": int(missing_store.sum()),
        "unknown_store_ids": int(unknown_store.sum()),
        "missing_sku_ids": int(missing_sku.sum()),
        "unknown_sku_ids": int(unknown_sku.sum()),
    }


# ============================================================
# SKU INVENTORY FLAG RELATIONSHIP VALIDATION
# ============================================================

def validate_flag_relationships(
    reference_keys: dict[str, set[str]],
) -> dict[str, Any]:
    """Validate SKU references in the inventory flags dataset."""

    path = PROCESSED_DIR / "sku_inventory_flags.parquet"

    if not path.is_file():
        raise FileNotFoundError(
            f"SKU inventory flags dataset not found: {path}"
        )

    flags = pd.read_parquet(
        path,
        columns=["sku_id"],
    )

    sku_ids = normalize_identifier(flags["sku_id"])

    missing = sku_ids.isna()

    unknown = (
        ~missing
        & ~sku_ids.isin(reference_keys["sku_id"])
    )

    return {
        "rows_checked": int(len(flags)),
        "missing_sku_ids": int(missing.sum()),
        "unknown_sku_ids": int(unknown.sum()),
    }


# ============================================================
# BUILD VALIDATION CHECKS
# ============================================================

def build_checks(
    sales_results: dict[str, Any],
    inventory_results: dict[str, Any],
    flag_results: dict[str, Any],
) -> dict[str, dict[str, bool]]:
    """Convert validation counts into explicit PASS/FAIL checks."""

    return {
        "sales": {
            "customer_references_valid": (
                sales_results["missing_customer_ids"] == 0
                and sales_results["unknown_customer_ids"] == 0
            ),
            "sku_references_valid": (
                sales_results["missing_sku_ids"] == 0
                and sales_results["unknown_sku_ids"] == 0
            ),
            "store_references_valid": (
                sales_results["missing_store_ids"] == 0
                and sales_results["unknown_store_ids"] == 0
            ),
            # Missing promotion IDs are permissible.
            "promotion_references_valid": (
                sales_results["unknown_promotion_ids"] == 0
            ),
        },
        "inventory": {
            "store_references_valid": (
                inventory_results["missing_store_ids"] == 0
                and inventory_results["unknown_store_ids"] == 0
            ),
            "sku_references_valid": (
                inventory_results["missing_sku_ids"] == 0
                and inventory_results["unknown_sku_ids"] == 0
            ),
        },
        "sku_inventory_flags": {
            "sku_references_valid": (
                flag_results["missing_sku_ids"] == 0
                and flag_results["unknown_sku_ids"] == 0
            ),
        },
    }


# ============================================================
# REPORT GENERATION
# ============================================================

def write_reports(report: dict[str, Any]) -> None:
    """Save machine-readable JSON and a human-readable text report."""

    REPORT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    JSON_REPORT.write_text(
        json.dumps(
            report,
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    lines = [
        "RetailPulse — Referential Integrity Validation",
        "=" * 65,
        f"Generated at UTC: {report['generated_at_utc']}",
        f"Overall status: {report['overall_status']}",
        f"Checks passed: {report['checks_passed']}",
        f"Checks failed: {report['checks_failed']}",
        f"Elapsed seconds: {report['elapsed_seconds']}",
        "",
        "VALIDATION CHECKS",
        "-" * 65,
    ]

    for group, group_checks in report["checks"].items():
        lines.append("")
        lines.append(group.upper())

        for check_name, passed in group_checks.items():
            status = "PASS" if passed else "FAIL"
            lines.append(f"[{status}] {check_name}")

    for section_name, section_data in [
        ("SALES RELATIONSHIPS", report["sales_relationships"]),
        ("INVENTORY RELATIONSHIPS", report["inventory_relationships"]),
        (
            "SKU INVENTORY FLAG RELATIONSHIPS",
            report["sku_inventory_flag_relationships"],
        ),
    ]:
        lines.extend(
            [
                "",
                section_name,
                "-" * 65,
            ]
        )

        for key, value in section_data.items():
            lines.append(f"{key}: {value:,}")

    lines.extend(
        [
            "",
            "NOTES",
            "-" * 65,
            "- Missing promotion IDs are allowed.",
            "- Unknown nonmissing promotion IDs fail validation.",
            "- Identifier normalization is applied for comparisons only.",
            "- Source Parquet files are not modified.",
            "",
        ]
    )

    TEXT_REPORT.write_text(
        "\n".join(lines),
        encoding="utf-8",
    )


# ============================================================
# MAIN
# ============================================================

def main() -> int:
    """Run referential integrity validation and save its reports."""

    started = time.perf_counter()

    logger.info("=" * 65)
    logger.info("RETAILPULSE — REFERENTIAL INTEGRITY VALIDATION")
    logger.info("=" * 65)

    report: dict[str, Any] = {
        "project": "RetailPulse",
        "validation_type": "Referential Integrity",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "overall_status": "RUNNING",
        "checks_passed": 0,
        "checks_failed": 0,
        "checks": {},
        "sales_relationships": {},
        "inventory_relationships": {},
        "sku_inventory_flag_relationships": {},
        "errors": [],
    }

    try:
        reference_keys = load_reference_keys()

        sales_results = validate_sales_relationships(
            reference_keys
        )

        inventory_results = validate_inventory_relationships(
            reference_keys
        )

        flag_results = validate_flag_relationships(
            reference_keys
        )

        checks = build_checks(
            sales_results,
            inventory_results,
            flag_results,
        )

        all_checks = [
            passed
            for group_checks in checks.values()
            for passed in group_checks.values()
        ]

        passed_count = sum(all_checks)
        failed_count = len(all_checks) - passed_count

        report.update(
            {
                "overall_status": (
                    "PASS" if failed_count == 0 else "FAIL"
                ),
                "checks_passed": passed_count,
                "checks_failed": failed_count,
                "checks": checks,
                "sales_relationships": sales_results,
                "inventory_relationships": inventory_results,
                "sku_inventory_flag_relationships": flag_results,
            }
        )

        print("\n" + "=" * 65)
        print("RETAILPULSE — REFERENTIAL INTEGRITY VALIDATION")
        print("=" * 65)

        for group, group_checks in checks.items():
            print(f"\n{group.upper()}")

            for check_name, passed in group_checks.items():
                status = "PASS" if passed else "FAIL"
                print(f"[{status}] {check_name}")

        print("\nSALES SUMMARY")
        print("-" * 45)

        for key, value in sales_results.items():
            print(f"{key}: {value:,}")

        print("\nINVENTORY SUMMARY")
        print("-" * 45)

        for key, value in inventory_results.items():
            print(f"{key}: {value:,}")

        print("\nSKU INVENTORY FLAGS SUMMARY")
        print("-" * 45)

        for key, value in flag_results.items():
            print(f"{key}: {value:,}")

    except Exception as exc:
        logger.exception("Referential integrity validation failed.")

        report["overall_status"] = "ERROR"
        report["errors"].append(
            f"{type(exc).__name__}: {exc}"
        )

    report["elapsed_seconds"] = round(
        time.perf_counter() - started,
        2,
    )

    try:
        write_reports(report)

        logger.info("JSON report saved to: %s", JSON_REPORT)
        logger.info("Text report saved to: %s", TEXT_REPORT)

    except Exception:
        logger.exception("Failed to save validation reports.")
        return 1

    print("\n" + "=" * 65)
    print(f"Checks passed: {report['checks_passed']}")
    print(f"Checks failed: {report['checks_failed']}")
    print(f"Overall result: {report['overall_status']}")
    print("=" * 65)

    return 1 if report["overall_status"] != "PASS" else 0


if __name__ == "__main__":
    sys.exit(main()) 
    