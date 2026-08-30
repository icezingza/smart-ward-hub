from __future__ import annotations

from pathlib import Path

from system_identity import (
    DEFAULT_DATABASE_FILENAME,
    PRODUCT_NAME,
    SYSTEM_IDENTITY,
    SYSTEM_NAME,
    SYSTEM_VERSION,
)


ROOT = Path(__file__).resolve().parent
IDENTITY_SURFACES = (
    Path("README.md"),
    Path("docs/SYSTEM_IDENTITY.md"),
    Path("docs/REBRAND_HANDOFF.md"),
    Path("architecture.md"),
    Path("alembic.ini"),
)


def test_canonical_identity_and_database_defaults() -> None:
    assert SYSTEM_NAME == "Smart Ward Hub"
    assert PRODUCT_NAME == "IPD Smart Sentinel"
    assert SYSTEM_VERSION == "2.0.0"
    assert DEFAULT_DATABASE_FILENAME == "ward_hub.db"
    assert SYSTEM_IDENTITY == "Smart Ward Hub / IPD Smart Sentinel v2.0.0"
    text = "\n".join((ROOT / path).read_text(encoding="utf-8") for path in IDENTITY_SURFACES)
    assert "Smart Ward Hub" in text
    assert "IPD Smart Sentinel" in text
    assert "ward_hub.db" in text


def test_unrelated_brand_names_are_absent_from_technical_surfaces() -> None:
    files = [path for path in ROOT.rglob("*") if path.is_file() and ".git" not in path.parts]
    forbidden = ("NamoNexus Enterprise", "Dhammic Moat", "v3.5.1")
    for path in files:
        relative = path.relative_to(ROOT)
        if relative == Path("test_system_identity.py") or path.suffix.lower() not in {".md", ".py", ".json", ".html", ".toml", ".ini"}:
            continue
        text = path.read_text(encoding="utf-8")
        assert not any(term.lower() in text.lower() for term in forbidden), relative


def run() -> None:
    test_canonical_identity_and_database_defaults()
    test_unrelated_brand_names_are_absent_from_technical_surfaces()
    print("[Identity] canonical product/version/database contract: PASSED")
    print("SYSTEM_IDENTITY_TESTS_PASSED")


if __name__ == "__main__":
    run()
