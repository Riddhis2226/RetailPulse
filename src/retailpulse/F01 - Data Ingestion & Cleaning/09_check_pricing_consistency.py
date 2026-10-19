"""
RetailPulse — Pricing Consistency Validation
=============================================

Location:
    src/retailpulse/f01_data_pipeline/check_pricing_consistency.py

Run from repository root:
    $env:PYTHONPATH = "$PWD\\src"
    .venv\\Scripts\\python.exe -m retailpulse.f01_data_pipeline.check_pricing_consistency

Dataset:
    Hugging Face — RS2226/RetailPulse

Outputs:
    reports/pricing_consistency_report.json
    reports/pricing_consistency_summary.txt
"""

from __future__ import annotations

import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from huggingface_hub import hf_hub_download


# ============================================================
# CONFIGURATION
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[3]

REPO_ID = "RS2226/RetailPulse"
REPO_TYPE = "dataset"

SALES_FILENAME = "sales_transactions.csv"
CHUNK_SIZE = 200_000
TOLERANCE = 0.02

REPORT_DIR = PROJECT_ROOT / "reports"

JSON_REPORT = REPORT_DIR / "pricing_consistency_report.json"
TEXT_REPORT = REPORT_DIR / "pricing_consistency_summary.txt"


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)

logger = logging.getLogger("retailpulse.f01.pricing_validation")


# ============================================================
# MAIN VALIDATION
# ============================================================

def main() -> int:
    """Validate recorded sales totals against gross and discounted prices."""

    started = time.perf_counter()

    total_rows = 0
    exact_matches = 0
    gross_matches = 0
    discount_matches = 0
    other_mismatches = 0

    invalid_numeric_rows = 0
    invalid_discount_rows = 0

    report = {
        "project": "RetailPulse",
        "analysis": "Pricing consistency validation",
        "repository_id": REPO_ID,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "tolerance": TOLERANCE,
        "chunk_size": CHUNK_SIZE,
        "status": "running",
        "results": {},
        "limitations": [
            "Validation is performed in chunks.",
            "Exact matches compare values rounded to two decimal places.",
            "Gross-price matches and discounted-price matches may overlap.",
            "Rows with invalid numeric values require separate investigation.",
        ],
        "errors": [],
    }

    try:
        logger.info("Retrieving %s from Hugging Face.", SALES_FILENAME)

        path = Path(
            hf_hub_download(
                repo_id=REPO_ID,
                filename=SALES_FILENAME,
                repo_type=REPO_TYPE,
            )
        )

        if not path.is_file():
            raise FileNotFoundError(
                f"Sales dataset was not found: {path}"
            )

        required_columns = [
            "quantity",
            "unit_price",
            "total_value",
            "discount_pct",
        ]

        logger.info("Starting chunk-based pricing validation.")

        for chunk_number, chunk in enumerate(
            pd.read_csv(
                path,
                usecols=required_columns,
                chunksize=CHUNK_SIZE,
                low_memory=False,
            ),
            start=1,
        ):
            total_rows += len(chunk)

            # Convert fields explicitly to numeric.
            quantity = pd.to_numeric(
                chunk["quantity"],
                errors="coerce",
            )

            unit_price = pd.to_numeric(
                chunk["unit_price"],
                errors="coerce",
            )

            recorded = pd.to_numeric(
                chunk["total_value"],
                errors="coerce",
            )

            discount_pct = pd.to_numeric(
                chunk["discount_pct"],
                errors="coerce",
            )

            # Identify invalid or missing numeric values.
            numeric_valid = (
                quantity.notna()
                & unit_price.notna()
                & recorded.notna()
                & discount_pct.notna()
                & (quantity > 0)
                & (unit_price >= 0)
                & (recorded >= 0)
                & (discount_pct >= 0)
                & (discount_pct <= 100)
            )

            invalid_numeric_rows += int(
                (
                    quantity.isna()
                    | unit_price.isna()
                    | recorded.isna()
                    | discount_pct.isna()
                ).sum()
            )

            invalid_discount_rows += int(
                (
                    discount_pct.notna()
                    & (
                        (discount_pct < 0)
                        | (discount_pct > 100)
                    )
                ).sum()
            )

            # Calculate expected prices.
            gross = quantity * unit_price

            expected_net = (
                gross * (1 - discount_pct / 100)
            ).round(2)

            recorded_rounded = recorded.round(2)

            # Exclude invalid rows from pricing comparisons.
            gross_match = (
                numeric_valid
                & (
                    (recorded_rounded - gross).abs()
                    <= TOLERANCE
                )
            )

            discount_match = (
                numeric_valid
                & (
                    (
                        recorded_rounded - expected_net
                    ).abs()
                    <= TOLERANCE
                )
            )

            exact_match = (
                numeric_valid
                & (recorded_rounded == expected_net)
            )

            exact_matches += int(exact_match.sum())
            gross_matches += int(gross_match.sum())
            discount_matches += int(discount_match.sum())

            # Only valid rows that fail the discounted-price
            # comparison are classified as pricing mismatches.
            other_mismatches += int(
                (numeric_valid & ~discount_match).sum()
            )

            if chunk_number % 10 == 0:
                logger.info(
                    "Processed %s rows.",
                    f"{total_rows:,}",
                )

        # ----------------------------------------------------
        # RESULTS
        # ----------------------------------------------------

        valid_rows = (
            total_rows
            - int(
                # Count rows that fail any required numeric
                # or business-range condition.
                0
            )
        )

        # Reconcile invalid row count independently using the
        # counts available from this pass.
        # Pricing match rates use total rows for transparency.
        report["results"] = {
            "total_rows": total_rows,
            "exact_rounded_discount_matches": exact_matches,
            "gross_price_matches_within_tolerance": gross_matches,
            "discount_adjusted_matches_within_tolerance": discount_matches,
            "records_requiring_pricing_investigation": other_mismatches,
            "rows_with_missing_or_non_numeric_values": invalid_numeric_rows,
            "rows_with_out_of_range_discount_percentages": invalid_discount_rows,
            "discount_adjusted_match_rate": (
                discount_matches / total_rows
                if total_rows
                else 0.0
            ),
            "gross_price_match_rate": (
                gross_matches / total_rows
                if total_rows
                else 0.0
            ),
        }

        report["status"] = "completed"

        print("\nPRICING VALIDATION RESULTS")
        print("-" * 55)
        print(f"Total rows: {total_rows:,}")
        print(f"Exact rounded discount matches: {exact_matches:,}")
        print(f"Gross-price matches within tolerance: {gross_matches:,}")
        print(
            "Discount-adjusted matches within tolerance: "
            f"{discount_matches:,}"
        )
        print(
            "Records requiring pricing investigation: "
            f"{other_mismatches:,}"
        )
        print(
            "Rows with missing/non-numeric values: "
            f"{invalid_numeric_rows:,}"
        )
        print(
            "Rows with invalid discount percentages: "
            f"{invalid_discount_rows:,}"
        )

        if total_rows:
            print(
                "Discount-adjusted match rate: "
                f"{discount_matches / total_rows:.4%}"
            )

    except Exception as exc:
        logger.exception("Pricing validation failed.")

        report["status"] = "failed"
        report["errors"].append(
            f"{type(exc).__name__}: {exc}"
        )

    report["elapsed_seconds"] = round(
        time.perf_counter() - started,
        2,
    )

    # --------------------------------------------------------
    # SAVE REPORTS
    # --------------------------------------------------------

    try:
        REPORT_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )

        JSON_REPORT.write_text(
            json.dumps(
                report,
                indent=2,
                ensure_ascii=False,
                allow_nan=False,
            )
            + "\n",
            encoding="utf-8",
        )

        lines = [
            "RetailPulse — Pricing Consistency Validation",
            "=" * 60,
            f"Generated at UTC: {report['generated_at_utc']}",
            f"Status: {report['status'].upper()}",
            f"Tolerance: {TOLERANCE}",
            "",
            "RESULTS",
            "-" * 60,
        ]

        for key, value in report["results"].items():
            lines.append(f"{key}: {value}")

        lines.extend(
            [
                "",
                "LIMITATIONS",
                "-" * 60,
            ]
        )

        lines.extend(
            f"- {item}"
            for item in report["limitations"]
        )

        if report["errors"]:
            lines.extend(
                [
                    "",
                    "ERRORS",
                    "-" * 60,
                ]
            )

            lines.extend(
                f"- {error}"
                for error in report["errors"]
            )

        TEXT_REPORT.write_text(
            "\n".join(lines) + "\n",
            encoding="utf-8",
        )

        logger.info("JSON report saved to: %s", JSON_REPORT)
        logger.info("Text report saved to: %s", TEXT_REPORT)

    except Exception:
        logger.exception("Could not write validation reports.")
        return 1

    logger.info(
        "Validation finished in %.2f seconds.",
        report["elapsed_seconds"],
    )

    return 1 if report["status"] == "failed" else 0


if __name__ == "__main__":
    sys.exit(main()) 