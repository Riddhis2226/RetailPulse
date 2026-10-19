"""
RetailPulse — Central Project Configuration
===========================================

Defines project paths, environment-based configuration,
and shared defaults for all RetailPulse modules.

Environment variables:
    RETAILPULSE_HF_REPO_ID
    RETAILPULSE_CHUNK_SIZE
    RETAILPULSE_RANDOM_STATE

Directory structure:
    RetailPulse/
    ├── data/
    │   ├── raw/
    │   └── processed/
    ├── reports/
    ├── models/
    ├── artifacts/
    └── src/
        └── retailpulse/
            └── config.py
"""

from __future__ import annotations

import logging
import os

from pathlib import Path


# ============================================================
# LOGGING
# ============================================================

logger = logging.getLogger(__name__)


# ============================================================
# PROJECT ROOT
# ============================================================

# config.py:
# parents[0] = retailpulse
# parents[1] = src
# parents[2] = RetailPulse

PROJECT_ROOT = Path(__file__).resolve().parents[2]


# ============================================================
# PROJECT DIRECTORIES
# ============================================================

DATA_DIR = PROJECT_ROOT / "data"

RAW_DIR = DATA_DIR / "raw"

PROCESSED_DIR = DATA_DIR / "processed"

REPORTS_DIR = PROJECT_ROOT / "reports"

MODELS_DIR = PROJECT_ROOT / "models"

ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"


# ============================================================
# ENVIRONMENT VARIABLE HELPERS
# ============================================================

def _get_int_env(
    name: str,
    default: int,
    *,
    minimum: int | None = None,
) -> int:
    """
    Read and validate an integer environment variable.

    Raises:
        ValueError: If the value is not an integer or violates
                    the configured minimum.
    """

    raw_value = os.getenv(name)

    if raw_value is None or not raw_value.strip():
        return default

    try:
        value = int(raw_value.strip())

    except ValueError as exc:
        raise ValueError(
            f"Environment variable {name} must be an integer; "
            f"received {raw_value!r}."
        ) from exc

    if minimum is not None and value < minimum:
        raise ValueError(
            f"Environment variable {name} must be >= {minimum}; "
            f"received {value}."
        )

    return value


def _get_str_env(
    name: str,
    default: str,
) -> str:
    """
    Read a string environment variable.

    Empty or whitespace-only values use the supplied default.
    """

    value = os.getenv(name)

    if value is None or not value.strip():
        return default

    return value.strip()


# ============================================================
# DATASET CONFIGURATION
# ============================================================

HF_DATASET_REPO_ID = _get_str_env(
    "RETAILPULSE_HF_REPO_ID",
    "RS2226/RetailPulse",
)


# ============================================================
# PIPELINE DEFAULTS
# ============================================================

CHUNK_SIZE = _get_int_env(
    "RETAILPULSE_CHUNK_SIZE",
    100_000,
    minimum=1,
)

RANDOM_STATE = _get_int_env(
    "RETAILPULSE_RANDOM_STATE",
    42,
    minimum=0,
)


# ============================================================
# DIRECTORY MANAGEMENT
# ============================================================

PROJECT_DIRECTORIES = (
    DATA_DIR,
    RAW_DIR,
    PROCESSED_DIR,
    REPORTS_DIR,
    MODELS_DIR,
    ARTIFACTS_DIR,
)


def ensure_project_directories() -> None:
    """
    Create the standard RetailPulse directories if they do not exist.

    Existing directories and files are not deleted or modified.
    """

    for directory in PROJECT_DIRECTORIES:
        try:
            directory.mkdir(
                parents=True,
                exist_ok=True,
            )

        except OSError as exc:
            raise OSError(
                f"Could not initialize project directory: {directory}"
            ) from exc


# ============================================================
# INITIALIZATION
# ============================================================

# Preserve the existing behavior: initialize output directories
# automatically when this configuration module is imported.
ensure_project_directories()


# ============================================================
# CONFIGURATION SUMMARY
# ============================================================

def get_config_summary() -> dict[str, object]:
    """
    Return a serializable summary of the active configuration.

    Useful for diagnostics and pipeline reports.
    """

    return {
        "project_root": str(PROJECT_ROOT),
        "data_dir": str(DATA_DIR),
        "raw_dir": str(RAW_DIR),
        "processed_dir": str(PROCESSED_DIR),
        "reports_dir": str(REPORTS_DIR),
        "models_dir": str(MODELS_DIR),
        "artifacts_dir": str(ARTIFACTS_DIR),
        "hf_dataset_repo_id": HF_DATASET_REPO_ID,
        "chunk_size": CHUNK_SIZE,
        "random_state": RANDOM_STATE,
    }