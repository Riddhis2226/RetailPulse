"""
RetailPulse — Dataset Inspection
================================

Inspects the seven datasets hosted on Hugging Face.

Location:
    src/retailpulse/f01_data_pipeline/inspect_datasets.py

Run from the repository root:
    .venv\\Scripts\\python.exe -m retailpulse.f01_data_pipeline.inspect_datasets

Outputs:
    reports/dataset_inspection/dataset_inspection_report.json
    reports/dataset_inspection/dataset_inspection_summary.txt

Important:
- Source datasets are not modified.
- The sales dataset is processed in chunks.
- Duplicate counts for sales are calculated within chunks only.
- Duplicate rows spanning different chunks are not detected.
- Missing values are reported but not imputed.
- Failed dataset inspections are recorded in both reports.
"""

from __future__ import annotations

import json
import logging
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from huggingface_hub import hf_hub_download


# ============================================================
# CONFIGURATION
# ============================================================

# Repository layout:
# RetailPulse/
# ├── reports/
# └── src/
#     └── retailpulse/
#         └── f01_data_pipeline/
#             └── inspect_datasets.py

ROOT = Path(__file__).resolve().parents[3]

REPO_ID = "RS2226/RetailPulse"
REPO_TYPE = "dataset"

REPORTS_DIR = ROOT / "reports" / "dataset_inspection"

JSON_REPORT = REPORTS_DIR / "dataset_inspection_report.json"
TEXT_REPORT = REPORTS_DIR / "dataset_inspection_summary.txt"

CHUNK_SIZE = 100_000

DATASETS = [
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

logger = logging.getLogger("retailpulse.f01.dataset_inspection")


# ============================================================
# HELPERS
# ============================================================

def json_safe(value: Any) -> Any:
    """
    Convert common Pandas and Python values into JSON-safe values.

    Handles missing values, NumPy scalars, timestamps, and non-finite
    floating-point values without assuming every object is scalar.
    """

    if value is None or value is pd.NA or value is pd.NaT:
        return None

    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()

    # Convert NumPy scalar types to their corresponding Python values.
    if hasattr(value, "item"):
        try:
            converted = value.item()

            # Avoid looping if .item() returns the same object.
            if converted is not value:
                return json_safe(converted)

        except (ValueError, TypeError):
            pass

    if isinstance(value, float):
        if not math.isfinite(value):
            return None
        return value

    if isinstance(value, (str, int, bool)):
        return value

    # Handle remaining scalar missing values safely.
    try:
        missing = pd.isna(value)

        if isinstance(missing, bool) and missing:
            return None

    except (TypeError, ValueError):
        pass

    # Preserve otherwise unsupported values as readable strings.
    return str(value)


def validate_dataset_filename(filename: str) -> None:
    """Ensure the requested dataset is in the configured allowlist."""

    if filename not in DATASETS:
        raise ValueError(
            f"Dataset is not configured for inspection: {filename}"
        )


def download_dataset(filename: str) -> Path:
    """Download or retrieve a cached dataset from Hugging Face."""

    validate_dataset_filename(filename)

    logger.info(
        "Downloading/retrieving %s from %s",
        filename,
        REPO_ID,
    )

    path = hf_hub_download(
        repo_id=REPO_ID,
        filename=filename,
        repo_type=REPO_TYPE,
    )

    file_path = Path(path)

    if not file_path.is_file():
        raise FileNotFoundError(
            f"Downloaded dataset file does not exist: {file_path}"
        )

    return file_path


def get_sample_rows(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Return up to three sample rows with JSON-safe values."""

    records = df.head(3).to_dict(orient="records")

    return [
        {
            str(column): json_safe(value)
            for column, value in record.items()
        }
        for record in records
    ]


# ============================================================
# SMALL DATASET INSPECTION
# ============================================================

def inspect_small_file(
    file_path: Path,
    filename: str,
) -> dict[str, Any]:
    """Inspect a dataset that is small enough to load into Pandas."""

    logger.info("Inspecting dataset: %s", filename)

    df = pd.read_csv(file_path)

    missing_counts = df.isna().sum()
    duplicate_rows = int(df.duplicated().sum())

    result: dict[str, Any] = {
        "filename": filename,
        "source_path": str(file_path),
        "inspection_method": "full_dataframe",
        "rows": int(len(df)),
        "columns_count": int(len(df.columns)),
        "columns": df.columns.tolist(),
        "data_types": {
            str(column): str(dtype)
            for column, dtype in df.dtypes.items()
        },
        "missing_values": {
            str(column): int(count)
            for column, count in missing_counts.items()
            if count > 0
        },
        "total_missing_cells": int(missing_counts.sum()),
        "duplicate_rows": duplicate_rows,
        "duplicate_scope": "entire_dataset",
        "sample_rows": get_sample_rows(df),
        "data_modified": False,
    }

    print(f"\n{'=' * 70}")
    print(f"FILE: {filename}")
    print(f"SHAPE: {df.shape}")
    print(f"{'=' * 70}")

    print("\nColumns and data types:")
    print(df.dtypes.to_string())

    print("\nMissing values:")
    nonzero_missing = missing_counts[missing_counts > 0]

    print(
        nonzero_missing.to_string()
        if not nonzero_missing.empty
        else "None"
    )

    print(f"\nDuplicate rows: {duplicate_rows:,}")

    print("\nFirst 3 rows:")
    print(df.head(3).to_string(index=False))

    return result


# ============================================================
# LARGE DATASET INSPECTION
# ============================================================

def inspect_large_file(
    file_path: Path,
    filename: str,
) -> dict[str, Any]:
    """
    Inspect a large CSV in chunks.

    Duplicate rows are counted within each chunk. Duplicate rows
    occurring in separate chunks are not detected.

    Memory use is bounded approximately by the configured chunk size,
    excluding Pandas and Python processing overhead.
    """

    logger.info(
        "Inspecting large dataset in chunks: %s",
        filename,
    )

    total_rows = 0
    total_duplicates_within_chunks = 0
    total_missing_cells = 0

    missing_counts: pd.Series | None = None
    columns: list[str] | None = None
    first_rows: pd.DataFrame | None = None

    # Record observed dtype representations for each column.
    observed_dtypes: dict[str, set[str]] = {}

    for chunk_number, chunk in enumerate(
        pd.read_csv(
            file_path,
            chunksize=CHUNK_SIZE,
        ),
        start=1,
    ):
        total_rows += len(chunk)

        if columns is None:
            columns = chunk.columns.tolist()

            first_rows = chunk.head(3).copy()

            missing_counts = pd.Series(
                0,
                index=columns,
                dtype="int64",
            )

        # Confirm that the CSV schema remains consistent.
        if chunk.columns.tolist() != columns:
            raise ValueError(
                f"Column structure changed in chunk {chunk_number} "
                f"of {filename}."
            )

        # Count missing cells.
        chunk_missing = chunk.isna().sum()

        missing_counts += chunk_missing
        total_missing_cells += int(chunk_missing.sum())

        # Count duplicate rows inside this chunk only.
        total_duplicates_within_chunks += int(
            chunk.duplicated().sum()
        )

        # Record all dtype representations observed across chunks.
        for column, dtype in chunk.dtypes.items():
            observed_dtypes.setdefault(
                str(column),
                set(),
            ).add(str(dtype))

        if chunk_number % 10 == 0:
            logger.info(
             "%s: processed %s rows",
                filename,
                f"{total_rows:,}",
            )

    if columns is None or missing_counts is None or first_rows is None:
        raise ValueError(
            f"The dataset is empty or could not be read: {filename}"
        )

    missing_values = {
        str(column): int(count)
        for column, count in missing_counts.items()
        if count > 0
    }

    # Retain all observed dtype representations rather than assuming
    # that the first chunk's inferred types apply to the entire file.
    dtype_summary = {
        column: sorted(dtypes)
        for column, dtypes in observed_dtypes.items()
    }

    result: dict[str, Any] = {
        "filename": filename,
        "source_path": str(file_path),
        "inspection_method": "chunked_csv",
        "chunk_size": CHUNK_SIZE,
        "rows": total_rows,
        "columns_count": len(columns),
        "columns": columns,
        "observed_data_types_by_chunk": dtype_summary,
        "missing_values": missing_values,
        "total_missing_cells": total_missing_cells,
        "duplicate_rows_within_chunks": (
            total_duplicates_within_chunks
        ),
        "duplicate_scope": "within_each_chunk_only",
        "cross_chunk_duplicates_checked": False,
        "sample_rows": get_sample_rows(first_rows),
        "data_modified": False,
        "notes": [
            (
                "Duplicate rows are counted within each chunk only."
            ),
            (
                "Duplicate rows spanning different chunks may not "
                "be detected."
            ),
            (
                "Data types are recorded as observed in each chunk "
                "because Pandas may infer different types across chunks."
            ),
        ],
    }

    print(f"\n{'=' * 70}")
    print(f"FILE: {filename}")
    print(f"{'=' * 70}")

    print(f"\nRows: {total_rows:,}")
    print(f"Columns: {len(columns)}")

    print("\nColumn names:")
    print(columns)

    print("\nObserved data types:")

    for column, dtypes in dtype_summary.items():
        print(f"  {column}: {', '.join(dtypes)}")

    print("\nMissing values:")

    if missing_values:
        print(pd.Series(missing_values).to_string())
    else:
        print("None")

    print(
        "\nDuplicate rows within individual chunks: "
        f"{total_duplicates_within_chunks:,}"
    )

    print("\nFirst 3 rows:")
    print(first_rows.to_string(index=False))

    print(
        "\nNote: Duplicate counts are calculated within chunks. "
        "Duplicates spanning different chunks are not detected."
    )

    return result


# ============================================================
# TEXT REPORT
# ============================================================

def build_text_report(
    results: dict[str, Any],
    failures: list[dict[str, str]],
) -> str:
    """Build a readable summary of inspection results and failures."""

    lines = [
        "RetailPulse — Dataset Inspection Summary",
        "=" * 70,
        f"Generated at UTC: {datetime.now(timezone.utc).isoformat()}",
        f"Hugging Face repository: {REPO_ID}",
        f"Datasets requested: {len(DATASETS)}",
        f"Datasets inspected successfully: {len(results)}",
        f"Datasets failed: {len(failures)}",
        "",
    ]

    # --------------------------------------------------------
    # Successful inspections
    # --------------------------------------------------------

    for filename, report in results.items():
        lines.extend(
            [
                "-" * 70,
                f"Dataset: {filename}",
                f"Method: {report['inspection_method']}",
                f"Rows: {report['rows']:,}",
                f"Columns: {report['columns_count']}",
                f"Missing cells: {report['total_missing_cells']:,}",
            ]
        )

        if report["inspection_method"] == "full_dataframe":
            lines.append(
                f"Duplicate rows: {report['duplicate_rows']:,}"
            )
        else:
            lines.append(
                "Duplicate rows within chunks: "
                f"{report['duplicate_rows_within_chunks']:,}"
            )

            lines.append(
                "Cross-chunk duplicates checked: No"
            )

        lines.append("")

        if report["missing_values"]:
            lines.append("Missing values by column:")

            for column, count in report["missing_values"].items():
                lines.append(f"  {column}: {count:,}")
        else:
            lines.append("Missing values by column: None")

        lines.append("")

    # --------------------------------------------------------
    # Failed inspections
    # --------------------------------------------------------

    lines.extend(
        [
            "-" * 70,
            "Inspection Failures",
            "-" * 70,
        ]
    )

    if failures:
        for failure in failures:
            lines.append(
                f"Dataset: {failure['filename']}"
            )
            lines.append(
                f"Error: {failure['error']}"
            )
            lines.append("")
    else:
        lines.extend(
            [
                "None",
                "",
            ]
        )

    # --------------------------------------------------------
    # Limitations
    # --------------------------------------------------------

    lines.extend(
        [
            "=" * 70,
            "Important:",
            "- Source datasets were not modified.",
            "- Sales duplicate counts are chunk-level only.",
            "- Cross-chunk duplicates are not detected.",
            "- Missing values are reported but not imputed.",
            "- Data types are inferred by Pandas.",
            "",
        ]
    )

    return "\n".join(lines)


# ============================================================
# MAIN
# ============================================================

def main() -> int:
    """Inspect all configured datasets and save reports."""

    logger.info("=" * 70)
    logger.info("RetailPulse — Dataset Inspection")
    logger.info("=" * 70)

    logger.info("Repository root: %s", ROOT)
    logger.info("Output directory: %s", REPORTS_DIR)

    # Ensure the output directory exists.
    REPORTS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    results: dict[str, Any] = {}
    failures: list[dict[str, str]] = []

    # --------------------------------------------------------
    # Inspect configured datasets
    # --------------------------------------------------------

    for filename in DATASETS:
        try:
            file_path = download_dataset(filename)

            if filename == "sales_transactions.csv":
                result = inspect_large_file(
                    file_path,
                    filename,
                )
            else:
                result = inspect_small_file(
                    file_path,
                    filename,
                )

            results[filename] = result

        except Exception as exc:
            logger.exception(
                "Inspection failed for %s",
                filename,
            )

            failures.append(
                {
                    "filename": filename,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )

    # --------------------------------------------------------
    # Build consolidated JSON report
    # --------------------------------------------------------

    report = {
        "metadata": {
            "project": "RetailPulse",
            "analysis": "Dataset inspection",
            "generated_at_utc": datetime.now(
                timezone.utc
            ).isoformat(),
            "repository_id": REPO_ID,
            "repository_type": REPO_TYPE,
            "datasets_requested": len(DATASETS),
            "datasets_inspected": len(results),
            "datasets_failed": len(failures),
            "data_modified": False,
        },
        "datasets": results,
        "failures": failures,
        "limitations": [
            (
                "Sales duplicate counts are calculated within chunks "
                "and may miss duplicates spanning different chunks."
            ),
            (
                "CSV data types are inferred by Pandas and may vary "
                "between chunks."
            ),
            (
                "Missing values are reported but not imputed."
            ),
        ],
    }

    # --------------------------------------------------------
    # Save reports
    # --------------------------------------------------------

    try:
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

        TEXT_REPORT.write_text(
            build_text_report(
                results,
                failures,
            ),
            encoding="utf-8",
        )

    except OSError:
        logger.exception(
            "Failed to write inspection reports."
        )
        return 1

    except (TypeError, ValueError):
        logger.exception(
            "Failed to serialize the inspection report as JSON."
        )
        return 1

    # --------------------------------------------------------
    # Final summary
    # --------------------------------------------------------

    logger.info("=" * 70)
    logger.info("DATASET INSPECTION FINISHED")
    logger.info("=" * 70)

    logger.info(
        "Datasets inspected successfully: %s/%s",
        len(results),
        len(DATASETS),
    )

    logger.info(
        "Datasets failed: %s",
        len(failures),
    )

    logger.info("JSON report: %s", JSON_REPORT)
    logger.info("Text report: %s", TEXT_REPORT)

    if failures:
        logger.warning(
            "Some datasets could not be inspected. "
            "Review the failures in the JSON and text reports."
        )
        return 1

    logger.info("All datasets inspected successfully.")

    return 0


if __name__ == "__main__":
    sys.exit(main())