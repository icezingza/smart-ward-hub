#!/usr/bin/env python3
"""Automated Packaging Tool for IPD Smart Sentinel Portable Hub.

Bundles the application into IPD_Smart_Sentinel_Hub_Portable.zip with zero-install
batch scripts, database migrations, and operational contracts.
"""

from __future__ import annotations

import os
from pathlib import Path
import zipfile

PROJECT_ROOT = Path(__file__).resolve().parent
OUTPUT_ZIP = PROJECT_ROOT / "IPD_Smart_Sentinel_Hub_Portable.zip"

EXCLUDE_DIRS = {
    ".git",
    ".github",
    ".ruff_cache",
    "__pycache__",
    ".venv",
    "venv",
    ".pytest_cache",
}

EXCLUDE_EXTENSIONS = {
    ".pyc",
    ".pyo",
    ".pyd",
    ".db",
    ".db-wal",
    ".db-shm",
    ".zip",
}


def package_portable() -> Path:
    print(f"[*] Packaging IPD Smart Sentinel Hub into: {OUTPUT_ZIP.name}")
    
    file_count = 0
    total_bytes = 0
    
    with zipfile.ZipFile(OUTPUT_ZIP, "w", compression=zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(PROJECT_ROOT):
            # Prune excluded directories
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and not d.startswith(".")]
            
            for file in files:
                file_path = Path(root) / file
                
                # Check exclusion rules
                if file_path.suffix in EXCLUDE_EXTENSIONS:
                    continue
                if file_path == OUTPUT_ZIP:
                    continue
                
                rel_path = file_path.relative_to(PROJECT_ROOT)
                zipf.write(file_path, arcname=str(rel_path))
                file_count += 1
                total_bytes += file_path.stat().st_size
                
    print(f"[OK] Successfully packaged {file_count} files ({total_bytes / (1024*1024):.2f} MB)")
    print(f"[OK] Portable Archive Ready: {OUTPUT_ZIP}")
    return OUTPUT_ZIP


if __name__ == "__main__":
    package_portable()
