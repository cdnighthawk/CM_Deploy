"""Shared default paths for CSV import scripts.

Set ``DATABASE_FILES_ROOT`` in the environment (or ``backend/.env``) to the
folder that holds your exports (wage rates, Bobrick pricing, CDTFA, Corecon
CSVs, etc.). Falls back to the historical OneDrive layout used in this repo.
"""
from __future__ import annotations

import os
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

_FALLBACK_DIR = Path(r"E:\OneDrive - godocon.com\New Company Software\Database files")


def database_files_dir() -> Path:
    raw = (os.environ.get("DATABASE_FILES_ROOT") or "").strip()
    return Path(raw) if raw else _FALLBACK_DIR
