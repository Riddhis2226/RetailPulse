"""Manual maintenance utility for uploading a local dataset folder to Hugging Face.

This utility is deliberately separate from the deployment ingestion pipeline.
It mutates the remote dataset repository and must be run manually.
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from huggingface_hub import HfApi, login

DATASET_PATH = Path(os.getenv("RETAILPULSE_UPLOAD_SOURCE_DIR", "data/raw")).expanduser().resolve()
REPO_ID = os.getenv("RETAILPULSE_HF_REPO_ID", "RS2226/RetailPulse")
REPO_TYPE = "dataset"
COMMIT_MESSAGE = "Upload RetailPulse retail datasets"

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
LOGGER = logging.getLogger("retailpulse.f01.huggingface_upload")


def validate_dataset_directory() -> list[Path]:
    """Return regular files from the configured source folder."""
    if not DATASET_PATH.is_dir():
        raise FileNotFoundError(
            f"Dataset directory not found: {DATASET_PATH}. "
            "Set RETAILPULSE_UPLOAD_SOURCE_DIR to the correct local folder."
        )
    files = sorted(
        (p for p in DATASET_PATH.rglob("*") if p.is_file() and not p.is_symlink()),
        key=lambda p: str(p.relative_to(DATASET_PATH)).lower(),
    )
    if not files:
        raise RuntimeError(f"No regular files found in {DATASET_PATH}")
    return files


def main() -> int:
    try:
        files = validate_dataset_directory()
        print(f"Source directory: {DATASET_PATH}")
        print(f"Target repository: https://huggingface.co/datasets/{REPO_ID}")
        print(f"Files: {len(files)}")
        for path in files:
            print(f" - {path.relative_to(DATASET_PATH)} ({path.stat().st_size:,} bytes)")
        total_bytes = sum(path.stat().st_size for path in files)
        print(f"Total: {total_bytes:,} bytes")

        confirmation = input(
            "\nThis action changes the remote Hugging Face dataset. "
            "Type UPLOAD to continue: "
        ).strip()
        if confirmation != "UPLOAD":
            LOGGER.info("Upload cancelled.")
            return 0

        # Use the standard Hugging Face login/token cache; never embed credentials.
        login()
        result = HfApi().upload_folder(
            folder_path=str(DATASET_PATH),
            repo_id=REPO_ID,
            repo_type=REPO_TYPE,
            commit_message=COMMIT_MESSAGE,
        )
        print("Upload completed.")
        if result:
            print(f"Commit URL: {result}")
        return 0
    except KeyboardInterrupt:
        LOGGER.warning("Interrupted by user.")
        return 130
    except Exception:
        LOGGER.exception("Dataset upload failed.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
