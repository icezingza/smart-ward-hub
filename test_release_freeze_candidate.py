from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MANIFEST_PATH = ROOT / "evals/micro_rag/evidence/release-candidate-freeze-20260820.json"
LOCKED_AUTHORIZATION = {
    "external_authority": "NONE",
    "clinical_validation_authorized": False,
    "production_authorized": False,
    "runtime_authority": "NONE",
    "pilot_gate_status": "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION",
}
EXPECTED_VALID_CLAIMS = {
    "controlled production prototype",
    "P0-hardened software baseline",
    "functional verification passed",
    "pilot-ready foundation",
    "clinical validation pending",
}
EXPECTED_FORBIDDEN_CLAIMS = {
    "clinical-ready",
    "production-ready",
    "tamper-proof",
    "HIPAA/PDPA compliant 100%",
}
TEXT_SUFFIXES = {".bat", ".cmd", ".csv", ".css", ".example", ".html", ".ini", ".js", ".json", ".mako", ".md", ".ps1", ".py", ".service", ".sh", ".sql", ".svg", ".toml", ".txt", ".xml", ".yaml", ".yml"}
TEXT_NAMES = {".gitattributes", ".gitignore"}


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()


def is_ancestor(ancestor: str, descendant: str) -> bool:
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", ancestor, descendant],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


def sha256(path: Path) -> str:
    raw = path.read_bytes()
    if path.suffix.lower() in TEXT_SUFFIXES or path.name in TEXT_NAMES:
        raw = raw.replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()


def test_release_freeze_manifest_is_current():
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == "smart-ward-hub-release-freeze-v1"
    assert manifest["freeze_status"] == "PASS"
    assert manifest["checks"] == {
        "head_matches_origin_main": True,
        "runtime_artifact_scan_pass": True,
        "secret_marker_scan_pass": True,
        "tracked_file_hashes_generated": True,
        "working_tree_clean_before_manifest": True,
    }
    assert manifest["authorization_boundary"] == LOCKED_AUTHORIZATION
    assert set(manifest["claim_boundary"]["valid"]) == EXPECTED_VALID_CLAIMS
    assert set(manifest["claim_boundary"]["forbidden_from_local_freeze"]) == EXPECTED_FORBIDDEN_CLAIMS
    assert manifest["external_gate_snapshot"] == {"blocked": 7, "evidence_submitted": 0, "open": 3, "passed": 0}

    current_head = git("rev-parse", "HEAD")
    origin_head = git("rev-parse", "origin/main")
    source_revision = manifest["source_revision"]
    assert is_ancestor(source_revision, current_head)
    assert origin_head == current_head or is_ancestor(origin_head, current_head)
    assert is_ancestor(manifest["origin_main_revision"], source_revision)

    changed_since_source = set(git("diff", "--name-only", source_revision, current_head).splitlines())
    assert changed_since_source in (set(), {str(MANIFEST_PATH.relative_to(ROOT))})


def test_manifest_hashes_selected_current_files():
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    by_path = {entry["path"]: entry for entry in manifest["files"]}
    for relative in (
        "run_all_tests.py",
        "wave1_software_preparation.py",
        "test_wave1_software_preparation.py",
        "WAVE_1_SOFTWARE_PREPARATION_PACKAGE_20260820.md",
    ):
        assert relative in by_path
        assert by_path[relative]["sha256"] == sha256(ROOT / relative)
    assert str(MANIFEST_PATH.relative_to(ROOT)) not in by_path


if __name__ == "__main__":
    test_release_freeze_manifest_is_current()
    test_manifest_hashes_selected_current_files()
    print("RELEASE_FREEZE_CANDIDATE_TESTS_PASSED")
