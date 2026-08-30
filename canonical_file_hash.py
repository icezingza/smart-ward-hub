from __future__ import annotations

import hashlib
from pathlib import Path


TEXT_SUFFIXES = {
    ".bat",
    ".cmd",
    ".csv",
    ".css",
    ".example",
    ".html",
    ".ini",
    ".js",
    ".json",
    ".mako",
    ".md",
    ".ps1",
    ".py",
    ".service",
    ".sh",
    ".sql",
    ".svg",
    ".toml",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}
TEXT_NAMES = {".gitattributes", ".gitignore"}


def canonical_bytes(path: Path) -> bytes:
    """Normalize text line endings so evidence hashes are platform-independent."""
    raw = path.read_bytes()
    if path.suffix.lower() in TEXT_SUFFIXES or path.name in TEXT_NAMES:
        return raw.replace(b"\r\n", b"\n")
    return raw


def canonical_sha256(path: Path) -> str:
    return hashlib.sha256(canonical_bytes(path)).hexdigest()
