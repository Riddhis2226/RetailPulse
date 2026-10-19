"""
RetailPulse — Monetary Consistency Analysis
============================================

Checks monetary consistency in sales_transactions.csv.

Validations:
1. Compare total_value against quantity * unit_price.
2. Compare total_value against the expected discounted value.
3. Apply a configurable rounding tolerance.
4. Capture a sample of inconsistent transactions.
5. Report aggregate mismatch statistics.

Location:
    src/retailpulse/f01_data_pipeline/check_monetary_consistency.py

Run from the repository root:
    .venv\\Scripts\\python.exe -m retailpulse.f01_data_pipeline.check_monetary_consistency

Outputs:
    reports/monetary_consistency_report.json
    reports/monetary_consistency_samples.csv

Important:
- The source dataset is never modified.
- The complete sales dataset is processed in chunks.
- Only a limited sample of mismatches is retained.
- Monetary mismatches require investigation before correction.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from huggingface_hub import hf_hub_download


# ============================================================
# CONFIGURATION
# ============================================================

ROOT = Path(__file__).resolve().parents[3]

REPO_ID = "RS2226/RetailPulse"
REPO_TYPE = "dataset"
DATASET_FILENAME = "sales_transactions.csv"

REPORTS_DIR = ROOT / "reports"

JSON_REPORT = REPORTS_DIR / "monetary_consistency_report.json"
CSV_REPORT = REPORTS_DIR / "monetary_consistency_samples.csv"

CHUNK_SIZE = 200_000
TOLERANCE = 0.02
MAX_SAMPLES = 30

COLUMNS = [
    "date",
    "receipt_id",
    "store_id",
    "sku_id",
    "customer_id",
    "quantity",
    "unit_price",
    "total_value",
    "discount_pct",
    "promo_id",
]

# Only these columns are required for the calculations.
REQUIRED_COLUMNS = [
    "date",
    "receipt_id",
    "sku_id",
    "quantity",
    "unit_price",
    "total_value",
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

logger = logging.getLogger("retailpulse.f01.monetary_consistency")


# ============================================================
# HELPERS
# ============================================================

def download_sales_dataset() -> Path:
    """Download or retrieve the sales CSV from Hugging Face."""

    logger.info(
        "Retrieving %s from %s",
        DATASET_FILENAME,
        REPO_ID,
    )

    path = hf_hub_download(
        repo_id=REPO_ID,
        filename=DATASET_FILENAME,
        repo_type=REPO_TYPE,
    )

    file_path = Path(path)

    if not file_path.is_file():
        raise FileNotFoundError(
            f"Sales dataset was not found: {file_path}"
        )

    return file_path


def validate_columns(path: Path) -> None:
    """Check that the source CSV contains all required columns."""

    available_columns = pd.read_csv(
        path,
        nrows=0,
    ).columns.tolist()

    missing_columns = [
        column
        for column in REQUIRED_COLUMNS
        if column not in available_columns
    ]

    if missing_columns:
        raise ValueError(
            "Sales dataset is missing required columns: "
            f"{missing_columns}"
        )


def json_safe(value: Any) -> Any:
    """Convert values to JSON-compatible representations."""

    if hasattr(value, "item"):
        value = value.item()

    if pd.isna(value):
        return None

    if isinstance(value, (str, int, float, bool)):
        return value

    if hasattr(value, "isoformat"):
        return value.isoformat()

    return str(value)


# ============================================================
# MONETARY ANALYSIS
# ============================================================

def analyze_monetary_consistency(
    path: Path,
) -> tuple[dict[str, Any], pd.DataFrame]:
    """
    Analyze monetary consistency without loading the entire CSV.

    A row is considered inconsistent when its absolute monetary
    difference exceeds TOLERANCE.

    Two calculations are evaluated:
    - Undiscounted gross value.
    - Expected value after discount.

    The checks are independent: a mismatch against gross value
    may be explained by a legitimate discount.
    """

    total_rows = 0
    invalid_numeric_rows = 0

    gross_mismatch_rows = 0
    discounted_mismatch_rows = 0

    gross_absolute_error_sum = 0.0
    discounted_absolute_error_sum = 0.0

    gross_max_absolute_error = 0.0
    discounted_max_absolute_error = 0.0

    gross_samples: list[pd.DataFrame] = []
    discounted_samples: list[pd.DataFrame] = []

    logger.info("Starting monetary consistency analysis.")
    logger.info("Chunk size: %s", f"{CHUNK_SIZE:,}")
    logger.info("Tolerance: %.4f", TOLERANCE)

    for chunk_number, chunk in enumerate(
        pd.read_csv(
            path,
            usecols=REQUIRED_COLUMNS,
            chunksize=CHUNK_SIZE,
        ),
        start=1,
    ):
        total_rows += len(chunk)

        # Convert monetary and quantity columns explicitly.
        numeric_columns = [
            "quantity",
            "unit_price",
            "total_value",
            "discount_pct",
        ]

        for column in numeric_columns:
            chunk[column] = pd.to_numeric(
                chunk[column],
                errors="coerce",
            )

        numeric_valid = (
            chunk[numeric_columns].notna().all(axis=1)
        )

        # Exclude rows with invalid numeric values from monetary
        # comparisons, but count them for separate investigation.
        invalid_numeric_rows += int((~numeric_valid).sum())

        valid = chunk.loc[numeric_valid].copy()

        if valid.empty:
            continue

        # ----------------------------------------------------
        # 1. EXPECTED GROSS VALUE
        # ----------------------------------------------------

        valid["gross_value"] = (
            valid["quantity"] * valid["unit_price"]
        )

        valid["gross_absolute_difference"] = (
            valid["total_value"] - valid["gross_value"]
        ).abs()

        gross_mismatch = (
            valid["gross_absolute_difference"] > TOLERANCE
        )

        # ----------------------------------------------------
        # 2. EXPECTED DISCOUNTED VALUE
        # ----------------------------------------------------

        valid["expected_after_discount"] = (
            valid["gross_value"]
            * (1 - valid["discount_pct"] / 100)
        )

        valid["discounted_absolute_difference"] = (
            valid["total_value"]
            - valid["expected_after_discount"]
        ).abs()

        discounted_mismatch = (
            valid["discounted_absolute_difference"] > TOLERANCE
        )

        # ----------------------------------------------------
        # 3. AGGREGATE STATISTICS
        # ----------------------------------------------------

        gross_mismatch_rows += int(gross_mismatch.sum())

        discounted_mismatch_rows += int(
            discounted_mismatch.sum()
        )

        gross_absolute_error_sum += float(
            valid["gross_absolute_difference"].sum()
        )

        discounted_absolute_error_sum += float(
            valid["discounted_absolute_difference"].sum()
        )

        gross_max_absolute_error = max(
            gross_max_absolute_error,
            float(valid["gross_absolute_difference"].max()),
        )

        discounted_max_absolute_error = max(
            discounted_max_absolute_error,
            float(valid["discounted_absolute_difference"].max()),
        )

        # ----------------------------------------------------
        # 4. RETAIN LIMITED SAMPLES
        # ----------------------------------------------------

        sample_columns = [
            "date",
            "receipt_id",
            "sku_id",
            "quantity",
            "unit_price",
            "total_value",
            "discount_pct",
            "promo_id",
            "gross_value",
            "expected_after_discount",
            "gross_absolute_difference",
            "discounted_absolute_difference",
        ]

        if gross_mismatch.any() and sum(
            len(frame) for frame in gross_samples
        ) < MAX_SAMPLES:
            remaining = MAX_SAMPLES - sum(
                len(frame) for frame in gross_samples
            )

            gross_samples.append(
                valid.loc[gross_mismatch, sample_columns]
                .head(remaining)
                .assign(mismatch_type="gross_value")
            )

        if discounted_mismatch.any() and sum(
            len(frame) for frame in discounted_samples
        ) < MAX_SAMPLES:
            remaining = MAX_SAMPLES - sum(
                len(frame) for frame in discounted_samples
            )

            discounted_samples.append(
                valid.loc[discounted_mismatch, sample_columns]
                .head(remaining)
                .assign(mismatch_type="discounted_value")
            )

        if chunk_number % 10 == 0:
            logger.info(
                "Processed %,d rows.",
                total_rows,
            )

    # --------------------------------------------------------
    # 5. BUILD SAMPLE OUTPUT
    # --------------------------------------------------------

    samples: list[pd.DataFrame] = []

    if gross_samples:
        samples.append(pd.concat(gross_samples, ignore_index=True))

    if discounted_samples:
        samples.append(
            pd.concat(discounted_samples, ignore_index=True)
        )

    if samples:
        sample_df = pd.concat(
            samples,
            ignore_index=True,
        )
    else:
        sample_df = pd.DataFrame(
            columns=[
                *REQUIRED_COLUMNS,
                "gross_value",
                "expected_after_discount",
                "gross_absolute_difference",
                "discounted_absolute_difference",
                "mismatch_type",
            ]
        )

    # --------------------------------------------------------
    # 6. BUILD REPORT
    # --------------------------------------------------------

    valid_rows = total_rows - invalid_numeric_rows

    report = {
        "metadata": {
            "project": "RetailPulse",
            "analysis": "Monetary consistency analysis",
            "generated_at_utc": datetime.now(
                timezone.utc
            ).isoformat(),
            "repository_id": REPO_ID,
            "source_filename": DATASET_FILENAME,
            "chunk_size": CHUNK_SIZE,
            "tolerance": TOLERANCE,
            "data_modified": False,
        },
        "dataset": {
            "total_rows_processed": total_rows,
            "valid_numeric_rows": valid_rows,
            "invalid_numeric_rows": invalid_numeric_rows,
        },
        "gross_value_check": {
            "formula": "quantity * unit_price",
            "mismatch_rows": gross_mismatch_rows,
            "mismatch_percentage": round(
                gross_mismatch_rows / valid_rows * 100,
                6,
            ) if valid_rows else 0.0,
            "sum_absolute_difference": round(
                gross_absolute_error_sum,
                4,
            ),
            "maximum_absolute_difference": round(
                gross_max_absolute_error,
                4,
            ),
        },
        "discounted_value_check": {
            "formula": (
                "quantity * unit_price * (1 - discount_pct / 100)"
            ),
            "mismatch_rows": discounted_mismatch_rows,
            "mismatch_percentage": round(
                discounted_mismatch_rows / valid_rows * 100,
                6,
            ) if valid_rows else 0.0,
            "sum_absolute_difference": round(
                discounted_absolute_error_sum,
                4,
            ),
            "maximum_absolute_difference": round(
                discounted_max_absolute_error,
                4,
            ),
        },
        "interpretation": (
            "A gross-value mismatch is not necessarily an error because "
            "discounts may explain the difference. The discounted-value "
            "check is the primary consistency check, assuming total_value "
            "is defined as the transaction value after discount. Confirm "
            "the dataset's monetary semantics before correcting records."
        ),
        "limitations": [
            (
                "Invalid numeric rows are excluded from monetary "
                "comparisons and counted separately."
            ),
            (
                "This script does not validate discount ranges or "
                "whether each promotion was applicable."
            ),
            (
                "Only a limited sample of mismatches is exported."
            ),
        ],
    }

    return report, sample_df


# ============================================================
# MAIN
# ============================================================

def main() -> int:
    """Run monetary consistency checks and save reports."""

    logger.info("=" * 70)
    logger.info("RetailPulse — Monetary Consistency Analysis")
    logger.info("=" * 70)

    REPORTS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    try:
        sales_path = download_sales_dataset()
        validate_columns(sales_path)

        report, samples = analyze_monetary_consistency(
            sales_path
        )

        JSON_REPORT.write_text(
            json.dumps(
                report,
                indent=2,
                ensure_ascii=False,
                default=json_safe,
            )
            + "\n",
            encoding="utf-8",
        )

        samples.to_csv(
            CSV_REPORT,
            index=False,
            encoding="utf-8-sig",
        )

        logger.info("=" * 70)
        logger.info("MONETARY CONSISTENCY ANALYSIS COMPLETED")
        logger.info("=" * 70)

        logger.info(
            "Rows processed: %s",
            f"{report['dataset']['total_rows_processed']:,}",
        )

        logger.info(
            "Gross-value mismatches: %s",
            f"{report['gross_value_check']['mismatch_rows']:,}",
        )

        logger.info(
            "Discounted-value mismatches: %s",
            f"{report['discounted_value_check']['mismatch_rows']:,}",
        )

        logger.info(
            "Invalid numeric rows: %s",
            f"{report['dataset']['invalid_numeric_rows']:,}",
        )

        logger.info("JSON report: %s", JSON_REPORT)
        logger.info("CSV samples: %s", CSV_REPORT)
        logger.info("Source data was not modified.")

        return 0

    except Exception:
        logger.exception(
            "Monetary consistency analysis failed."
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())