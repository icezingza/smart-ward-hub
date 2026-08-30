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


def canonicalize_bytes(path: Path, raw: bytes) -> bytes:
    """Normalize supplied file bytes using the release-freeze text rules."""
    if path.suffix.lower() in TEXT_SUFFIXES or path.name in TEXT_NAMES:
        return raw.replace(b"\r\n", b"\n")
    return raw


def canonical_bytes(path: Path) -> bytes:
    """Read and normalize a file so evidence hashes are platform-independent."""
    return canonicalize_bytes(path, path.read_bytes())


def canonical_sha256(path: Path) -> str:
    return hashlib.sha256(canonical_bytes(path)).hexdigest()
