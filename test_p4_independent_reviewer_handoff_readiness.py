"""Focused/adversarial tests for the P4 independent-reviewer handoff readiness control."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from p4_independent_reviewer_handoff_readiness import (
    PREFLIGHT_PATH,
    ROOT,
    _load_json,
    evaluate_reviewer_handoff_readiness,
)


def test_reviewer_handoff_is_ready_only_for_external_appointment():
    report = evaluate_reviewer_handoff_readiness()
    assert report["decision"] == "P4_INDEPENDENT_REVIEWER_HANDOFF_READY"
    assert report["remediation_codes"] == []
    assert all(report["checks"].values())
    assert report["mapping_count"] == 12
    assert report["artifact_count"] == 22
    assert report["external_inputs_pending_count"] == 12
    assert report["checklist_status_counts"] == {
        "PENDING_EXTERNAL": 8,
        "SOFTWARE_VERIFIED_PENDING_READBACK": 3,
        "SOFTWARE_LOCKED_EXTERNAL_REVIEW_PENDING": 1,
    }
    assert report["ready_for_external_appointment"] is True
    assert report["ready_for_external_review"] is False
    assert report["submission_allowed"] is False
    assert report["reviewer_appointment"] == "PENDING_EXTERNAL_APPOINTMENT"
    assert report["external_decision"] == "NOT_ISSUED"
    print("[P4 Reviewer] Handoff is ready only for external appointment: PASSED")


def test_checklist_mutation_fails_closed():
    preflight = deepcopy(_load_json(ROOT / PREFLIGHT_PATH))
    preflight["reviewer_checklist"] = preflight["reviewer_checklist"][:-1]

    def load_mutated(path: Path):
        if path.name == PREFLIGHT_PATH.name:
            return preflight
        return _load_json(path)

    with patch("p4_independent_reviewer_handoff_readiness._load_json", side_effect=load_mutated):
        report = evaluate_reviewer_handoff_readiness()
    assert report["decision"] == "P4_INDEPENDENT_REVIEWER_HANDOFF_BLOCKED"
    assert report["checks"]["preflight_schema_valid"] is False
    assert report["checks"]["twelve_item_checklist_complete"] is False
    assert "REVIEWER_PREFLIGHT_INVALID" in report["remediation_codes"]
    assert "REVIEWER_CHECKLIST_INCOMPLETE" in report["remediation_codes"]
    print("[P4 Reviewer] Checklist mutation fails closed: PASSED")


def test_artifact_mapping_mutation_fails_closed():
    preflight = deepcopy(_load_json(ROOT / PREFLIGHT_PATH))
    preflight["artifact_count"] = 21

    def load_mutated(path: Path):
        if path.name == PREFLIGHT_PATH.name:
            return preflight
        return _load_json(path)

    with patch("p4_independent_reviewer_handoff_readiness._load_json", side_effect=load_mutated):
        report = evaluate_reviewer_handoff_readiness()
    assert report["decision"] == "P4_INDEPENDENT_REVIEWER_HANDOFF_BLOCKED"
    assert report["checks"]["twenty_two_artifacts_bound"] is False
    assert "REVIEWER_PREFLIGHT_INVALID" in report["remediation_codes"]
    assert "REVIEWER_ARTIFACT_MAPPING_INCOMPLETE" in report["remediation_codes"]
    print("[P4 Reviewer] Artifact mapping mutation fails closed: PASSED")


def test_external_appointment_mutation_fails_closed():
    preflight = deepcopy(_load_json(ROOT / PREFLIGHT_PATH))
    preflight["reviewer_appointment"] = "APPOINTED"

    def load_mutated(path: Path):
        if path.name == PREFLIGHT_PATH.name:
            return preflight
        return _load_json(path)

    with patch("p4_independent_reviewer_handoff_readiness._load_json", side_effect=load_mutated):
        report = evaluate_reviewer_handoff_readiness()
    assert report["decision"] == "P4_INDEPENDENT_REVIEWER_HANDOFF_BLOCKED"
    assert report["checks"]["external_appointment_boundary_locked"] is False
    assert "REVIEWER_PREFLIGHT_INVALID" in report["remediation_codes"]
    assert "REVIEWER_APPOINTMENT_BOUNDARY_MUTATED" in report["remediation_codes"]
    assert report["submission_allowed"] is False
    print("[P4 Reviewer] Appointment mutation fails closed: PASSED")


def test_authorization_mutation_fails_closed():
    preflight = deepcopy(_load_json(ROOT / PREFLIGHT_PATH))
    preflight["authorization_boundary"]["production_authorized"] = True

    def load_mutated(path: Path):
        if path.name == PREFLIGHT_PATH.name:
            return preflight
        return _load_json(path)

    with patch("p4_independent_reviewer_handoff_readiness._load_json", side_effect=load_mutated):
        report = evaluate_reviewer_handoff_readiness()
    assert report["decision"] == "P4_INDEPENDENT_REVIEWER_HANDOFF_BLOCKED"
    assert report["checks"]["preflight_schema_valid"] is False
    assert report["checks"]["authorization_boundary_locked"] is False
    assert "REVIEWER_AUTHORIZATION_BOUNDARY_MUTATED" in report["remediation_codes"]
    assert report["production_authorized"] is False
    assert report["authorization_promoted"] is False
    print("[P4 Reviewer] Authorization mutation cannot promote reviewer handoff: PASSED")


def test_redaction_and_freeze_mutations_fail_closed():
    preflight = deepcopy(_load_json(ROOT / PREFLIGHT_PATH))
    preflight["external_inputs_pending"][0] = "HN-RAW-IDENTITY must not be exported"

    def load_mutated(path: Path):
        if path.name == PREFLIGHT_PATH.name:
            return preflight
        return _load_json(path)

    with patch("p4_independent_reviewer_handoff_readiness._load_json", side_effect=load_mutated), patch(
        "p4_independent_reviewer_handoff_readiness._freeze_hash", return_value="0" * 64
    ):
        report = evaluate_reviewer_handoff_readiness()
    assert report["decision"] == "P4_INDEPENDENT_REVIEWER_HANDOFF_BLOCKED"
    assert report["checks"]["preflight_redacted"] is False
    assert report["checks"]["preflight_freeze_bound"] is False
    assert "REVIEWER_PREFLIGHT_REDACTION_FAILED" in report["remediation_codes"]
    assert "REVIEWER_PREFLIGHT_FREEZE_BINDING_MISSING" in report["remediation_codes"]
    print("[P4 Reviewer] Redaction and freeze mutations fail closed: PASSED")


def run() -> None:
    tests = [
        test_reviewer_handoff_is_ready_only_for_external_appointment,
        test_checklist_mutation_fails_closed,
        test_artifact_mapping_mutation_fails_closed,
        test_external_appointment_mutation_fails_closed,
        test_authorization_mutation_fails_closed,
        test_redaction_and_freeze_mutations_fail_closed,
    ]
    for test in tests:
        test()
    print(f"[P4 Reviewer] focused/adversarial tests: {len(tests)} PASSED")
    print("P4_INDEPENDENT_REVIEWER_HANDOFF_READINESS_TESTS_PASSED")


if __name__ == "__main__":
    run()
