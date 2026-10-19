"""
RetailPulse — Missing-Value Analysis
====================================

Analyzes missing values in all seven RetailPulse datasets.

Datasets:
1. customer_master
2. inventory_snapshot
3. promotions
4. sales_transactions
5. sku_inventory_flags
6. sku_master
7. store_master

Outputs:
    reports/missing_values_report.json
    reports/missing_values_summary.csv

Features:
- Counts missing values by column.
- Calculates missing-value percentages.
- Identifies columns with no missing values.
- Distinguishes missing promotion IDs from unknown promotion IDs.
- Highlights missing inventory-flag window dates.
- Processes sales Parquet files without loading the full dataset
  into Pandas memory.
- Does not modify or delete any source data.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import pandas as pd


# ============================================================
# CONFIGURATION
# ============================================================

# Actual project structure:
#
# RetailPulse/
# ├── data/
# │   ├── raw/
# │   └── processed/
# │       ├── customer_master.parquet
# │       ├── inventory_snapshot.parquet
# │       ├── promotions.parquet
# │       ├── sku_inventory_flags.parquet
# │       ├── sku_master.parquet
# │       ├── store_master.parquet
# │       └── sales_transactions/
# │           ├── part-00001.parquet
# │           └── ...
# ├── reports/
# └── src/
#     └── retailpulse/
#         └── f01_data_pipeline/
#             └── analyze_missing_values.py

ROOT = Path(__file__).resolve().parents[3]

DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"

SALES_DIR = PROCESSED_DIR / "sales_transactions"

REPORTS_DIR = ROOT / "reports"

JSON_REPORT = REPORTS_DIR / "missing_values_report.json"
CSV_REPORT = REPORTS_DIR / "missing_values_summary.csv"

TEMP_DIR = PROCESSED_DIR / "duckdb_temp"

MEMORY_LIMIT = "2GB"
THREADS = 4


# Processed dataset paths.
DATASETS = {
    "customer_master": PROCESSED_DIR / "customer_master.parquet",
    "inventory_snapshot": PROCESSED_DIR / "inventory_snapshot.parquet",
    "promotions": PROCESSED_DIR / "promotions.parquet",
    "sales_transactions": SALES_DIR,
    "sku_inventory_flags": (
        PROCESSED_DIR / "sku_inventory_flags.parquet"
    ),
    "sku_master": PROCESSED_DIR / "sku_master.parquet",
    "store_master": PROCESSED_DIR / "store_master.parquet",
}


# Columns that need additional investigation.
SPECIAL_COLUMNS = {
    "sales_transactions": ["promo_id"],
    "sku_inventory_flags": ["window_start", "window_end"],
}


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)

logger = logging.getLogger("retailpulse.missing_values")


# ============================================================
# HELPERS
# ============================================================

def sql_path(path: Path) -> str:
    """Convert a filesystem path into a SQL-safe string."""

    return str(path.resolve()).replace("\\", "/").replace("'", "''")


def is_missing_path(path: Path) -> bool:
    """Return True when the expected Parquet input is absent."""

    if path.is_dir():
        return not any(path.glob("*.parquet"))

    return not path.is_file()


def get_parquet_glob(path: Path) -> str:
    """Return the Parquet file path or directory glob."""

    if path.is_dir():
        return sql_path(path / "*.parquet")

    return sql_path(path)


def validate_inputs() -> list[str]:
    """Return a list of missing processed dataset inputs."""

    missing = []

    for dataset_name, dataset_path in DATASETS.items():
        if is_missing_path(dataset_path):
            missing.append(
                f"{dataset_name}: {dataset_path}"
            )

    return missing


def quote_identifier(identifier: str) -> str:
    """Safely quote a DuckDB SQL identifier."""

    return '"' + identifier.replace('"', '""') + '"'


# ============================================================
# DATASET ANALYSIS
# ============================================================

def analyze_dataset(
    con: duckdb.DuckDBPyConnection,
    dataset_name: str,
    dataset_path: Path,
) -> dict:
    """Calculate missing-value statistics for one dataset."""

    logger.info("Analyzing dataset: %s", dataset_name)

    if is_missing_path(dataset_path):
        raise FileNotFoundError(
            f"Processed dataset not found: {dataset_path}"
        )

    parquet_path = get_parquet_glob(dataset_path)

    # The dataset names are controlled by the DATASETS mapping.
    view_name = f"dataset_{dataset_name}"

    con.execute(
        f"""
        CREATE OR REPLACE TEMP VIEW {view_name} AS
        SELECT *
        FROM read_parquet(
            '{parquet_path}',
            union_by_name = TRUE
        )
        """
    )

    # --------------------------------------------------------
    # SCHEMA
    # --------------------------------------------------------

    schema = con.execute(
        f"DESCRIBE SELECT * FROM {view_name}"
    ).fetchall()

    columns = [row[0] for row in schema]

    if not columns:
        raise ValueError(
            f"Dataset has no columns: {dataset_name}"
        )

    # --------------------------------------------------------
    # TOTAL ROWS
    # --------------------------------------------------------

    total_rows = int(
        con.execute(
            f"SELECT COUNT(*) FROM {view_name}"
        ).fetchone()[0]
    )

    # --------------------------------------------------------
    # MISSING VALUES BY COLUMN
    # --------------------------------------------------------

    # Count nulls in one SQL aggregation. The full dataset is
    # not loaded into Pandas memory.

    null_expressions = []

    for column in columns:
        quoted_column = quote_identifier(column)

        null_expressions.append(
            f"COUNT(*) FILTER "
            f"(WHERE {quoted_column} IS NULL) "
            f"AS {quoted_column}"
        )

    null_query = f"""
        SELECT {", ".join(null_expressions)}
        FROM {view_name}
    """

    null_counts = con.execute(null_query).fetchone()

    column_results = {}
    total_missing_cells = 0

    for index, column in enumerate(columns):
        missing_count = int(null_counts[index] or 0)

        missing_percentage = (
            missing_count / total_rows * 100
            if total_rows
            else 0.0
        )

        total_missing_cells += missing_count

        column_results[column] = {
            "missing_count": missing_count,
            "missing_percentage": round(
                missing_percentage,
                6,
            ),
            "non_missing_count": total_rows - missing_count,
            "status": (
                "MISSING_VALUES"
                if missing_count > 0
                else "COMPLETE"
            ),
        }

    # --------------------------------------------------------
    # ROWS WITH MISSING VALUES
    # --------------------------------------------------------

    null_conditions = [
        f"{quote_identifier(column)} IS NULL"
        for column in columns
    ]

    rows_with_missing_values = int(
        con.execute(
            f"""
            SELECT COUNT(*)
            FROM {view_name}
            WHERE {" OR ".join(null_conditions)}
            """
        ).fetchone()[0]
    )

    rows_without_missing_values = (
        total_rows - rows_with_missing_values
    )

    total_cells = total_rows * len(columns)

    overall_missing_percentage = (
        total_missing_cells / total_cells * 100
        if total_cells
        else 0.0
    )

    # --------------------------------------------------------
    # BUILD RESULT
    # --------------------------------------------------------

    result = {
        "dataset": dataset_name,
        "source_path": str(dataset_path),
        "total_rows": total_rows,
        "total_columns": len(columns),
        "total_cells": total_cells,
        "total_missing_cells": total_missing_cells,
        "overall_missing_percentage": round(
            overall_missing_percentage,
            6,
        ),
        "rows_with_missing_values": rows_with_missing_values,
        "rows_without_missing_values": rows_without_missing_values,
        "columns_with_missing_values": sum(
            1
            for stats in column_results.values()
            if stats["missing_count"] > 0
        ),
        "columns_without_missing_values": sum(
            1
            for stats in column_results.values()
            if stats["missing_count"] == 0
        ),
        "columns": column_results,
    }

    logger.info(
        "%s: %s rows, %s columns, %s missing cells",
        dataset_name,
        f"{total_rows:,}",
        f"{len(columns):,}",
        f"{total_missing_cells:,}",
    )

    return result


# ============================================================
# SPECIAL INVESTIGATIONS
# ============================================================

def analyze_special_cases(
    con: duckdb.DuckDBPyConnection,
) -> dict:
    """
    Investigate known missing-value patterns.

    Missing values are reported, not automatically imputed.
    """

    special_results = {}

    # --------------------------------------------------------
    # 1. MISSING PROMOTION IDS
    # --------------------------------------------------------

    logger.info("Investigating missing sales promotion IDs...")

    sales_path = get_parquet_glob(SALES_DIR)

    con.execute(
        f"""
        CREATE OR REPLACE TEMP VIEW sales_special AS
        SELECT *
        FROM read_parquet(
            '{sales_path}',
            union_by_name = TRUE
        )
        """
    )

    promotion_stats = con.execute(
        """
        SELECT
            COUNT(*) AS total_rows,
            COUNT(*) FILTER (
                WHERE promo_id IS NULL
            ) AS missing_promo_ids,
            COUNT(*) FILTER (
                WHERE promo_id IS NOT NULL
            ) AS non_missing_promo_ids
        FROM sales_special
        """
    ).fetchone()

    (
        sales_total_rows,
        missing_promo_ids,
        non_missing_promo_ids,
    ) = map(int, promotion_stats)

    # Check whether any non-null promotion IDs fail to match
    # the promotions master dataset.
    con.execute(
        f"""
        CREATE OR REPLACE TEMP VIEW promotions_special AS
        SELECT *
        FROM read_parquet(
            '{get_parquet_glob(DATASETS["promotions"])}',
            union_by_name = TRUE
        )
        """
    )

    unknown_promo_ids = int(
        con.execute(
            """
            SELECT COUNT(*)
            FROM sales_special AS s
            WHERE s.promo_id IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1
                  FROM promotions_special AS p
                  WHERE p.promo_id = s.promo_id
              )
            """
        ).fetchone()[0]
    )

    special_results["sales_promotion_ids"] = {
        "total_sales_rows": sales_total_rows,
        "missing_promo_ids": missing_promo_ids,
        "non_missing_promo_ids": non_missing_promo_ids,
        "unknown_non_null_promo_ids": unknown_promo_ids,
        "missing_percentage": round(
            missing_promo_ids / sales_total_rows * 100
            if sales_total_rows
            else 0.0,
            6,
        ),
        "interpretation": (
            "A missing promotion ID may represent a transaction "
            "without a promotion. Confirm this against source-system "
            "rules before imputing values. Unknown non-null IDs are "
            "counted separately."
        ),
    }

    # --------------------------------------------------------
    # 2. INVENTORY-FLAG DATE WINDOWS
    # --------------------------------------------------------

    logger.info(
        "Investigating missing inventory-flag date windows..."
    )

    flags_path = get_parquet_glob(
        DATASETS["sku_inventory_flags"]
    )

    con.execute(
        f"""
        CREATE OR REPLACE TEMP VIEW flags_special AS
        SELECT *
        FROM read_parquet(
            '{flags_path}',
            union_by_name = TRUE
        )
        """
    )

    flag_stats = con.execute(
        """
        SELECT
            COUNT(*) AS total_rows,

            COUNT(*) FILTER (
                WHERE window_start IS NULL
            ) AS missing_window_start,

            COUNT(*) FILTER (
                WHERE window_end IS NULL
            ) AS missing_window_end,

            COUNT(*) FILTER (
                WHERE window_start IS NULL
                  AND window_end IS NULL
            ) AS both_dates_missing,

            COUNT(*) FILTER (
                WHERE window_start IS NOT NULL
                  AND window_end IS NOT NULL
            ) AS both_dates_present,

            COUNT(*) FILTER (
                WHERE window_start IS NULL
                  AND window_end IS NOT NULL
            ) AS start_missing_only,

            COUNT(*) FILTER (
                WHERE window_start IS NOT NULL
                  AND window_end IS NULL
            ) AS end_missing_only

        FROM flags_special
        """
    ).fetchone()

    (
        flag_total_rows,
        missing_window_start,
        missing_window_end,
        both_dates_missing,
        both_dates_present,
        start_missing_only,
        end_missing_only,
    ) = map(int, flag_stats)

    special_results["inventory_flag_date_windows"] = {
        "total_rows": flag_total_rows,
        "missing_window_start": missing_window_start,
        "missing_window_end": missing_window_end,
        "both_dates_missing": both_dates_missing,
        "both_dates_present": both_dates_present,
        "start_missing_only": start_missing_only,
        "end_missing_only": end_missing_only,
        "interpretation": (
            "Missing date windows require investigation. Do not "
            "replace them with arbitrary dates or assume that missing "
            "dates mean the flags are inactive."
        ),
    }

    return special_results


# ============================================================
# CSV SUMMARY
# ============================================================

def build_csv_summary(
    dataset_reports: dict,
) -> pd.DataFrame:
    """Convert dataset and column statistics into a flat table."""

    records = []

    for dataset_name, report in dataset_reports.items():
        for column_name, stats in report["columns"].items():
            records.append(
                {
                    "dataset": dataset_name,
                    "column": column_name,
                    "total_rows": report["total_rows"],
                    "missing_count": stats["missing_count"],
                    "missing_percentage": (
                        stats["missing_percentage"]
                    ),
                    "non_missing_count": (
                        stats["non_missing_count"]
                    ),
                    "status": stats["status"],
                }
            )

    return pd.DataFrame(
        records,
        columns=[
            "dataset",
            "column",
            "total_rows",
            "missing_count",
            "missing_percentage",
            "non_missing_count",
            "status",
        ],
    )


# ============================================================
# MAIN
# ============================================================

def main() -> int:
    """Run missing-value analysis and save the reports."""

    logger.info("=" * 65)
    logger.info("RetailPulse — Missing-Value Analysis")
    logger.info("=" * 65)

    logger.info("Project root: %s", ROOT)
    logger.info("Processed data directory: %s", PROCESSED_DIR)

    # --------------------------------------------------------
    # 1. VERIFY INPUTS BEFORE ANALYSIS
    # --------------------------------------------------------

    missing_inputs = validate_inputs()

    if missing_inputs:
        logger.error(
            "The following processed datasets are missing:"
        )

        for item in missing_inputs:
            logger.error("  - %s", item)

        logger.error(
            "No reports were generated. Check the paths above."
        )
        return 1

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
        # 2. ANALYZE ALL SEVEN DATASETS
        # ----------------------------------------------------

        dataset_reports = {}

        for dataset_name, dataset_path in DATASETS.items():
            dataset_reports[dataset_name] = analyze_dataset(
                con,
                dataset_name,
                dataset_path,
            )

        # ----------------------------------------------------
        # 3. SPECIAL INVESTIGATIONS
        # ----------------------------------------------------

        special_cases = analyze_special_cases(con)

        # ----------------------------------------------------
        # 4. OVERALL SUMMARY
        # ----------------------------------------------------

        total_rows_across_datasets = sum(
            item["total_rows"]
            for item in dataset_reports.values()
        )

        total_missing_cells = sum(
            item["total_missing_cells"]
            for item in dataset_reports.values()
        )

        total_cells = sum(
            item["total_cells"]
            for item in dataset_reports.values()
        )

        overall_missing_percentage = (
            total_missing_cells / total_cells * 100
            if total_cells
            else 0.0
        )

        report = {
            "metadata": {
                "project": "RetailPulse",
                "analysis": "Missing-value analysis",
                "generated_at_utc": datetime.now(
                    timezone.utc
                ).isoformat(),
                "data_modified": False,
                "missing_values_imputed": False,
                "source_data_deleted": False,
            },
            "overall_summary": {
                "datasets_analyzed": len(dataset_reports),
                "total_rows_across_datasets": (
                    total_rows_across_datasets
                ),
                "total_missing_cells": total_missing_cells,
                "total_cells": total_cells,
                "overall_missing_percentage": round(
                    overall_missing_percentage,
                    6,
                ),
            },
            "datasets": dataset_reports,
            "special_investigations": special_cases,
            "recommendations": [
                (
                    "Do not impute missing values until their "
                    "business meaning has been established."
                ),
                (
                    "Investigate missing inventory-flag window dates "
                    "before using those flags in inventory optimization."
                ),
                (
                    "Treat missing promotion IDs separately from "
                    "unknown non-null promotion IDs."
                ),
                (
                    "Assess the impact of missing values on each "
                    "downstream analytical task."
                ),
            ],
        }

        # ----------------------------------------------------
        # 5. BUILD CSV SUMMARY
        # ----------------------------------------------------

        summary_df = build_csv_summary(dataset_reports)

        # ----------------------------------------------------
        # 6. SAVE REPORTS
        # ----------------------------------------------------

        with JSON_REPORT.open("w", encoding="utf-8") as file:
            json.dump(
                report,
                file,
                indent=2,
                ensure_ascii=False,
                default=str,
            )

        summary_df.to_csv(
            CSV_REPORT,
            index=False,
            encoding="utf-8",
        )

        # ----------------------------------------------------
        # 7. FINAL SUMMARY
        # ----------------------------------------------------

        logger.info("=" * 65)
        logger.info("MISSING-VALUE ANALYSIS COMPLETED")
        logger.info("=" * 65)

        logger.info(
            "Datasets analyzed: %s",
            len(dataset_reports),
        )

        logger.info(
            "Total missing cells: %s",
            f"{total_missing_cells:,}",
        )

        logger.info(
            "Overall missing percentage: %.6f%%",
            overall_missing_percentage,
        )

        logger.info("JSON report: %s", JSON_REPORT)
        logger.info("CSV summary: %s", CSV_REPORT)
        logger.info("Source data was not modified.")

        return 0

    except Exception:
        logger.exception("Missing-value analysis failed.")
        return 1

    finally:
        con.close()


if __name__ == "__main__":
    sys.exit(main()) 