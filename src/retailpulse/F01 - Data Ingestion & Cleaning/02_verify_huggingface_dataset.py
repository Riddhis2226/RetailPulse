"""
RetailPulse — Hugging Face Dataset Verification
================================================

Location:
    src/retailpulse/f01_data_pipeline/verify_huggingface_dataset.py

Run from the repository root:
    $env:PYTHONPATH = "$PWD\\src"
    .venv\\Scripts\\python.exe -m retailpulse.f01_data_pipeline.verify_huggingface_dataset

Dataset:
    Repository: RS2226/RetailPulse
    File: customer_master.csv

Purpose:
    - Download or retrieve the dataset from the Hugging Face cache.
    - Verify that the downloaded file exists.
    - Load the CSV using Pandas.
    - Display dataset dimensions, columns, and sample rows.

Important:
    - The source dataset is not modified.
    - The downloaded file is stored in the Hugging Face cache.
    - This script does not write files into data/raw or data/processed.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import pandas as pd
from huggingface_hub import hf_hub_download


# ============================================================
# CONFIGURATION
# ============================================================

REPO_ID = "RS2226/RetailPulse"
REPO_TYPE = "dataset"
FILENAME = "customer_master.csv"

SAMPLE_ROWS = 5


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)

logger = logging.getLogger(
    "retailpulse.f01.huggingface_verification"
)


# ============================================================
# MAIN
# ============================================================

def main() -> int:
    """Download and inspect the customer master dataset."""

    logger.info("=" * 65)
    logger.info("RetailPulse — Hugging Face Dataset Verification")
    logger.info("=" * 65)

    logger.info("Repository: %s", REPO_ID)
    logger.info("Dataset file: %s", FILENAME)

    try:
        # ----------------------------------------------------
        # Download or retrieve cached dataset
        # ----------------------------------------------------

        logger.info("Downloading or retrieving dataset from Hugging Face...")

        downloaded_path = hf_hub_download(
            repo_id=REPO_ID,
            filename=FILENAME,
            repo_type=REPO_TYPE,
        )

        file_path = Path(downloaded_path)

        if not file_path.is_file():
            raise FileNotFoundError(
                f"Downloaded dataset file does not exist: {file_path}"
            )

        logger.info(
            "Dataset retrieved successfully: %s",
            file_path,
        )

        # ----------------------------------------------------
        # Load dataset
        # ----------------------------------------------------

        logger.info("Loading CSV into Pandas...")

        df = pd.read_csv(file_path)

        if df.empty:
            logger.warning("The dataset contains no data rows.")

        # ----------------------------------------------------
        # Display inspection results
        # ----------------------------------------------------

        print("\n" + "=" * 65)
        print("DATASET VERIFICATION RESULTS")
        print("=" * 65)

        print(f"\nRepository: {REPO_ID}")
        print(f"Filename: {FILENAME}")
        print(f"Cached file path: {file_path}")

        print("\nDataset dimensions:")
        print(f"Rows: {len(df):,}")
        print(f"Columns: {len(df.columns):,}")

        print("\nColumn names:")
        for index, column in enumerate(df.columns, start=1):
            print(f"{index:>3}. {column}")

        print("\nData types:")
        print(df.dtypes.to_string())

        print("\nMissing values by column:")
        missing_values = df.isna().sum()
        missing_values = missing_values[missing_values > 0]

        if missing_values.empty:
            print("No missing values detected.")
        else:
            print(missing_values.to_string())

        print(f"\nFirst {SAMPLE_ROWS} rows:")
        print(df.head(SAMPLE_ROWS).to_string(index=False))

        print("\n" + "=" * 65)
        print("DATASET VERIFICATION COMPLETED")
        print("=" * 65)

        logger.info("Dataset loaded successfully.")

        return 0

    except Exception:
        logger.exception(
            "Dataset verification failed."
        )
        return 1


if __name__ == "__main__":
    sys.exit(main()) 