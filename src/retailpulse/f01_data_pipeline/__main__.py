"""Command-line entry point: python -m retailpulse.f01_data_pipeline."""
from __future__ import annotations

import argparse
import logging
import sys

from .pipeline import DEFAULT_REPO_ID, run_pipeline


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Download the seven RetailPulse source CSVs from Hugging Face and create cleaned Parquet outputs."
    )
    parser.add_argument("--repo-id", default=None, help=f"Hugging Face dataset repo ID (default: {DEFAULT_REPO_ID}).")
    parser.add_argument("--chunk-size", type=int, default=None, help="Sales CSV chunk size (default: RETAILPULSE_CHUNK_SIZE or 100000).")
    parser.add_argument("--output-dir", default=None, help="Output root (default: data/processed). Each run gets a new subfolder.")
    parser.add_argument("--report-dir", default=None, help="Report root (default: reports/f01).")
    parser.add_argument("--log-level", default="INFO", choices=("DEBUG", "INFO", "WARNING", "ERROR"))
    args = parser.parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level), format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    try:
        report = run_pipeline(repo_id=args.repo_id, chunk_size=args.chunk_size, output_root=args.output_dir, report_root=args.report_dir)
    except Exception:
        return 1
    print(f"F01 status: {report['status']}")
    print(f"Output: {report['output_directory']}")
    print(f"Report: {report['report_path']}")
    for name, details in report["source_files"].items():
        print(f"  {name}: {details['rows_written']:,} rows ({details['status']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
