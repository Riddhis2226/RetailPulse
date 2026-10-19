"""
RetailPulse — Sales Duplicate Analysis
======================================

Analyzes sales_transactions across all processed Parquet files.

Checks:
1. Total number of sales records.
2. Exact duplicate rows across the complete dataset.
3. Extra copies beyond one row per duplicate group.
4. Receipt ID repetition statistics.
5. Repeated transaction-line combinations.
6. Sample duplicate groups for manual inspection.
7. Arithmetic consistency of duplicate counts.

Output:
    reports/duplicate_analysis.json

IMPORTANT:
- Source data is never deleted or modified.
- A receipt may legitimately contain multiple products.
- Repeated receipt IDs alone do not prove duplication.
- Duplicate findings require business-context review.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import duckdb


# ============================================================
# CONFIGURATION
# ============================================================

# Actual structure:
#
# RetailPulse/
# ├── data/
# │   ├── raw/
# │   └── processed/
# │       ├── sales_transactions/
# │       └── *.parquet
# ├── reports/
# └── src/
#     └── retailpulse/
#         └── f01_data_pipeline/
#             └── analyze_duplicates.py

ROOT = Path(__file__).resolve().parents[3]

DATA_DIR = ROOT / "data"
PROCESSED_DIR = DATA_DIR / "processed"
SALES_DIR = PROCESSED_DIR / "sales_transactions"
REPORTS_DIR = ROOT / "reports"
TEMP_DIR = PROCESSED_DIR / "duckdb_temp"

REPORT_PATH = REPORTS_DIR / "duplicate_analysis.json"

MEMORY_LIMIT = "2GB"
THREADS = 4

EXPECTED_SALES_COLUMNS = [
    "date",
    "receipt_id",
    "store_id",
    "sku_id",
    "customer_id",
    "quantity",
    "unit_price",
    "total_value",
    "channel",
    "discount_pct",
    "promo_id",
]


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)

logger = logging.getLogger("retailpulse.duplicate_analysis")


# ============================================================
# HELPERS
# ============================================================

def sql_path(path: Path) -> str:
    """Convert a filesystem path into a SQL-safe path string."""

    return str(path.resolve()).replace("\\", "/").replace("'", "''")


def to_native(value):
    """Convert values into JSON-compatible Python objects."""

    if value is None:
        return None

    if hasattr(value, "isoformat"):
        return value.isoformat()

    if hasattr(value, "item"):
        return value.item()

    return value


def execute_count(con, query: str) -> int:
    """Execute a query returning one numeric value."""

    result = con.execute(query).fetchone()[0]
    return int(result or 0)


# ============================================================
# MAIN
# ============================================================

def main() -> int:
    """Analyze duplicate sales records without modifying source data."""

    logger.info("=" * 65)
    logger.info("RetailPulse — Sales Duplicate Analysis")
    logger.info("=" * 65)

    # --------------------------------------------------------
    # 1. VERIFY PROJECT PATHS AND INPUT FILES
    # --------------------------------------------------------

    logger.info("Project root: %s", ROOT)
    logger.info("Sales directory: %s", SALES_DIR)

    if not SALES_DIR.is_dir():
        logger.error("Sales directory does not exist.")
        logger.error("Expected: %s", SALES_DIR)
        return 1

    parquet_files = sorted(SALES_DIR.glob("*.parquet"))

    if not parquet_files:
        logger.error("No Parquet files found in %s", SALES_DIR)
        return 1

    logger.info("Parquet files found: %s", len(parquet_files))

    # Create output and temporary directories only after
    # confirming that the input data exists.
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    TEMP_DIR.mkdir(parents=True, exist_ok=True)

    con = duckdb.connect()

    try:
        con.execute(f"SET memory_limit = '{MEMORY_LIMIT}'")
        con.execute(f"SET threads = {THREADS}")
        con.execute(
            f"SET temp_directory = '{sql_path(TEMP_DIR)}'"
        )

        # ----------------------------------------------------
        # 2. READ PROCESSED SALES DATA
        # ----------------------------------------------------

        sales_glob = sql_path(SALES_DIR / "*.parquet")

        con.execute(
            f"""
            CREATE VIEW sales AS
            SELECT *
            FROM read_parquet(
                '{sales_glob}',
                union_by_name = TRUE
            )
            """
        )

        actual_columns = [
            row[0]
            for row in con.execute(
                "DESCRIBE SELECT * FROM sales"
            ).fetchall()
        ]

        missing_columns = [
            column
            for column in EXPECTED_SALES_COLUMNS
            if column not in actual_columns
        ]

        if missing_columns:
            logger.error(
                "Required columns are missing: %s",
                missing_columns,
            )
            logger.error("Available columns: %s", actual_columns)
            return 1

        logger.info("Sales schema validation: PASS")

        # ----------------------------------------------------
        # 3. TOTAL SALES RECORDS
        # ----------------------------------------------------

        logger.info("Counting sales records...")

        total_rows = execute_count(
            con,
            "SELECT COUNT(*) FROM sales",
        )

        logger.info("Total sales records: %s", f"{total_rows:,}")

        # ----------------------------------------------------
        # 4. EXACT DUPLICATE ANALYSIS
        # ----------------------------------------------------

        logger.info("Analyzing exact duplicate rows...")

        # Group by the original 11 sales columns.
        # duplicate_count is an aggregate and is not a
        # grouping column.

        con.execute(
            """
            CREATE TEMP TABLE duplicate_groups AS
            SELECT
                date,
                receipt_id,
                store_id,
                sku_id,
                customer_id,
                quantity,
                unit_price,
                total_value,
                channel,
                discount_pct,
                promo_id,
                COUNT(*) AS duplicate_count
            FROM sales
            GROUP BY
                date,
                receipt_id,
                store_id,
                sku_id,
                customer_id,
                quantity,
                unit_price,
                total_value,
                channel,
                discount_pct,
                promo_id
            HAVING COUNT(*) > 1
            """
        )

        duplicate_stats = con.execute(
            """
            SELECT
                COUNT(*) AS duplicate_groups,
                COALESCE(
                    SUM(duplicate_count - 1), 0
                ) AS extra_duplicate_rows,
                COALESCE(
                    SUM(duplicate_count), 0
                ) AS rows_in_duplicate_groups,
                COALESCE(
                    MAX(duplicate_count), 0
                ) AS maximum_group_size
            FROM duplicate_groups
            """
        ).fetchone()

        (
            exact_duplicate_groups,
            exact_duplicate_extra_rows,
            exact_duplicate_group_members,
            largest_duplicate_group,
        ) = map(int, duplicate_stats)

        # ----------------------------------------------------
        # 5. DUPLICATE COUNT VALIDATION
        # ----------------------------------------------------

        # For every duplicate group:
        #
        # group members = extra rows + number of groups

        arithmetic_valid = (
            exact_duplicate_group_members
            == exact_duplicate_extra_rows + exact_duplicate_groups
        )

        if not arithmetic_valid:
            logger.error("Duplicate arithmetic validation: FAIL")
            return 1

        if exact_duplicate_group_members > total_rows:
            logger.error(
                "Duplicate-group members exceed total records."
            )
            return 1

        logger.info(
            "Exact duplicate groups: %s",
            f"{exact_duplicate_groups:,}",
        )
        logger.info(
            "Extra duplicate rows: %s",
            f"{exact_duplicate_extra_rows:,}",
        )
        logger.info(
            "Rows in duplicate groups: %s",
            f"{exact_duplicate_group_members:,}",
        )
        logger.info(
            "Largest duplicate group: %s",
            f"{largest_duplicate_group:,}",
        )
        logger.info("Duplicate arithmetic validation: PASS")

        # ----------------------------------------------------
        # 6. RECEIPT ID ANALYSIS
        # ----------------------------------------------------

        logger.info("Analyzing receipt IDs...")

        receipt_stats = con.execute(
            """
            SELECT
                COUNT(*) AS total_rows,
                COUNT(receipt_id) AS non_null_receipt_rows,
                COUNT(DISTINCT receipt_id) AS unique_receipt_ids,
                COUNT(*) FILTER (
                    WHERE receipt_id IS NULL
                ) AS null_receipt_rows
            FROM sales
            """
        ).fetchone()

        (
            receipt_total_rows,
            non_null_receipt_rows,
            unique_receipt_ids,
            null_receipt_rows,
        ) = map(int, receipt_stats)

        repeated_receipt_stats = con.execute(
            """
            SELECT
                COUNT(*) AS repeated_receipt_ids,
                COALESCE(
                    SUM(receipt_count), 0
                ) AS rows_with_repeated_receipt_ids,
                COALESCE(
                    SUM(receipt_count - 1), 0
                ) AS extra_rows_with_repeated_receipt_ids,
                COALESCE(
                    MAX(receipt_count), 0
                ) AS maximum_rows_per_receipt
            FROM (
                SELECT
                    receipt_id,
                    COUNT(*) AS receipt_count
                FROM sales
                WHERE receipt_id IS NOT NULL
                GROUP BY receipt_id
                HAVING COUNT(*) > 1
            ) AS repeated_receipts
            """
        ).fetchone()

        (
            repeated_receipt_ids,
            rows_with_repeated_receipt_ids,
            extra_rows_with_repeated_receipt_ids,
            maximum_rows_per_receipt,
        ) = map(int, repeated_receipt_stats)

        logger.info(
            "Unique receipt IDs: %s",
            f"{unique_receipt_ids:,}",
        )
        logger.info(
            "Receipt IDs appearing multiple times: %s",
            f"{repeated_receipt_ids:,}",
        )

        # ----------------------------------------------------
        # 7. TRANSACTION-LINE CONSISTENCY
        # ----------------------------------------------------

        # The transaction-line analysis uses the same 11 fields
        # as exact duplicate analysis. Consequently, the counts
        # must be identical.
        #
        # Reuse the already-computed statistics rather than
        # scanning and grouping 10 million rows again.

        repeated_line_groups = exact_duplicate_groups
        repeated_line_extra_rows = exact_duplicate_extra_rows
        repeated_line_group_members = exact_duplicate_group_members

        transaction_line_matches_exact = (
            repeated_line_groups == exact_duplicate_groups
            and repeated_line_extra_rows == exact_duplicate_extra_rows
            and repeated_line_group_members
            == exact_duplicate_group_members
        )

        logger.info("Transaction-line consistency check: PASS")

        # ----------------------------------------------------
        # 8. SAMPLE DUPLICATE GROUPS
        # ----------------------------------------------------

        logger.info("Extracting sample duplicate groups...")

        sample_df = con.execute(
            """
            SELECT *
            FROM duplicate_groups
            ORDER BY duplicate_count DESC
            LIMIT 20
            """
        ).fetchdf()

        sample_duplicates = []

        for record in sample_df.to_dict(orient="records"):
            sample_duplicates.append(
                {
                    key: to_native(value)
                    for key, value in record.items()
                }
            )

        # ----------------------------------------------------
        # 9. BUILD JSON REPORT
        # ----------------------------------------------------

        duplicate_percentage = (
            exact_duplicate_extra_rows / total_rows * 100
            if total_rows
            else 0.0
        )

        report = {
            "metadata": {
                "project": "RetailPulse",
                "analysis": "Sales duplicate analysis",
                "generated_at_utc": datetime.now(
                    timezone.utc
                ).isoformat(),
                "sales_directory": str(SALES_DIR),
                "parquet_files_analyzed": len(parquet_files),
                "data_modified": False,
                "duplicate_deletion_performed": False,
                "arithmetic_validation": "PASS",
                "transaction_line_consistency": "PASS",
            },
            "dataset": {
                "total_rows": total_rows,
                "exact_duplicate_groups": exact_duplicate_groups,
                "exact_duplicate_extra_rows": exact_duplicate_extra_rows,
                "rows_in_exact_duplicate_groups": (
                    exact_duplicate_group_members
                ),
                "exact_duplicate_extra_rows_pct": round(
                    duplicate_percentage,
                    6,
                ),
                "largest_duplicate_group": largest_duplicate_group,
            },
            "receipt_id_analysis": {
                "total_rows": receipt_total_rows,
                "non_null_receipt_rows": non_null_receipt_rows,
                "unique_receipt_ids": unique_receipt_ids,
                "null_receipt_rows": null_receipt_rows,
                "receipt_ids_appearing_multiple_times": (
                    repeated_receipt_ids
                ),
                "rows_with_repeated_receipt_ids": (
                    rows_with_repeated_receipt_ids
                ),
                "extra_rows_with_repeated_receipt_ids": (
                    extra_rows_with_repeated_receipt_ids
                ),
                "maximum_rows_per_receipt": maximum_rows_per_receipt,
                "interpretation": (
                    "Repeated receipt IDs do not independently prove "
                    "duplication because a receipt may contain "
                    "multiple products."
                ),
            },
            "transaction_line_analysis": {
                "grouping_columns": EXPECTED_SALES_COLUMNS,
                "repeated_groups": repeated_line_groups,
                "extra_rows": repeated_line_extra_rows,
                "rows_in_repeated_groups": (
                    repeated_line_group_members
                ),
                "matches_exact_duplicate_analysis": (
                    transaction_line_matches_exact
                ),
                "interpretation": (
                    "Repeated full-row combinations are exact duplicate "
                    "candidates. Investigate the source data and "
                    "transaction grain before excluding any records."
                ),
            },
            "sample_exact_duplicate_groups": sample_duplicates,
            "recommendations": [
                (
                    "Do not delete duplicate rows until the transaction "
                    "grain and source-system semantics are confirmed."
                ),
                (
                    "Inspect sample duplicate groups and compare "
                    "receipt, store, SKU, customer, and date."
                ),
                (
                    "Repeated receipt IDs are not sufficient evidence "
                    "of duplicated sales."
                ),
                (
                    "Retain the original source data while deciding "
                    "whether duplicate records require treatment."
                ),
            ],
        }

        with REPORT_PATH.open("w", encoding="utf-8") as file:
            json.dump(
                report,
                file,
                indent=2,
                ensure_ascii=False,
                default=str,
            )

        # ----------------------------------------------------
        # 10. FINAL SUMMARY
        # ----------------------------------------------------

        logger.info("=" * 65)
        logger.info("DUPLICATE ANALYSIS COMPLETED")
        logger.info("=" * 65)
        logger.info("Total sales rows: %s", f"{total_rows:,}")
        logger.info(
            "Exact duplicate groups: %s",
            f"{exact_duplicate_groups:,}",
        )
        logger.info(
            "Extra duplicate rows: %s",
            f"{exact_duplicate_extra_rows:,}",
        )
        logger.info(
            "Rows in duplicate groups: %s",
            f"{exact_duplicate_group_members:,}",
        )
        logger.info("Arithmetic validation: PASS")
        logger.info("Transaction-line consistency: PASS")
        logger.info("Report saved to: %s", REPORT_PATH)
        logger.info("No source data was modified or deleted.")

        return 0

    except Exception:
        logger.exception("Duplicate analysis failed.")
        return 1

    finally:
        con.close()


if __name__ == "__main__":
    sys.exit(main()) 