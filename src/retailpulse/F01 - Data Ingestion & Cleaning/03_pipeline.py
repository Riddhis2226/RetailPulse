"""
RetailPulse — Data Ingestion and Cleaning Pipeline
==================================================

Location:
    src/retailpulse/f01_data_pipeline/pipeline.py

Run from the repository root:
    $env:PYTHONPATH = "$PWD\\src"
    .venv\\Scripts\\python.exe -m retailpulse.f01_data_pipeline.pipeline

Input:
    data/raw/
        customer_master.csv
        inventory_snapshot.csv
        promotions.csv
        sales_transactions.csv
        sku_inventory_flags.csv
        sku_master.csv
        store_master.csv

Output:
    data/processed/
        customer_master.parquet
        inventory_snapshot.parquet
        promotions.parquet
        sku_inventory_flags.parquet
        sku_master.parquet
        store_master.parquet
        sales_transactions/
            part-00001.parquet
            ...

Report:
    reports/ingestion_report.json

Important:
- Source CSV files are not modified.
- Sales transactions are processed in chunks.
- Smaller datasets are loaded into memory.
- Existing generated sales output is removed before reprocessing.
- This pipeline does not perform deduplication or imputation.
"""

from __future__ import annotations

import json
import logging
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from .cleaning import clean_dataframe


# ============================================================
# CONFIGURATION
# ============================================================

# Repository layout:
# RetailPulse/
# ├── data/
# │   ├── raw/
# │   └── processed/
# ├── reports/
# └── src/
#     └── retailpulse/
#         └── f01_data_pipeline/
#             ├── cleaning.py
#             └── pipeline.py

PROJECT_ROOT = Path(__file__).resolve().parents[3]

RAW_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
REPORT_DIR = PROJECT_ROOT / "reports"

INGESTION_REPORT = REPORT_DIR / "ingestion_report.json"

CHUNK_SIZE = 100_000

DATASET_FILES = [
    "customer_master.csv",
    "inventory_snapshot.csv",
    "promotions.csv",
    "sales_transactions.csv",
    "sku_inventory_flags.csv",
    "sku_master.csv",
    "store_master.csv",
]


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)

logger = logging.getLogger("retailpulse.f01.pipeline")


# ============================================================
# HELPERS
# ============================================================

def validate_input_files() -> None:
    """Verify that all configured source CSV files exist."""

    missing_files = [
        RAW_DIR / filename
        for filename in DATASET_FILES
        if not (RAW_DIR / filename).is_file()
    ]

    if missing_files:
        missing_list = "\n".join(
            f"  - {path}"
            for path in missing_files
        )

        raise FileNotFoundError(
            "The following required datasets are missing:\n"
            f"{missing_list}\n\n"
            "Ensure all seven CSV files exist in data/raw."
        )


def get_missing_values(df: pd.DataFrame) -> dict[str, int]:
    """Return missing-value counts for columns containing missing data."""

    return {
        str(column): int(count)
        for column, count in df.isna().sum().items()
        if count > 0
    }


def relative_output_path(path: Path) -> str:
    """Return an output path relative to the repository root."""

    return str(path.relative_to(PROJECT_ROOT))


def write_ingestion_report(report: dict[str, Any]) -> None:
    """Persist the ingestion report as JSON."""

    REPORT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    try:
        INGESTION_REPORT.write_text(
            json.dumps(
                report,
                indent=2,
                ensure_ascii=False,
                default=str,
                allow_nan=False,
            )
            + "\n",
            encoding="utf-8",
        )

        logger.info(
            "Ingestion report saved to: %s",
            INGESTION_REPORT,
        )

    except (OSError, TypeError, ValueError):
        logger.exception(
            "Could not write the ingestion report."
        )
        raise


# ============================================================
# SMALL DATASET PROCESSING
# ============================================================

def process_small_file(
    filename: str,
    report: dict[str, Any],
) -> None:
    """
    Clean a smaller CSV and save it as a Parquet file.

    The entire dataset is loaded into Pandas memory.
    """

    source = RAW_DIR / filename

    destination = (
        PROCESSED_DIR
        / filename.replace(".csv", ".parquet")
    )

    logger.info("Processing dataset: %s", filename)

    if not source.is_file():
        raise FileNotFoundError(
            f"Source dataset not found: {source}"
        )

    started = time.perf_counter()

    df = pd.read_csv(
        source,
        low_memory=False,
    )

    original_rows = len(df)

    df = clean_dataframe(
        df,
        filename,
    )

    # Ensure the destination directory exists.
    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    df.to_parquet(
        destination,
        index=False,
        engine="pyarrow",
    )

    elapsed_seconds = round(
        time.perf_counter() - started,
        2,
    )

    report[filename] = {
        "status": "success",
        "source": relative_output_path(source),
        "rows_read": int(original_rows),
        "rows_written": int(len(df)),
        "rows_dropped": int(original_rows - len(df)),
        "columns_count": int(len(df.columns)),
        "columns": df.columns.tolist(),
        "missing_values": get_missing_values(df),
        "total_missing_cells": int(df.isna().sum().sum()),
        "output": relative_output_path(destination),
        "elapsed_seconds": elapsed_seconds,
        "data_modified": True,
    }

    logger.info(
        "Saved %s rows to %s",
        f"{len(df):,}",
        destination,
    )


# ============================================================
# LARGE SALES DATASET PROCESSING
# ============================================================

def process_sales_file(
    report: dict[str, Any],
) -> None:
    """
    Clean the sales CSV in chunks and write separate Parquet files.

    Only the current CSV chunk is loaded into memory.

    WARNING:
    The existing generated sales output directory is deleted before
    processing begins. The original CSV in data/raw is not deleted.
    """

    filename = "sales_transactions.csv"

    source = RAW_DIR / filename
    output_dir = PROCESSED_DIR / "sales_transactions"

    logger.info("Processing large dataset: %s", filename)
    logger.info("Chunk size: %s rows", f"{CHUNK_SIZE:,}")

    if not source.is_file():
        raise FileNotFoundError(
            f"Sales source dataset not found: {source}"
        )

    started = time.perf_counter()

    # Remove only the generated sales output directory.
    # Do not remove the original CSV or other processed datasets.
    if output_dir.exists():
        if not output_dir.is_dir():
            raise NotADirectoryError(
                "Expected the sales output path to be a directory: "
                f"{output_dir}"
            )

        logger.warning(
            "Removing previous generated sales output: %s",
            output_dir,
        )

        shutil.rmtree(output_dir)

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    rows_read = 0
    rows_written = 0
    total_missing: dict[str, int] = {}

    invalid_or_missing_dates = 0
    chunk_count = 0

    try:
        reader = pd.read_csv(
            source,
            chunksize=CHUNK_SIZE,
            low_memory=False,
        )

        for chunk_number, chunk in enumerate(
            reader,
            start=1,
        ):
            chunk_count = chunk_number

            original_chunk_rows = len(chunk)
            rows_read += original_chunk_rows

            # Clean the current chunk.
            chunk = clean_dataframe(
                chunk,
                filename,
            )

            # Count dates that are missing or invalid after cleaning.
            if "date" in chunk.columns:
                invalid_or_missing_dates += int(
                    chunk["date"].isna().sum()
                )

            # Aggregate missing values across all chunks.
            chunk_missing = chunk.isna().sum()

            for column, count in chunk_missing.items():
                if count:
                    total_missing[column] = (
                        total_missing.get(column, 0)
                        + int(count)
                    )

            output_file = (
                output_dir
                / f"part-{chunk_number:05d}.parquet"
            )

            chunk.to_parquet(
                output_file,
                index=False,
                engine="pyarrow",
            )

            rows_written += len(chunk)

            logger.info(
                "Chunk %s: %s rows written | Total: %s",
                chunk_number,
                f"{len(chunk):,}",
                f"{rows_written:,}",
            )

            # Release references to the current chunk before reading
            # the next chunk.
            del chunk

    except Exception:
        logger.exception(
            "Sales processing failed. "
            "The sales output directory may contain partial results."
        )
        raise

    elapsed_seconds = round(
        time.perf_counter() - started,
        2,
    )

    report[filename] = {
        "status": "success",
        "source": relative_output_path(source),
        "rows_read": rows_read,
        "rows_written": rows_written,
        "rows_dropped": rows_read - rows_written,
        "chunk_size": CHUNK_SIZE,
        "chunks_written": chunk_count,
        "invalid_or_missing_dates": invalid_or_missing_dates,
        "missing_values": total_missing,
        "total_missing_cells": sum(total_missing.values()),
        "output_directory": relative_output_path(output_dir),
        "elapsed_seconds": elapsed_seconds,
        "data_modified": True,
        "notes": [
            "Source CSV was not modified.",
            "Rows were cleaned and written in chunks.",
            "No deduplication was performed by this pipeline.",
            "No missing-value imputation was performed by this pipeline.",
        ],
    }

    logger.info(
        "Sales processing complete: %s rows written.",
        f"{rows_written:,}",
    )


# ============================================================
# MAIN PIPELINE
# ============================================================

def main() -> int:
    """Execute ingestion, cleaning, Parquet conversion, and reporting."""

    started_at = datetime.now(timezone.utc)

    report: dict[str, Any] = {
        "pipeline": "RetailPulse ingestion and cleaning",
        "dataset_source": "Local CSV files in data/raw",
        "repository_root": str(PROJECT_ROOT),
        "started_at_utc": started_at.isoformat(),
        "chunk_size": CHUNK_SIZE,
        "datasets_requested": len(DATASET_FILES),
        "files": {},
        "status": "running",
        "data_modified": True,
        "notes": [
            "Raw source CSV files are not modified.",
            "Processed Parquet outputs may be created or overwritten.",
            "Sales processing removes the previous generated sales output directory.",
            "The pipeline does not perform deduplication or imputation.",
        ],
    }

    logger.info("=" * 70)
    logger.info("RetailPulse — Ingestion and Cleaning Pipeline")
    logger.info("=" * 70)

    logger.info("Project root: %s", PROJECT_ROOT)
    logger.info("Raw data directory: %s", RAW_DIR)
    logger.info("Processed data directory: %s", PROCESSED_DIR)
    logger.info("Reports directory: %s", REPORT_DIR)

    PROCESSED_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    REPORT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    try:
        # Validate all source files before starting processing.
        validate_input_files()

        # Process each configured dataset.
        for filename in DATASET_FILES:
            logger.info("-" * 70)

            if filename == "sales_transactions.csv":
                process_sales_file(
                    report["files"],
                )
            else:
                process_small_file(
                    filename,
                    report["files"],
                )

        report["status"] = "success"

        logger.info("=" * 70)
        logger.info("PIPELINE COMPLETED SUCCESSFULLY")
        logger.info("=" * 70)

        return 0

    except Exception as error:
        report["status"] = "failed"
        report["error"] = (
            f"{type(error).__name__}: {error}"
        )

        logger.exception(
            "RetailPulse ingestion pipeline failed."
        )

        return 1

    finally:
        report["finished_at_utc"] = (
            datetime.now(timezone.utc).isoformat()
        )

        report["elapsed_seconds"] = round(
            (
                datetime.now(timezone.utc) - started_at
            ).total_seconds(),
            2,
        )

        report["datasets_completed"] = sum(
            1
            for file_report in report["files"].values()
            if file_report.get("status") == "success"
        )

        report["datasets_failed"] = sum(
            1
            for file_report in report["files"].values()
            if file_report.get("status") == "failed"
        )

        try:
            write_ingestion_report(report)
        except Exception:
            logger.exception(
                "The pipeline finished, but its report could not be saved."
            )


if __name__ == "__main__":
    raise SystemExit(main()) 