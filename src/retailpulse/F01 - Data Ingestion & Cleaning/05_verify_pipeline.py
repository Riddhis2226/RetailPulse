from pathlib import Path
import json

import pandas as pd
import pyarrow.parquet as pq


PROJECT_ROOT = Path(__file__).resolve().parents[3]

RAW_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
REPORT_DIR = PROJECT_ROOT / "reports"

INGESTION_REPORT_PATH = REPORT_DIR / "ingestion_report.json"
OUTPUT_PATH = REPORT_DIR / "pipeline_verification.json"

SMALL_FILES = [
    "customer_master",
    "inventory_snapshot",
    "promotions",
    "sku_inventory_flags",
    "sku_master",
    "store_master",
]

CHUNK_SIZE = 100_000


def count_csv_rows(path: Path) -> int:
    """Count CSV data rows without loading the entire file into memory."""
    if not path.exists():
        raise FileNotFoundError(f"Raw CSV not found: {path}")

    return sum(
        len(chunk)
        for chunk in pd.read_csv(
            path,
            chunksize=CHUNK_SIZE,
            low_memory=False,
        )
    )


def count_parquet_rows(path: Path) -> int:
    """Return the number of rows recorded in a Parquet file."""
    if not path.exists():
        raise FileNotFoundError(f"Processed Parquet file not found: {path}")

    return pq.ParquetFile(path).metadata.num_rows


def verify_small_dataset(name: str) -> dict:
    """Compare raw and processed row counts for a smaller dataset."""
    raw_path = RAW_DIR / f"{name}.csv"
    parquet_path = PROCESSED_DIR / f"{name}.parquet"

    raw_rows = count_csv_rows(raw_path)
    processed_rows = count_parquet_rows(parquet_path)

    passed = raw_rows == processed_rows

    result = {
        "dataset": name,
        "raw_rows": raw_rows,
        "processed_rows": processed_rows,
        "passed": passed,
    }

    print(
        f"{name}: raw={raw_rows:,}, "
        f"processed={processed_rows:,} "
        f"{'PASS' if passed else 'FAIL'}"
    )

    return result


def verify_sales_dataset() -> dict:
    """Compare raw sales row count with all processed Parquet parts."""
    raw_path = RAW_DIR / "sales_transactions.csv"
    sales_dir = PROCESSED_DIR / "sales_transactions"

    if not sales_dir.exists():
        raise FileNotFoundError(
            f"Processed sales directory not found: {sales_dir}"
        )

    parquet_files = sorted(sales_dir.glob("part-*.parquet"))

    if not parquet_files:
        raise FileNotFoundError(
            f"No Parquet parts found in: {sales_dir}"
        )

    raw_rows = count_csv_rows(raw_path)

    processed_rows = sum(
        count_parquet_rows(path)
        for path in parquet_files
    )

    passed = raw_rows == processed_rows

    result = {
        "dataset": "sales_transactions",
        "raw_rows": raw_rows,
        "processed_rows": processed_rows,
        "parquet_parts": len(parquet_files),
        "passed": passed,
    }

    print(
        f"sales_transactions: raw={raw_rows:,}, "
        f"processed={processed_rows:,}, "
        f"parts={len(parquet_files)} "
        f"{'PASS' if passed else 'FAIL'}"
    )

    return result


def main():
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    print("\nRETAILPULSE PIPELINE VERIFICATION")
    print("=" * 65)

    # Confirm that the ingestion report exists and is valid JSON.
    if not INGESTION_REPORT_PATH.exists():
        raise FileNotFoundError(
            f"Ingestion report not found: {INGESTION_REPORT_PATH}"
        )

    with INGESTION_REPORT_PATH.open("r", encoding="utf-8") as file:
        ingestion_report = json.load(file)

    results = []
    errors = []

    # Verify the six smaller datasets.
    for name in SMALL_FILES:
        try:
            results.append(verify_small_dataset(name))
        except Exception as exc:
            errors.append({
                "dataset": name,
                "error": str(exc),
            })
            print(f"{name}: ERROR — {exc}")

    # Verify the chunked sales dataset.
    try:
        results.append(verify_sales_dataset())
    except Exception as exc:
        errors.append({
            "dataset": "sales_transactions",
            "error": str(exc),
        })
        print(f"sales_transactions: ERROR — {exc}")

    all_passed = (
        len(results) == len(SMALL_FILES) + 1
        and not errors
        and all(result["passed"] for result in results)
    )

    output = {
        "all_row_counts_match": all_passed,
        "datasets_verified": len(results),
        "expected_datasets": len(SMALL_FILES) + 1,
        "datasets": results,
        "errors": errors,
        "ingestion_report_exists": True,
    }

    OUTPUT_PATH.write_text(
        json.dumps(output, indent=2),
        encoding="utf-8",
    )

    print("=" * 65)
    print("Overall result:", "PASS" if all_passed else "FAIL")
    print(f"Datasets verified: {len(results)}/7")
    print(f"Verification report: {OUTPUT_PATH}")

    if not all_passed:
        raise SystemExit(
            "Pipeline verification failed. Review the report before continuing."
        )


if __name__ == "__main__":
    main()