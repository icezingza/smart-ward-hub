"""Focused/adversarial tests for the P4 reviewer read-back decision guard."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from p4_reviewer_readback_decision_guard import (
    DECISION_RECORD_PATH,
    ROOT,
    _load_json,
    evaluate_readback_guard,
)


def test_readback_guard_is_verified_without_authorization():
    report = evaluate_readback_guard()
    assert report["decision"] == "P4_REVIEWER_READBACK_GUARD_VERIFIED"
    assert report["remediation_codes"] == []
    assert all(report["checks"].values())
    assert report["fresh_poll_result"]["result"] == "POLL_ACCEPTED_UNVERIFIED"
    assert report["fresh_poll_result"]["trusted"] is False
    assert report["stale_poll_result"]["result"] == "STALE_RESPONSE_REJECTED"
    assert report["external_update_result"]["state"] == "BLOCKED_SIMULATION"
    assert report["external_update_result"]["external_decision_verified"] is False
    assert report["external_update_result"]["authorization_promoted"] is False
    assert report["audit_event_count"] == 2
    assert report["appointment_confirmed"] is False
    assert report["submission_allowed"] is False
    assert report["ready_for_external_appointment"] is True
    assert report["ready_for_external_review"] is False
    print("[P4 Read-back] Unverified read-back remains non-authorizing: PASSED")


def test_local_snapshot_mutation_fails_closed():
    snapshot = deepcopy(_load_json(ROOT / DECISION_RECORD_PATH))
    snapshot["authorization_promoted"] = True

    def load_mutated(path: Path):
        if path.name == DECISION_RECORD_PATH.name:
            return snapshot
        return _load_json(path)

    with patch("p4_reviewer_readback_decision_guard._load_json", side_effect=load_mutated):
        report = evaluate_readback_guard()
    assert report["decision"] == "P4_REVIEWER_READBACK_GUARD_BLOCKED"
    assert report["checks"]["local_decision_record_template_valid"] is False
    assert "LOCAL_DECISION_RECORD_TEMPLATE_VALID" in report["remediation_codes"]
    assert report["authorization_promoted"] is False
    print("[P4 Read-back] Local snapshot authorization mutation fails closed: PASSED")


def test_appointment_dependency_mutation_fails_closed():
    dependency = {
        "decision": "P4_INDEPENDENT_REVIEWER_APPOINTMENT_PLAN_BLOCKED",
        "appointment_confirmed": True,
        "submission_allowed": True,
    }
    with patch("p4_reviewer_readback_decision_guard.evaluate_appointment_plan", return_value=dependency):
        report = evaluate_readback_guard()
    assert report["decision"] == "P4_REVIEWER_READBACK_GUARD_BLOCKED"
    assert report["checks"]["appointment_plan_still_template_only"] is False
    assert "APPOINTMENT_PLAN_STILL_TEMPLATE_ONLY" in report["remediation_codes"]
    print("[P4 Read-back] Appointment dependency mutation fails closed: PASSED")


def test_reviewer_handoff_dependency_mutation_fails_closed():
    dependency = {
        "decision": "P4_INDEPENDENT_REVIEWER_HANDOFF_READY",
        "ready_for_external_review": True,
    }
    with patch("p4_reviewer_readback_decision_guard.evaluate_reviewer_handoff_readiness", return_value=dependency):
        report = evaluate_readback_guard()
    assert report["decision"] == "P4_REVIEWER_READBACK_GUARD_BLOCKED"
    assert report["checks"]["reviewer_handoff_still_appointment_only"] is False
    assert "REVIEWER_HANDOFF_STILL_APPOINTMENT_ONLY" in report["remediation_codes"]
    print("[P4 Read-back] Reviewer handoff promotion mutation fails closed: PASSED")


def test_local_update_and_external_response_cannot_promote_authority():
    report = evaluate_readback_guard()
    assert report["unauthorized_local_update_rejected"] is True
    assert report["external_update_result"]["trusted"] is False
    assert report["external_update_result"]["external_execution_authorized"] is False
    assert report["external_update_result"]["production_authorized"] is False
    assert report["external_update_result"]["clinical_validation_authorized"] is False
    assert report["post_update_status"]["authorization_boundary"] == {
        "external_authority": "NONE",
        "clinical_validation_authorized": False,
        "production_authorized": False,
        "runtime_authority": "NONE",
        "pilot_gate_status": "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION",
    }
    print("[P4 Read-back] Local/external response cannot promote authority: PASSED")


def test_lifecycle_integrity_mutation_is_detected_by_contract():
    report = evaluate_readback_guard()
    assert report["checks"]["audit_chain_valid"] is True
    assert report["post_update_status"]["remote_revision"] == 1
    assert report["post_update_status"]["state"] == "BLOCKED_SIMULATION"
    assert report["stale_poll_result"]["reason"] == "stale_or_future_response"
    print("[P4 Read-back] Lifecycle revision and audit integrity: PASSED")


def run() -> None:
    tests = [
        test_readback_guard_is_verified_without_authorization,
        test_local_snapshot_mutation_fails_closed,
        test_appointment_dependency_mutation_fails_closed,
        test_reviewer_handoff_dependency_mutation_fails_closed,
        test_local_update_and_external_response_cannot_promote_authority,
        test_lifecycle_integrity_mutation_is_detected_by_contract,
    ]
    for test in tests:
        test()
    print(f"[P4 Read-back] focused/adversarial tests: {len(tests)} PASSED")
    print("P4_REVIEWER_READBACK_DECISION_GUARD_TESTS_PASSED")


if __name__ == "__main__":
    run()
