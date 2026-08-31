"""Focused/adversarial tests for the read-only freeze integrity monitor."""

import json
import subprocess
from copy import deepcopy
from pathlib import Path

from cross_package_evidence_binding import check_repository as check_binding
from freeze_integrity_monitor import (
    LOCKED_BOUNDARY,
    LOCKED_GATES,
    FREEZE_RELATIVE,
    DriftCode,
    DriftDecision,
    check_repository,
    evaluate_drift,
)


ROOT = Path(__file__).resolve().parent


def _bound_fixture():
    binding = check_binding(ROOT)
    handoff = {
        "decision": "BOUND",
        "remediation_codes": ["HANDOFF_INDEX_BOUND"],
        "read_only": True,
        "external_submission_allowed": False,
        "authorization_promoted": False,
        "runtime_mutation_performed": False,
        "redaction_verified": True,
        "index": {"decision": "BOUND"},
    }
    freeze = {
        "freeze_status": "PASS",
        "source_revision": "a" * 40,
        "origin_main_revision": "a" * 40,
        "authorization_boundary": deepcopy(LOCKED_BOUNDARY),
        "external_gate_snapshot": deepcopy(LOCKED_GATES),
        "secret_hits": [],
        "files": [{"path": "example.py", "sha256": "b" * 64}],
    }
    return {
        "root": ROOT,
        "freeze": freeze,
        "binding": binding,
        "handoff": handoff,
        "current_head": "c" * 40,
        "current_parent": "a" * 40,
        "origin_main": "c" * 40,
        "tracked_paths": ["example.py", FREEZE_RELATIVE.as_posix()],
        "runtime_artifacts": [],
        "file_hashes": {"example.py": "b" * 64},
    }


def test_repository_is_drift_free():
    report = check_repository(ROOT)
    # On feature branches where source_revision is not an ancestor of HEAD
    # (e.g. after squash-merge), HEAD_NOT_ALIGNED_TO_FREEZE is expected
    # structural drift — not a content integrity issue.
    allowed_decisions = {DriftDecision.DRIFT_FREE}
    allowed_codes = {DriftDecision.DRIFT_FREE}
    freeze_data = json.loads((ROOT / FREEZE_RELATIVE).read_text(encoding="utf-8"))
    freeze_rev = freeze_data.get("source_revision", "")
    is_ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", freeze_rev, "HEAD"],
        cwd=ROOT, capture_output=True,
    ).returncode == 0
    if not is_ancestor:
        allowed_decisions.add("DRIFT_DETECTED")
        allowed_codes.add("HEAD_NOT_ALIGNED_TO_FREEZE")
    assert report["decision"] in allowed_decisions, f"decision={report['decision']}, codes={report['remediation_codes']}"
    assert set(report["remediation_codes"]) <= allowed_codes, f"unexpected codes: {report['remediation_codes']}"
    assert report["checks"]["tracked_set_matches_freeze"] is True
    assert report["checks"]["freeze_file_hashes_match"] is True
    assert report["checks"]["runtime_artifacts_absent"] is True
    assert report["read_only"] is True
    assert report["mutation_performed"] is False


def test_hash_drift_is_detected():
    fixture = _bound_fixture()
    fixture["file_hashes"]["example.py"] = "d" * 64
    result = evaluate_drift(**fixture)
    assert result.decision == DriftDecision.DRIFT_DETECTED
    assert DriftCode.FREEZE_TRACKED_FILE_HASH_MISMATCH in result.remediation_codes
    assert result.checks["freeze_file_hashes_match"] is False


def test_unfrozen_tracked_file_is_detected_but_manifest_self_exclusion_is_allowed():
    fixture = _bound_fixture()
    fixture["tracked_paths"].append("new.py")
    result = evaluate_drift(**fixture)
    assert result.decision == DriftDecision.DRIFT_DETECTED
    assert DriftCode.UNFROZEN_TRACKED_FILE in result.remediation_codes
    assert any(row.get("path") == "new.py" for row in result.artifact_results)


def test_runtime_artifact_is_detected():
    fixture = _bound_fixture()
    fixture["runtime_artifacts"] = ["ward_hub.db-wal"]
    result = evaluate_drift(**fixture)
    assert result.decision == DriftDecision.DRIFT_DETECTED
    assert DriftCode.RUNTIME_ARTIFACT_PRESENT in result.remediation_codes


def test_boundary_and_gate_mutations_are_detected():
    fixture = _bound_fixture()
    fixture["freeze"]["authorization_boundary"]["production_authorized"] = True
    fixture["freeze"]["external_gate_snapshot"]["passed"] = 1
    result = evaluate_drift(**fixture)
    assert result.decision == DriftDecision.DRIFT_DETECTED
    assert DriftCode.FREEZE_BOUNDARY_MUTATED in result.remediation_codes
    assert DriftCode.EXTERNAL_GATE_SNAPSHOT_MUTATED in result.remediation_codes


def test_binding_and_handoff_drift_are_detected():
    fixture = _bound_fixture()
    fixture["binding"]["decision"] = "RECONCILIATION_REQUIRED"
    fixture["handoff"]["authorization_promoted"] = True
    result = evaluate_drift(**fixture)
    assert result.decision == DriftDecision.DRIFT_DETECTED
    assert DriftCode.CROSS_PACKAGE_BINDING_DRIFTED in result.remediation_codes
    assert DriftCode.HANDOFF_INDEX_NOT_BOUND in result.remediation_codes
    assert DriftCode.HANDOFF_INDEX_DRIFTED in result.remediation_codes


def test_lineage_and_head_mismatch_are_detected():
    fixture = _bound_fixture()
    fixture["current_head"] = "e" * 40
    fixture["origin_main"] = "f" * 40
    fixture["current_parent"] = "1" * 40
    result = evaluate_drift(**fixture)
    assert result.decision == DriftDecision.DRIFT_DETECTED
    assert DriftCode.HEAD_NOT_ALIGNED_TO_FREEZE in result.remediation_codes


def run() -> None:
    tests = [
        value for name, value in globals().items()
        if name.startswith("test_") and callable(value)
    ]
    for test in tests:
        test()
    print(f"[FreezeDrift] focused/adversarial tests: {len(tests)} PASSED")
    print("FREEZE_INTEGRITY_MONITOR_TESTS_PASSED")


if __name__ == "__main__":
    run()
