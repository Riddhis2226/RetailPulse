"""
RetailPulse — Consolidated F01 Data-Quality Reports
===================================================

Consolidates existing F01 reports into a single JSON report
and CSV summary.

Location:
    src/retailpulse/f01_data_pipeline/consolidate_quality_reports.py

Run from the repository root:
    set PYTHONPATH=src
    .venv\\Scripts\\python.exe -m retailpulse.f01_data_pipeline.consolidate_quality_reports

Outputs:
    reports/consolidated_data_quality_report.json
    reports/consolidated_data_quality_summary.csv

Important:
- Reads existing reports only.
- Does not rescan datasets.
- Does not rerun validation or analytical checks.
- Does not modify source datasets.
- Reports missing input files rather than silently ignoring them.
- Extracts key findings using explicit report structures.
- Validates the generated report's key metrics before completion.
"""

from __future__ import annotations

import csv
import json
import logging
import re
import sys

from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ============================================================
# PROJECT CONFIGURATION
# ============================================================

# File location:
# RetailPulse/src/retailpulse/f01_data_pipeline/
#
# parents[0] = f01_data_pipeline
# parents[1] = retailpulse
# parents[2] = src
# parents[3] = RetailPulse

ROOT = Path(__file__).resolve().parents[3]

REPORTS_DIR = ROOT / "reports"

OUTPUT_JSON = REPORTS_DIR / "consolidated_data_quality_report.json"
OUTPUT_CSV = REPORTS_DIR / "consolidated_data_quality_summary.csv"


# Existing report locations relative to the repository root.
INPUTS: dict[str, Path] = {
    "ingestion": REPORTS_DIR / "ingestion_report.json",
    "pipeline_verification": REPORTS_DIR / "pipeline_verification.json",
    "referential_integrity": (
        REPORTS_DIR / "referential_integrity_report.json"
    ),
    "duplicate_analysis": REPORTS_DIR / "duplicate_analysis.json",
    "missing_values": REPORTS_DIR / "missing_values_report.json",
    "validation_summary": REPORTS_DIR / "f01_validation_summary.txt",
}


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)

logger = logging.getLogger("retailpulse.f01.quality_report")


# ============================================================
# FILE LOADING
# ============================================================

def load_json(path: Path) -> dict[str, Any]:
    """Load a JSON report and validate its top-level structure."""

    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)

    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Invalid JSON in report '{path}': {exc}"
        ) from exc

    if not isinstance(data, dict):
        raise ValueError(
            f"Expected a JSON object in report: {path}"
        )

    return data


def load_report(
    name: str,
    path: Path,
) -> dict[str, Any]:
    """Load a JSON or text report based on its configured name."""

    if name == "validation_summary":
        text = path.read_text(encoding="utf-8")
        return parse_validation_text(text)

    return load_json(path)


# ============================================================
# REPORT PARSING
# ============================================================

def parse_validation_text(text: str) -> dict[str, Any]:
    """
    Extract validation counts from the existing text summary.

    Expected source format:
        Overall status: PASS
        Checks passed: 20
        Checks failed: 0

    Missing metrics remain absent rather than being invented.
    """

    result: dict[str, Any] = {
        "raw_summary": text.strip(),
    }

    patterns = {
        "overall_status": (
            r"^\s*Overall status:\s*(.+?)\s*$"
        ),
        "passed_checks": (
            r"^\s*Checks passed:\s*(\d+)\s*$"
        ),
        "failed_checks": (
            r"^\s*Checks failed:\s*(\d+)\s*$"
        ),
        "warnings": (
            r"^\s*Warnings:\s*(\d+)\s*$"
        ),
    }

    for key, pattern in patterns.items():
        match = re.search(
            pattern,
            text,
            flags=re.IGNORECASE | re.MULTILINE,
        )

        if match:
            value = match.group(1).strip()

            if key in {"passed_checks", "failed_checks", "warnings"}:
                result[key] = int(value)
            else:
                result[key] = value

    return result


def flatten_scalars(
    obj: Any,
    prefix: str = "",
) -> list[dict[str, Any]]:
    """Flatten nested dictionaries and lists into CSV-compatible rows."""

    rows: list[dict[str, Any]] = []

    if isinstance(obj, dict):
        for key, value in obj.items():
            path = f"{prefix}.{key}" if prefix else str(key)

            if isinstance(value, (dict, list)):
                rows.extend(
                    flatten_scalars(value, path)
                )
            else:
                rows.append(
                    {
                        "section": prefix or "root",
                        "metric": path,
                        "value": value,
                    }
                )

    elif isinstance(obj, list):
        for index, value in enumerate(obj):
            path = f"{prefix}[{index}]"

            if isinstance(value, (dict, list)):
                rows.extend(
                    flatten_scalars(value, path)
                )
            else:
                rows.append(
                    {
                        "section": prefix or "root",
                        "metric": path,
                        "value": value,
                    }
                )

    else:
        rows.append(
            {
                "section": prefix or "root",
                "metric": prefix or "value",
                "value": obj,
            }
        )

    return rows


# ============================================================
# SOURCE REPORT EXTRACTION
# ============================================================

def extract_sales_metrics(
    ingestion: dict[str, Any],
    verification: dict[str, Any],
) -> tuple[int | None, int | None]:
    """
    Extract sales row count and Parquet part count.

    Prefer the ingestion report, with pipeline verification as
    a fallback.
    """

    files = ingestion.get("files", {})

    sales_info = files.get(
        "sales_transactions.csv",
        {},
    )

    if not isinstance(sales_info, dict):
        sales_info = {}

    datasets = verification.get("datasets", [])

    if not isinstance(datasets, list):
        datasets = []

    sales_verification: dict[str, Any] = {}

    for dataset in datasets:
        if (
            isinstance(dataset, dict)
            and dataset.get("dataset") == "sales_transactions"
        ):
            sales_verification = dataset
            break

    sales_rows = sales_info.get("rows_written")

    if sales_rows is None:
        sales_rows = sales_info.get("rows_read")

    if sales_rows is None:
        sales_rows = sales_verification.get("processed_rows")

    parquet_parts = sales_info.get("chunks_written")

    if parquet_parts is None:
        parquet_parts = sales_verification.get("parquet_parts")

    return sales_rows, parquet_parts


def extract_duplicate_metrics(
    duplicates: dict[str, Any],
) -> dict[str, Any]:
    """Extract duplicate statistics from the duplicate-analysis report."""

    dataset = duplicates.get("dataset", {})

    if not isinstance(dataset, dict):
        dataset = {}

    return {
        "exact_duplicate_groups": dataset.get(
            "exact_duplicate_groups"
        ),
        "extra_duplicate_rows": dataset.get(
            "exact_duplicate_extra_rows"
        ),
        "rows_in_duplicate_groups": dataset.get(
            "rows_in_exact_duplicate_groups"
        ),
        "largest_duplicate_group_size": dataset.get(
            "largest_duplicate_group"
        ),
    }


def extract_missing_value_metrics(
    missing_values: dict[str, Any],
) -> dict[str, Any]:
    """
    Extract missing-value counts from known report structures.

    Supports the special-investigation fields and falls back
    to the corresponding dataset column counts.
    """

    investigations = missing_values.get(
        "special_investigations",
        {},
    )

    if not isinstance(investigations, dict):
        investigations = {}

    promo_info = investigations.get(
        "sales_promotion_ids",
        {},
    )

    inventory_info = investigations.get(
        "inventory_flag_date_windows",
        {},
    )

    if not isinstance(promo_info, dict):
        promo_info = {}

    if not isinstance(inventory_info, dict):
        inventory_info = {}

    datasets = missing_values.get("datasets", {})

    if not isinstance(datasets, dict):
        datasets = {}

    # Fallback for sales promotion IDs.
    sales_dataset = datasets.get(
        "sales_transactions",
        {},
    )

    if not isinstance(sales_dataset, dict):
        sales_dataset = {}

    sales_columns = sales_dataset.get(
        "columns",
        {},
    )

    if not isinstance(sales_columns, dict):
        sales_columns = {}

    promo_column = sales_columns.get(
        "promo_id",
        {},
    )

    if not isinstance(promo_column, dict):
        promo_column = {}

    missing_sales_promo_ids = promo_info.get(
        "missing_promo_ids"
    )

    if missing_sales_promo_ids is None:
        missing_sales_promo_ids = promo_column.get(
            "missing_count"
        )

    # Fallback for inventory flag dates.
    flags_dataset = datasets.get(
        "sku_inventory_flags",
        {},
    )

    if not isinstance(flags_dataset, dict):
        flags_dataset = {}

    flags_columns = flags_dataset.get(
        "columns",
        {},
    )

    if not isinstance(flags_columns, dict):
        flags_columns = {}

    start_column = flags_columns.get(
        "window_start",
        {},
    )

    end_column = flags_columns.get(
        "window_end",
        {},
    )

    if not isinstance(start_column, dict):
        start_column = {}

    if not isinstance(end_column, dict):
        end_column = {}

    missing_window_start = inventory_info.get(
        "missing_window_start"
    )

    if missing_window_start is None:
        missing_window_start = start_column.get(
            "missing_count"
        )

    missing_window_end = inventory_info.get(
        "missing_window_end"
    )

    if missing_window_end is None:
        missing_window_end = end_column.get(
            "missing_count"
        )

    return {
        "missing_sales_promo_id_cells": missing_sales_promo_ids,
        "missing_sku_inventory_flags_window_start_cells": (
            missing_window_start
        ),
        "missing_sku_inventory_flags_window_end_cells": (
            missing_window_end
        ),
    }


# ============================================================
# KEY FINDINGS
# ============================================================

def build_key_findings(
    loaded: dict[str, Any],
) -> dict[str, Any]:
    """Extract important metrics using explicit report structures."""

    ingestion = loaded.get("ingestion", {})
    verification = loaded.get("pipeline_verification", {})
    duplicates = loaded.get("duplicate_analysis", {})
    missing_values = loaded.get("missing_values", {})

    # --------------------------------------------------------
    # Sales metrics
    # --------------------------------------------------------

    sales_rows, parquet_parts = extract_sales_metrics(
        ingestion,
        verification,
    )

    # --------------------------------------------------------
    # Duplicate metrics
    # --------------------------------------------------------

    duplicate_metrics = extract_duplicate_metrics(
        duplicates
    )

    # --------------------------------------------------------
    # Missing-value metrics
    # --------------------------------------------------------

    missing_metrics = extract_missing_value_metrics(
        missing_values
    )

    return {
        "sales_transactions_rows": sales_rows,
        "sales_parquet_parts": parquet_parts,
        **duplicate_metrics,
        **missing_metrics,
        "important_caveat": (
            "Duplicate rows have not been deleted. Missing promotion IDs "
            "and inventory-flag dates require business interpretation "
            "before imputation or removal. A null metric means the "
            "corresponding value could not be extracted from the "
            "existing report structure."
        ),
    }


# ============================================================
# CONSISTENCY CHECKS
# ============================================================

def validate_consolidated_metrics(
    loaded: dict[str, Any],
    consolidated: dict[str, Any],
) -> list[str]:
    """
    Check consistency between extracted metrics and source reports.

    These checks inspect existing report content only. They do not
    rescan datasets or rerun the underlying analyses.
    """

    errors: list[str] = []

    status = consolidated.get("status", {})
    findings = consolidated.get("key_findings", {})

    validation = loaded.get("validation_summary", {})

    ingestion = loaded.get("ingestion", {})
    verification = loaded.get("pipeline_verification", {})
    duplicates = loaded.get("duplicate_analysis", {})
    missing_values = loaded.get("missing_values", {})

    # --------------------------------------------------------
    # Validation summary
    # --------------------------------------------------------

    passed = validation.get("passed_checks")
    failed = validation.get("failed_checks")

    if passed is None:
        errors.append(
            "Validation summary is missing the passed-check count."
        )

    if failed is None:
        errors.append(
            "Validation summary is missing the failed-check count."
        )

    # --------------------------------------------------------
    # Sales metrics
    # --------------------------------------------------------

    sales_rows, parquet_parts = extract_sales_metrics(
        ingestion,
        verification,
    )

    if sales_rows is None:
        errors.append(
            "Sales transaction row count could not be extracted."
        )

    if parquet_parts is None:
        errors.append(
            "Sales Parquet part count could not be extracted."
        )

    if sales_rows is not None and parquet_parts is not None:
        datasets = verification.get("datasets", [])

        if isinstance(datasets, list):
            for dataset in datasets:
                if (
                    isinstance(dataset, dict)
                    and dataset.get("dataset") == "sales_transactions"
                ):
                    verified_rows = dataset.get("processed_rows")

                    if (
                        verified_rows is not None
                        and sales_rows != verified_rows
                    ):
                        errors.append(
                            "Sales row count differs between ingestion "
                            "and pipeline verification reports."
                        )

                    verified_parts = dataset.get("parquet_parts")

                    if (
                        verified_parts is not None
                        and parquet_parts != verified_parts
                    ):
                        errors.append(
                            "Sales Parquet part count differs between "
                            "ingestion and pipeline verification reports."
                        )

    # --------------------------------------------------------
    # Duplicate metrics
    # --------------------------------------------------------

    duplicate_metrics = extract_duplicate_metrics(
        duplicates
    )

    for metric, value in duplicate_metrics.items():
        if value is None:
            errors.append(
                f"Duplicate metric could not be extracted: {metric}"
            )

    # --------------------------------------------------------
    # Missing-value metrics
    # --------------------------------------------------------

    missing_metrics = extract_missing_value_metrics(
        missing_values
    )

    for metric, value in missing_metrics.items():
        if value is None:
            errors.append(
                f"Missing-value metric could not be extracted: {metric}"
            )

    # --------------------------------------------------------
    # Consolidated report checks
    # --------------------------------------------------------

    if status.get("validation_checks_passed") != passed:
        errors.append(
            "Consolidated passed-check count does not match the source."
        )

    if status.get("validation_checks_failed") != failed:
        errors.append(
            "Consolidated failed-check count does not match the source."
        )

    for metric, expected in {
        **{
            "sales_transactions_rows": sales_rows,
            "sales_parquet_parts": parquet_parts,
        },
        **duplicate_metrics,
        **missing_metrics,
    }.items():
        if findings.get(metric) != expected:
            errors.append(
                f"Consolidated metric does not match source: {metric}"
            )

    return errors


# ============================================================
# CSV SUMMARY
# ============================================================

def build_csv_rows(
    loaded: dict[str, Any],
    key_findings: dict[str, Any],
) -> list[dict[str, Any]]:
    """Convert loaded reports and key findings into flat CSV rows."""

    rows: list[dict[str, Any]] = []

    for report_name, report_data in loaded.items():

        if report_name == "validation_summary":
            for key, value in report_data.items():

                if key == "raw_summary":
                    value = str(value).replace("\n", " | ")

                rows.append(
                    {
                        "report": report_name,
                        "section": "summary",
                        "metric": key,
                        "value": value,
                    }
                )

        else:
            for item in flatten_scalars(report_data):
                rows.append(
                    {
                        "report": report_name,
                        **item,
                    }
                )

    # Add extracted key findings.
    for metric, value in key_findings.items():
        rows.append(
            {
                "report": "consolidated_key_findings",
                "section": "key_findings",
                "metric": metric,
                "value": value,
            }
        )

    return rows


# ============================================================
# MAIN
# ============================================================

def main() -> int:
    """Consolidate existing F01 reports without rerunning analyses."""

    logger.info("=" * 65)
    logger.info("RetailPulse — Consolidated F01 Data-Quality Reports")
    logger.info("=" * 65)

    logger.info("Repository root: %s", ROOT)
    logger.info("Reports directory: %s", REPORTS_DIR)

    REPORTS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    # --------------------------------------------------------
    # 1. CHECK INPUT REPORTS
    # --------------------------------------------------------

    missing = [
        str(path.relative_to(ROOT))
        for path in INPUTS.values()
        if not path.is_file()
    ]

    if missing:
        logger.error(
            "Cannot consolidate: %s expected report(s) are missing.",
            len(missing),
        )

        for item in missing:
            logger.error("Missing report: %s", item)

        logger.error(
            "Generate the missing reports before running consolidation."
        )

        return 1

    # --------------------------------------------------------
    # 2. LOAD EXISTING REPORTS
    # --------------------------------------------------------

    loaded: dict[str, Any] = {}

    try:
        for name, path in INPUTS.items():
            logger.info("Loading report: %s", path.name)

            loaded[name] = load_report(
                name,
                path,
            )

    except (OSError, ValueError, json.JSONDecodeError):
        logger.exception(
            "Failed to load existing reports."
        )
        return 1

    # --------------------------------------------------------
    # 3. BUILD CONSOLIDATED REPORT
    # --------------------------------------------------------

    validation = loaded["validation_summary"]

    key_findings = build_key_findings(loaded)

    consolidated = {
        "report_name": (
            "RetailPulse Consolidated F01 Data Quality Report"
        ),
        "generated_at_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "repository_root": str(ROOT),
        "source_reports": {
            name: str(path.relative_to(ROOT))
            for name, path in INPUTS.items()
        },
        "status": {
            "all_expected_reports_present": True,
            "validation_checks_passed": validation.get(
                "passed_checks"
            ),
            "validation_checks_failed": validation.get(
                "failed_checks"
            ),
            "validation_warnings": validation.get(
                "warnings"
            ),
            "source_validation_status": validation.get(
                "overall_status"
            ),
            "report_consistency_check": "PENDING",
            "report_consistency_errors": [],
            "note": (
                "This report consolidates existing outputs. It does "
                "not rerun checks or independently certify the source data."
            ),
        },
        "key_findings": key_findings,
        "reports": loaded,
    }

    # --------------------------------------------------------
    # 4. CHECK REPORT CONSISTENCY
    # --------------------------------------------------------

    consistency_errors = validate_consolidated_metrics(
        loaded,
        consolidated,
    )

    consolidated["status"]["report_consistency_errors"] = (
        consistency_errors
    )

    if consistency_errors:
        consolidated["status"]["report_consistency_check"] = "FAIL"

        for error in consistency_errors:
            logger.error("Consistency check: %s", error)

    else:
        consolidated["status"]["report_consistency_check"] = "PASS"

        logger.info(
            "Consolidated report consistency checks passed."
        )

    # --------------------------------------------------------
    # 5. WRITE JSON REPORT
    # --------------------------------------------------------

    try:
        OUTPUT_JSON.write_text(
            json.dumps(
                consolidated,
                indent=2,
                ensure_ascii=False,
                default=str,
            )
            + "\n",
            encoding="utf-8",
        )

    except OSError:
        logger.exception(
            "Could not write JSON report: %s",
            OUTPUT_JSON,
        )
        return 1

    # --------------------------------------------------------
    # 6. WRITE CSV SUMMARY
    # --------------------------------------------------------

    csv_rows = build_csv_rows(
        loaded,
        key_findings,
    )

    # Include consistency results in the CSV.
    csv_rows.append(
        {
            "report": "consolidation",
            "section": "status",
            "metric": "report_consistency_check",
            "value": consolidated["status"]["report_consistency_check"],
        }
    )

    csv_rows.append(
        {
            "report": "consolidation",
            "section": "status",
            "metric": "report_consistency_errors",
            "value": " | ".join(consistency_errors),
        }
    )

    try:
        with OUTPUT_CSV.open(
            "w",
            newline="",
            encoding="utf-8-sig",
        ) as handle:

            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "report",
                    "section",
                    "metric",
                    "value",
                ],
            )

            writer.writeheader()
            writer.writerows(csv_rows)

    except OSError:
        logger.exception(
            "Could not write CSV summary: %s",
            OUTPUT_CSV,
        )
        return 1

    # --------------------------------------------------------
    # 7. FINAL SUMMARY
    # --------------------------------------------------------

    logger.info("=" * 65)
    logger.info("REPORT CONSOLIDATION COMPLETED")
    logger.info("=" * 65)

    logger.info(
        "Source reports consolidated: %s",
        len(loaded),
    )

    logger.info(
        "Validation checks passed: %s",
        validation.get("passed_checks"),
    )

    logger.info(
        "Validation checks failed: %s",
        validation.get("failed_checks"),
    )

    logger.info(
        "Sales transactions: %s",
        key_findings.get("sales_transactions_rows"),
    )

    logger.info(
        "Sales Parquet parts: %s",
        key_findings.get("sales_parquet_parts"),
    )

    logger.info(
        "Report consistency: %s",
        consolidated["status"]["report_consistency_check"],
    )

    logger.info(
        "JSON report: %s",
        OUTPUT_JSON.relative_to(ROOT),
    )

    logger.info(
        "CSV summary: %s",
        OUTPUT_CSV.relative_to(ROOT),
    )

    logger.info(
        "CSV metric rows: %s",
        len(csv_rows),
    )

    logger.info(
        "Source datasets were not modified."
    )

    logger.info(
        "No validation, duplicate, or missing-value analyses were rerun."
    )

    # Consolidation completed, but return a nonzero code if the
    # generated report is internally inconsistent.
    return 1 if consistency_errors else 0


if __name__ == "__main__":
    sys.exit(main())
    