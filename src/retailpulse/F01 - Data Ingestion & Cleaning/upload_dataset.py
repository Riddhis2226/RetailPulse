"""
RetailPulse — Upload Dataset to Hugging Face
=============================================

Location:
    src/retailpulse/f01_data_pipeline/upload_dataset_to_huggingface.py

Run from the repository root:
    $env:PYTHONPATH = "$PWD\\src"
    .venv\\Scripts\\python.exe -m retailpulse.f01_data_pipeline.upload_dataset_to_huggingface

Source directory:
    The path configured by RETAILPULSE_UPLOAD_SOURCE_DIR (default: data/raw)

Target repository:
    https://huggingface.co/datasets/RS2226/RetailPulse

Purpose:
    - Validate the local dataset directory.
    - List files before uploading.
    - Authenticate with Hugging Face.
    - Upload the directory to the dataset repository.

Important:
    - The local source files are not modified by this script.
    - The upload changes the remote repository.\n    - This is a manual maintenance utility, not part of deployment startup.\n    - Set RETAILPULSE_UPLOAD_SOURCE_DIR to the local source folder before use.
    - Review the target repository before uploading.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from huggingface_hub import HfApi, login


# ============================================================
# CONFIGURATION
# ============================================================

DATASET_PATH = Path(
    r"C:\Users\acer\Downloads\Zidio Development\retail_clean_dataset"
)

REPO_ID = "RS2226/RetailPulse"
REPO_TYPE = "dataset"

COMMIT_MESSAGE = "Upload RetailPulse retail datasets"


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)

logger = logging.getLogger(
    "retailpulse.f01.huggingface_upload"
)


# ============================================================
# VALIDATION
# ============================================================

def validate_dataset_directory() -> list[Path]:
    """Validate the source directory and return its files."""

    if not DATASET_PATH.is_dir():
        raise FileNotFoundError(
            f"Dataset directory not found: {DATASET_PATH}"
        )

    # Exclude symbolic links to avoid unintentionally uploading
    # files or directories outside the selected source folder.
    files = sorted(
        (
            path
            for path in DATASET_PATH.rglob("*")
            if path.is_file() and not path.is_symlink()
        ),
        key=lambda path: str(path.relative_to(DATASET_PATH)).lower(),
    )

    if not files:
        raise RuntimeError(
            f"No regular files found in {DATASET_PATH}"
        )

    return files


def display_upload_manifest(files: list[Path]) -> None:
    """Display the local files that will be included in the upload."""

    print("\n" + "=" * 70)
    print("RETAILPULSE — HUGGING FACE UPLOAD")
    print("=" * 70)

    print(f"\nSource directory:\n{DATASET_PATH}")
    print(f"\nTarget repository:\n{REPO_ID}")
    print(f"Repository type: {REPO_TYPE}")
    print(f"\nFiles found: {len(files):,}")

    print("\nUpload manifest:")

    for file_path in files:
        relative_path = file_path.relative_to(DATASET_PATH)
        file_size = file_path.stat().st_size

        print(
            f"  - {relative_path} "
            f"({file_size:,} bytes)"
        )

    total_bytes = sum(
        file_path.stat().st_size
        for file_path in files
    )

    print(f"\nTotal file size: {total_bytes:,} bytes")
    print("=" * 70)


# ============================================================
# AUTHENTICATION
# ============================================================

def authenticate() -> None:
    """Authenticate using the Hugging Face login flow."""

    logger.info("Starting Hugging Face authentication.")

    # The login flow prompts for a token if one is not already
    # available through the supported Hugging Face login mechanism.
    login()

    logger.info("Hugging Face login flow completed.")


# ============================================================
# UPLOAD
# ============================================================

def upload_dataset() -> None:
    """Upload the local dataset directory to Hugging Face."""

    logger.info(
        "Uploading dataset directory to %s",
        REPO_ID,
    )

    api = HfApi()

    result = api.upload_folder(
        folder_path=str(DATASET_PATH),
        repo_id=REPO_ID,
        repo_type=REPO_TYPE,
        commit_message=COMMIT_MESSAGE,
    )

    print("\nUpload completed.")
    print(f"Repository: https://huggingface.co/datasets/{REPO_ID}")

    if result is not None:
        print(f"Commit URL: {result}")

    logger.info("Hugging Face upload completed successfully.")


# ============================================================
# MAIN
# ============================================================

def main() -> int:
    """Validate, authenticate, and upload the dataset."""

    try:
        files = validate_dataset_directory()

        display_upload_manifest(files)

        # Require explicit confirmation before changing the remote repo.
        confirmation = input(
            "\nProceed with uploading these files? Type YES to continue: "
        ).strip()

        if confirmation != "YES":
            logger.info("Upload cancelled by user.")
            return 0

        authenticate()
        upload_dataset()

        return 0

    except KeyboardInterrupt:
        logger.warning("Operation interrupted by user.")
        return 130

    except Exception:
        logger.exception("Dataset upload failed.")
        return 1


if __name__ == "__main__":
    sys.exit(main()) 