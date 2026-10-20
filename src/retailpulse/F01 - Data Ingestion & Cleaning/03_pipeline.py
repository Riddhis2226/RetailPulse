"""Compatibility entry point for the canonical F01 package.

Prefer: python -m retailpulse.f01_data_pipeline
This legacy path is retained so existing documentation/bookmarks do not
silently invoke a second implementation with different input assumptions.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Allow direct execution from the historical folder with spaces in its name.
SRC_DIR = Path(__file__).resolve().parents[2]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from retailpulse.f01_data_pipeline.__main__ import main


if __name__ == "__main__":
    raise SystemExit(main())
