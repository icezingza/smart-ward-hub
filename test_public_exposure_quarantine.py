"""Focused and adversarial tests for public-exposure quarantine."""

from __future__ import annotations

from copy import deepcopy

from public_exposure_quarantine import (
    ExposureCode,
    ExposureDecision,
    evaluate_exposure,
)
from repository_visibility_governance import LOCKED_BOUNDARY, VisibilityDecision


BASE_FREEZE = {
    "freeze_status": "PASS",
    "source_revision": "a" * 40,
    "origin_main_revision": "a" * 40,
    "files": [{"path": "safe.txt", "sha256": ""}],
}
BASE_VISIBILITY = {
    "decision": VisibilityDecision.PRIVATE_REPOSITORY_CONFIRMED,
    "repository": "icezingza/smart-ward-hub",
    "observation_source": "GH_REPO_VIEW",
    "authorization_boundary": deepcopy(LOCKED_BOUNDARY),
    "external_submission_allowed": False,
    "authorization_promoted": False,
    "runtime_mutation_performed": False,
    "external_transmission_performed": False,
}


def _evaluate(raw: bytes = b"safe content", *, freeze=None, visibility=None):
    active_freeze = deepcopy(freeze or BASE_FREEZE)
    active_visibility = deepcopy(visibility or BASE_VISIBILITY)
    import hashlib

    if freeze is None:
        active_freeze["files"][0]["sha256"] = hashlib.sha256(raw).hexdigest()
    return evaluate_exposure(
        freeze=active_freeze,
        visibility=active_visibility,
        files={"safe.txt": raw},
    )


def test_safe_private_repository_is_clear():
    result = _evaluate()
    assert result.decision == ExposureDecision.PUBLIC_EXPOSURE_CLEAR
    assert result.remediation_codes == ()
    assert all(result.checks.values())


def test_public_visibility_quarantines_even_safe_bytes():
    visibility = deepcopy(BASE_VISIBILITY)
    visibility["decision"] = "REPOSITORY_VISIBILITY_BLOCKED"
    result = _evaluate(visibility=visibility)
    assert result.decision == ExposureDecision.PUBLIC_EXPOSURE_QUARANTINED
    assert ExposureCode.PUBLIC_REPOSITORY_EXPOSURE_QUARANTINED in result.remediation_codes


def test_secret_marker_quarantines():
    result = _evaluate(b"credential ghp_abcdefghijklmnopqrstuvwxyz123456")
    assert result.decision == ExposureDecision.PUBLIC_EXPOSURE_QUARANTINED
    assert ExposureCode.SECRET_MARKER_FOUND in result.remediation_codes
    assert result.findings[0]["kind"] == "SECRET_MARKER"


def test_identifier_pattern_quarantines():
    result = _evaluate(b"sample HN-2026-8901")
    assert result.decision == ExposureDecision.PUBLIC_EXPOSURE_QUARANTINED
    assert ExposureCode.IDENTIFIER_PATTERN_FOUND in result.remediation_codes


def test_hash_mismatch_quarantines():
    freeze = deepcopy(BASE_FREEZE)
    freeze["files"][0]["sha256"] = "f" * 64
    result = _evaluate(freeze=freeze)
    assert result.decision == ExposureDecision.PUBLIC_EXPOSURE_QUARANTINED
    assert ExposureCode.FREEZE_HASH_MISMATCH in result.remediation_codes


def test_missing_frozen_file_quarantines():
    freeze = deepcopy(BASE_FREEZE)
    freeze["files"][0]["path"] = "missing.txt"
    result = evaluate_exposure(
        freeze=freeze,
        visibility=BASE_VISIBILITY,
        files={"missing.txt": None},
    )
    assert result.decision == ExposureDecision.PUBLIC_EXPOSURE_QUARANTINED
    assert ExposureCode.FREEZE_FILE_UNREADABLE in result.remediation_codes


def test_missing_freeze_quarantines():
    result = evaluate_exposure(freeze=None, visibility=BASE_VISIBILITY, files={})
    assert result.decision == ExposureDecision.PUBLIC_EXPOSURE_QUARANTINED
    assert ExposureCode.FREEZE_MANIFEST_MISSING in result.remediation_codes


def test_boundary_mutation_quarantines():
    visibility = deepcopy(BASE_VISIBILITY)
    visibility["authorization_boundary"]["production_authorized"] = True
    result = _evaluate(visibility=visibility)
    assert result.decision == ExposureDecision.PUBLIC_EXPOSURE_QUARANTINED
    assert ExposureCode.AUTHORIZATION_BOUNDARY_MUTATED in result.remediation_codes


def test_execution_mutation_quarantines():
    visibility = deepcopy(BASE_VISIBILITY)
    visibility["external_submission_allowed"] = True
    result = _evaluate(visibility=visibility)
    assert result.decision == ExposureDecision.PUBLIC_EXPOSURE_QUARANTINED
    assert ExposureCode.EXECUTION_BOUNDARY_MUTATED in result.remediation_codes


def test_input_is_not_mutated():
    freeze = deepcopy(BASE_FREEZE)
    visibility = deepcopy(BASE_VISIBILITY)
    before_freeze = deepcopy(freeze)
    before_visibility = deepcopy(visibility)
    _evaluate(freeze=freeze, visibility=visibility)
    assert freeze == before_freeze
    assert visibility == before_visibility


def run() -> None:
    tests = [
        value for name, value in globals().items()
        if name.startswith("test_") and callable(value)
    ]
    for test in tests:
        test()
    print(f"[Exposure] focused/adversarial tests: {len(tests)} PASSED")
    print("PUBLIC_EXPOSURE_QUARANTINE_TESTS_PASSED")


if __name__ == "__main__":
    run()
