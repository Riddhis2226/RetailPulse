"""
RetailPulse — F02 Customer Feature Engineering
===============================================

Purpose:
    Generate customer-level Recency, Frequency, and Monetary (RFM)
    features from the processed sales transactions.

Input:
    data/processed/sales_transactions/*.parquet

Output:
    data/processed/customer_rfm.parquet
    reports/f02_feature_engineering_report.json

RFM definitions:
    Recency:
        Days since the customer's most recent purchase, relative to
        the day after the latest transaction date in the dataset.

    Frequency:
        Number of distinct receipts per customer.

    Monetary:
        Sum of total_value across the customer's transactions.

MLflow:
    Experiment: RetailPulse-Customer-Segmentation
    Tracks parameters, metrics, and generated artifacts.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import mlflow

from retailpulse.config import PROCESSED_DIR, REPORTS_DIR


# ============================================================
# CONFIGURATION
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[3]

SALES_DIR = PROCESSED_DIR / "sales_transactions"

OUTPUT_FILE = PROCESSED_DIR / "customer_rfm.parquet"

REPORT_FILE = REPORTS_DIR / "f02_feature_engineering_report.json"

EXPERIMENT_NAME = "RetailPulse-Customer-Segmentation"

TRACKING_URI = os.getenv(
    "MLFLOW_TRACKING_URI",
    "http://127.0.0.1:5000",
)

MEMORY_LIMIT = "2GB"
THREADS = 4


# Required source columns based on the F01 sales schema.
REQUIRED_COLUMNS = {
    "date",
    "receipt_id",
    "customer_id",
    "quantity",
    "unit_price",
    "total_value",
}


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)

logger = logging.getLogger("retailpulse.f02.feature_engineering")


# ============================================================
# HELPERS
# ============================================================

def sql_string(value: str) -> str:
    """Escape a string before inserting it into a SQL string literal."""
    return value.replace("'", "''")


def get_sales_files() -> list[Path]:
    """Return all processed sales Parquet files."""
    if not SALES_DIR.exists():
        raise FileNotFoundError(
            f"Processed sales directory not found: {SALES_DIR}"
        )

    files = sorted(SALES_DIR.glob("*.parquet"))

    if not files:
        raise FileNotFoundError(
            f"No Parquet files found in: {SALES_DIR}"
        )

    return files


def validate_source_schema(
    con: duckdb.DuckDBPyConnection,
    parquet_glob: str,
) -> list[str]:
    """Validate the source columns without loading the dataset into Pandas."""
    escaped_glob = sql_string(parquet_glob)

    result = con.execute(
        f"""
        DESCRIBE
        SELECT *
        FROM read_parquet('{escaped_glob}')
        """
    ).fetchall()

    available_columns = [row[0] for row in result]

    missing_columns = sorted(
        REQUIRED_COLUMNS.difference(available_columns)
    )

    if missing_columns:
        raise ValueError(
            "Sales dataset is missing required columns: "
            f"{missing_columns}. "
            f"Available columns: {available_columns}"
        )

    logger.info("Source schema validation passed.")
    logger.info("Source columns: %s", available_columns)

    return available_columns


# ============================================================
# FEATURE ENGINEERING
# ============================================================

def generate_rfm(
    con: duckdb.DuckDBPyConnection,
    parquet_glob: str,
) -> dict:
    """
    Aggregate transaction records into one RFM row per customer.

    DuckDB performs the aggregation directly against the Parquet files.
    Only the aggregated customer-level result is materialized in Pandas.
    """

    escaped_glob = sql_string(parquet_glob)

    logger.info("Calculating transaction-level data quality checks.")

    quality = con.execute(
        f"""
        SELECT
            COUNT(*) AS transaction_rows,

            COUNT(*) FILTER (
                WHERE customer_id IS NULL
            ) AS null_customer_ids,

            COUNT(*) FILTER (
                WHERE date IS NULL
            ) AS null_transaction_dates,

            COUNT(*) FILTER (
                WHERE receipt_id IS NULL
            ) AS null_receipt_ids,

            COUNT(*) FILTER (
                WHERE total_value IS NULL
            ) AS null_total_values,

            COUNT(*) FILTER (
                WHERE TRY_CAST(date AS DATE) IS NULL
            ) AS invalid_transaction_dates,

            COUNT(*) FILTER (
                WHERE TRY_CAST(total_value AS DOUBLE) IS NULL
            ) AS invalid_total_values

        FROM read_parquet('{escaped_glob}')
        """
    ).fetchone()

    quality_report = {
        "transaction_rows": int(quality[0]),
        "null_customer_ids": int(quality[1]),
        "null_transaction_dates": int(quality[2]),
        "null_receipt_ids": int(quality[3]),
        "null_total_values": int(quality[4]),
        "invalid_transaction_dates": int(quality[5]),
        "invalid_total_values": int(quality[6]),
    }

    logger.info("Source rows: %s", quality_report["transaction_rows"])
    logger.info("Source quality: %s", quality_report)

    if quality_report["transaction_rows"] == 0:
        raise ValueError("The sales dataset contains no transaction rows.")

    # Customer identity and transaction dates are essential for RFM.
    if quality_report["null_customer_ids"] > 0:
        raise ValueError(
            "Sales transactions contain null customer IDs. "
            "Resolve them before generating customer-level RFM features."
        )

    if quality_report["null_transaction_dates"] > 0:
        raise ValueError(
            "Sales transactions contain null dates. "
            "Resolve them before generating RFM features."
        )

    if quality_report["invalid_transaction_dates"] > 0:
        raise ValueError(
            "Sales transactions contain invalid dates. "
            "Inspect the source data before continuing."
        )

    if quality_report["null_total_values"] > 0:
        raise ValueError(
            "Sales transactions contain null total_value values. "
            "Resolve their monetary meaning before calculating RFM."
        )

    if quality_report["invalid_total_values"] > 0:
        raise ValueError(
            "Some total_value entries cannot be converted to numbers."
        )

    logger.info("Determining the dataset's latest transaction date.")

    latest_date_result = con.execute(
        f"""
        SELECT MAX(TRY_CAST(date AS DATE))
        FROM read_parquet('{escaped_glob}')
        """
    ).fetchone()

    latest_date = latest_date_result[0]

    if latest_date is None:
        raise ValueError(
            "Could not determine the latest transaction date."
        )

    # Use the day after the latest transaction as the reference date.
    # This avoids assigning zero recency to every customer who purchased
    # on the final date of the dataset.
    reference_date = latest_date.replace(
        day=latest_date.day
    )

    from datetime import timedelta

    reference_date = reference_date + timedelta(days=1)

    logger.info("Latest transaction date: %s", latest_date)
    logger.info("RFM reference date: %s", reference_date)

    reference_date_sql = reference_date.isoformat()

    logger.info("Aggregating customer-level RFM features.")

    rfm_df = con.execute(
        f"""
        WITH transaction_data AS (
            SELECT
                customer_id,
                receipt_id,
                TRY_CAST(date AS DATE) AS transaction_date,
                TRY_CAST(total_value AS DOUBLE) AS total_value

            FROM read_parquet('{escaped_glob}')
        ),

        customer_aggregation AS (
            SELECT
                customer_id AS cust_id,

                MAX(transaction_date) AS last_purchase_date,

                COUNT(DISTINCT receipt_id) AS frequency_receipts,

                SUM(total_value) AS monetary_value

            FROM transaction_data

            GROUP BY customer_id
        )

        SELECT
            cust_id,

            DATE_DIFF(
                'day',
                last_purchase_date,
                DATE '{reference_date_sql}'
            ) AS recency_days,

            frequency_receipts,

            monetary_value

        FROM customer_aggregation

        ORDER BY cust_id
        """
    ).fetchdf()

    if rfm_df.empty:
        raise ValueError(
            "RFM aggregation returned no customer records."
        )

    if rfm_df["cust_id"].isna().any():
        raise ValueError(
            "Generated RFM data contains null customer IDs."
        )

    if rfm_df["cust_id"].duplicated().any():
        raise ValueError(
            "Generated RFM data contains duplicate customer IDs."
        )

    if rfm_df[
        ["recency_days", "frequency_receipts", "monetary_value"]
    ].isna().any().any():
        raise ValueError(
            "Generated RFM features contain null values."
        )

    if (rfm_df["recency_days"] < 0).any():
        raise ValueError(
            "Generated RFM data contains negative recency values."
        )

    if (rfm_df["frequency_receipts"] < 0).any():
        raise ValueError(
            "Generated RFM data contains negative purchase frequencies."
        )

    if (rfm_df["monetary_value"] < 0).any():
        logger.warning(
            "Negative monetary values were found. "
            "They have not been removed or altered."
        )

    # Save the customer-level feature dataset.
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    rfm_df.to_parquet(OUTPUT_FILE, index=False)

    logger.info("Generated customer records: %s", len(rfm_df))
    logger.info("Saved RFM dataset: %s", OUTPUT_FILE)

    return {
        "rfm_df": rfm_df,
        "quality_report": quality_report,
        "latest_transaction_date": latest_date.isoformat(),
        "reference_date": reference_date.isoformat(),
    }


# ============================================================
# MAIN
# ============================================================

def main() -> int:
    """Generate RFM features and track the run in MLflow."""

    logger.info("=" * 70)
    logger.info("RetailPulse — F02 Customer Feature Engineering")
    logger.info("=" * 70)

    sales_files = get_sales_files()

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    parquet_glob = str(SALES_DIR / "*.parquet").replace("\\", "/")

    logger.info("Sales Parquet files found: %s", len(sales_files))
    logger.info("Sales directory: %s", SALES_DIR)

    con = duckdb.connect()

    try:
        con.execute(f"SET memory_limit = '{MEMORY_LIMIT}'")
        con.execute(f"SET threads = {THREADS}")

        validate_source_schema(con, parquet_glob)

        # Generate the RFM data first. A failed MLflow connection should
        # not prevent local feature generation from completing.
        result = generate_rfm(con, parquet_glob)

        rfm_df = result["rfm_df"]
        quality_report = result["quality_report"]

        report = {
            "module": "F02-Customer-Feature-Engineering",
            "status": "SUCCESS",
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "input_directory": str(SALES_DIR),
            "input_parquet_files": len(sales_files),
            "output_file": str(OUTPUT_FILE),
            "transaction_rows": quality_report["transaction_rows"],
            "customer_count": int(len(rfm_df)),
            "latest_transaction_date": result[
                "latest_transaction_date"
            ],
            "reference_date": result["reference_date"],
            "feature_columns": [
                "cust_id",
                "recency_days",
                "frequency_receipts",
                "monetary_value",
            ],
            "source_quality": quality_report,
            "rfm_summary": {
                column: {
                    "min": float(rfm_df[column].min()),
                    "median": float(rfm_df[column].median()),
                    "mean": float(rfm_df[column].mean()),
                    "max": float(rfm_df[column].max()),
                }
                for column in [
                    "recency_days",
                    "frequency_receipts",
                    "monetary_value",
                ]
            },
        }

        REPORT_FILE.write_text(
            json.dumps(report, indent=2),
            encoding="utf-8",
        )

        logger.info("Saved feature engineering report: %s", REPORT_FILE)

        # ----------------------------------------------------
        # MLFLOW TRACKING
        # ----------------------------------------------------

        try:
            mlflow.set_tracking_uri(TRACKING_URI)
            mlflow.set_experiment(EXPERIMENT_NAME)

            with mlflow.start_run(
                run_name="customer-rfm-feature-engineering"
            ):
                mlflow.set_tags(
                    {
                        "project": "RetailPulse",
                        "module": "F02-Customer-Feature-Engineering",
                        "feature_group": "RFM",
                    }
                )

                mlflow.log_params(
                    {
                        "input_parquet_files": len(sales_files),
                        "memory_limit": MEMORY_LIMIT,
                        "threads": THREADS,
                        "recency_reference_rule": (
                            "day_after_latest_transaction"
                        ),
                        "frequency_definition": (
                            "distinct_receipt_id_count"
                        ),
                        "monetary_definition": (
                            "sum_of_total_value"
                        ),
                    }
                )

                mlflow.log_metrics(
                    {
                        "source_transaction_rows": quality_report[
                            "transaction_rows"
                        ],
                        "customer_count": len(rfm_df),
                        "null_customer_ids": quality_report[
                            "null_customer_ids"
                        ],
                        "invalid_transaction_dates": quality_report[
                            "invalid_transaction_dates"
                        ],
                    }
                )

                mlflow.log_artifact(
                    str(OUTPUT_FILE),
                    artifact_path="feature_data",
                )

                mlflow.log_artifact(
                    str(REPORT_FILE),
                    artifact_path="reports",
                )

            logger.info("MLflow tracking completed.")

        except Exception:
            logger.exception(
                "MLflow tracking failed. Local RFM output was saved, "
                "but the run was not successfully tracked."
            )

        logger.info("=" * 70)
        logger.info("FEATURE ENGINEERING COMPLETED")
        logger.info("Transactions processed: %s", quality_report[
            "transaction_rows"
        ])
        logger.info("Customers generated: %s", len(rfm_df))
        logger.info("Output: %s", OUTPUT_FILE)
        logger.info("Report: %s", REPORT_FILE)
        logger.info("=" * 70)

        return 0

    finally:
        con.close()


if __name__ == "__main__":
    raise SystemExit(main()) 