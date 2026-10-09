#!/usr/bin/env python3
"""Compatibility entry point; implementation lives in src.pipeline."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from src.pipeline import main, get_latest_report, md_to_html, resolve_settings

if __name__ == "__main__":
    sys.exit(main())
