"""Portable F01 pipeline for downloading and preparing RetailPulse source data.

The pipeline downloads source CSVs from Hugging Face into its managed cache,
leaves those source files untouched, and writes each execution to a new output
folder. It never deletes an earlier successful output run.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from huggingface_hub import hf_hub_download

LOGGER = logging.getLogger("retailpulse.f01")
DEFAULT_REPO_ID = "RS2226/RetailPulse"
SOURCE_FILES = (
    "customer_master.csv",
    "inventory_snapshot.csv",
    "promotions.csv",
    "sales_transactions.csv",
    "sku_inventory_flags.csv",
    "sku_master.csv",
    "store_master.csv",
)
DATE_COLUMNS: dict[str, tuple[str, ...]] = {
    "customer_master.csv": ("registration_date",),
    "inventory_snapshot.csv": ("last_restock_date",),
    "promotions.csv": ("start_date", "end_date"),
    "sales_transactions.csv": ("date",),
    "sku_inventory_flags.csv": ("window_start", "window_end"),
    "sku_master.csv": (),
    "store_master.csv": ("opening_date",),
}


def project_root() -> Path:
    """Resolve repository root from this installed src-layout package."""
    return Path(__file__).resolve().parents[3]


def clean_dataframe(frame: pd.DataFrame, filename: str) -> tuple[pd.DataFrame, dict[str, int]]:
    """Apply conservative cleaning without dropping rows or imputing values."""
    cleaned = frame.copy()
    stats: dict[str, int] = {"trimmed_text_cells": 0, "invalid_dates": 0}
    text_columns = cleaned.select_dtypes(include=["object", "string"]).columns
    for column in text_columns:
        original = cleaned[column]
        trimmed = original.str.strip()
        stats["trimmed_text_cells"] += int((original.fillna("") != trimmed.fillna("")).sum())
        cleaned[column] = trimmed

    for column in DATE_COLUMNS.get(Path(filename).name, ()):
        if column not in cleaned.columns:
            continue
        original = cleaned[column]
        converted = pd.to_datetime(original, errors="coerce", utc=False)
        stats["invalid_dates"] += int((original.notna() & converted.isna()).sum())
        cleaned[column] = converted

    if len(cleaned) != len(frame) or list(cleaned.columns) != list(frame.columns):
        raise RuntimeError(f"Cleaning changed the row count or column order for {filename}")
    return cleaned, stats


def _download_source(filename: str, repo_id: str) -> Path:
    """Download or retrieve a source file using the Hugging Face managed cache."""
    try:
        path = hf_hub_download(
            repo_id=repo_id,
            repo_type="dataset",
            filename=filename,
            token=os.getenv("HF_TOKEN") or None,
        )
    except Exception as exc:
        raise RuntimeError(
            f"Could not retrieve {filename} from Hugging Face dataset {repo_id}. "
            "Check network access and, if the dataset is gated, set HF_TOKEN to "
            "a token for an account that has been granted access. Do not commit the token."
        ) from exc
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(f"Hugging Face returned a missing file path for {filename}: {source}")
    return source


def _write_parquet(frame: pd.DataFrame, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(destination, index=False, engine="pyarrow")


def run_pipeline(
    *,
    repo_id: str | None = None,
    chunk_size: int | None = None,
    output_root: str | Path | None = None,
    report_root: str | Path | None = None,
) -> dict[str, Any]:
    """Download and prepare all seven CSVs; return a JSON-serializable report."""
    repo_id = (repo_id or os.getenv("RETAILPULSE_HF_REPO_ID") or DEFAULT_REPO_ID).strip()
    chunk_size = chunk_size or int(os.getenv("RETAILPULSE_CHUNK_SIZE", "100000"))
    if not repo_id or "/" not in repo_id:
        raise ValueError("repo_id must be a Hugging Face dataset ID such as owner/name")
    if chunk_size < 1:
        raise ValueError("chunk_size must be greater than zero")

    root = project_root()
    output_base = Path(output_root or os.getenv("RETAILPULSE_OUTPUT_DIR") or root / "data" / "processed").expanduser().resolve()
    reports_base = Path(report_root or os.getenv("RETAILPULSE_REPORT_DIR") or root / "reports" / "f01").expanduser().resolve()
    run_id = datetime.now(timezone.utc).strftime("run_%Y%m%dT%H%M%S_%fZ")
    run_dir = output_base / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    report: dict[str, Any] = {
        "project": "RetailPulse", "functional_area": "F01", "status": "running",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "dataset_repo_id": repo_id, "chunk_size": chunk_size,
        "source_files": {}, "output_directory": str(run_dir), "errors": [],
    }
    LOGGER.info("F01 starting | dataset=%s | chunk_size=%s | output=%s", repo_id, chunk_size, run_dir)
    try:
        for filename in SOURCE_FILES:
            source_path = _download_source(filename, repo_id)
            dataset_report: dict[str, Any] = {
                "status": "running", "source_filename": filename,
                "source_bytes": source_path.stat().st_size,
                "rows_read": 0, "rows_written": 0, "chunks_written": 0,
                "missing_values": {}, "invalid_dates": 0, "trimmed_text_cells": 0,
            }
            if filename == "sales_transactions.csv":
                destination_dir = run_dir / "sales_transactions"
                destination_dir.mkdir(parents=True, exist_ok=True)
                missing_totals: dict[str, int] = {}
                for chunk_index, chunk in enumerate(pd.read_csv(source_path, chunksize=chunk_size, low_memory=False), start=1):
                    dataset_report["rows_read"] += int(len(chunk))
                    cleaned, stats = clean_dataframe(chunk, filename)
                    dataset_report["invalid_dates"] += stats["invalid_dates"]
                    dataset_report["trimmed_text_cells"] += stats["trimmed_text_cells"]
                    for col, count in cleaned.isna().sum().items():
                        if count:
                            missing_totals[str(col)] = missing_totals.get(str(col), 0) + int(count)
                    _write_parquet(cleaned, destination_dir / f"part-{chunk_index:05d}.parquet")
                    dataset_report["rows_written"] += int(len(cleaned))
                    dataset_report["chunks_written"] += 1
                    LOGGER.info("F01 sales chunk %s complete (%s rows written)", chunk_index, f"{dataset_report['rows_written']:,}")
                    del chunk, cleaned
                dataset_report["missing_values"] = missing_totals
                dataset_report["output"] = str(destination_dir)
            else:
                frame = pd.read_csv(source_path, low_memory=False)
                dataset_report["rows_read"] = int(len(frame))
                cleaned, stats = clean_dataframe(frame, filename)
                dataset_report["invalid_dates"] = stats["invalid_dates"]
                dataset_report["trimmed_text_cells"] = stats["trimmed_text_cells"]
                dataset_report["missing_values"] = {str(k): int(v) for k, v in cleaned.isna().sum().items() if v}
                destination = run_dir / filename.replace(".csv", ".parquet")
                _write_parquet(cleaned, destination)
                dataset_report["rows_written"] = int(len(cleaned))
                dataset_report["chunks_written"] = 1
                dataset_report["output"] = str(destination)
                del frame, cleaned
            dataset_report["status"] = "success"
            dataset_report["row_count_preserved"] = dataset_report["rows_read"] == dataset_report["rows_written"]
            report["source_files"][filename] = dataset_report

        report["status"] = "success"
        report["elapsed_seconds"] = round(time.perf_counter() - started, 2)
        reports_base.mkdir(parents=True, exist_ok=True)
        report_path = reports_base / f"{run_id}.json"
        report["report_path"] = str(report_path)
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
        LOGGER.info("F01 complete | report=%s | elapsed=%ss", report_path, report["elapsed_seconds"])
        return report
    except Exception as exc:
        report["status"] = "failed"
        report["errors"].append(f"{type(exc).__name__}: {exc}")
        report["elapsed_seconds"] = round(time.perf_counter() - started, 2)
        # Remove only the incomplete run created by this invocation. Earlier runs are untouched.
        shutil.rmtree(run_dir, ignore_errors=True)
        reports_base.mkdir(parents=True, exist_ok=True)
        failure_path = reports_base / f"{run_id}_failed.json"
        failure_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        LOGGER.exception("F01 failed; failure report saved to %s", failure_path)
        raise
