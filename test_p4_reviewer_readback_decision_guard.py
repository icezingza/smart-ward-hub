"""Focused/adversarial tests for the P4 reviewer read-back decision guard."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from external_decision_lifecycle import (
    DecisionLifecycle,
    DecisionLifecycleError,
    STALE_RESPONSE_REJECTED,
)
from external_decision_record import DecisionRecordValidationError, validate
from p4_reviewer_readback_decision_guard import (
    DECISION_RECORD_PATH,
    ROOT,
    _fixture_received_record,
    _load_json,
    _response,
    evaluate_readback_guard,
)


NOW = datetime(2026, 8, 22, 18, 15, tzinfo=timezone.utc)


def _expect_record_error(record: dict, label: str) -> None:
    try:
        validate(record)
    except DecisionRecordValidationError:
        print(f"[P4 Read-back] {label}: PASSED")
        return
    raise AssertionError(f"{label}: malformed decision record was accepted")


def _expect_lifecycle_error(callback, label: str) -> None:
    try:
        callback()
    except DecisionLifecycleError:
        print(f"[P4 Read-back] {label}: PASSED")
        return
    raise AssertionError(f"{label}: unsafe lifecycle input was accepted")


def test_readback_guard_is_verified_without_authorization():
    report = evaluate_readback_guard()
    assert report["decision"] == "P4_REVIEWER_READBACK_GUARD_VERIFIED"
    assert report["remediation_codes"] == []
    assert all(report["checks"].values())
    assert report["fresh_poll_result"]["result"] == "POLL_ACCEPTED_UNVERIFIED"
    assert report["fresh_poll_result"]["trusted"] is False
    assert report["fresh_poll_result"]["external_decision_verified"] is False
    assert report["stale_poll_result"]["result"] == STALE_RESPONSE_REJECTED
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


def test_received_record_malformed_and_authorization_mutations_fail_closed():
    malformed = _fixture_received_record()
    malformed["record_id"] = "patient:raw-identity"
    _expect_record_error(malformed, "Malformed opaque decision record")

    unknown = _fixture_received_record()
    unknown["unexpected_field"] = "fixture"
    _expect_record_error(unknown, "Unknown decision-record field")

    promoted = _fixture_received_record()
    promoted["authorization_promoted"] = True
    _expect_record_error(promoted, "Decision-record authorization promotion")

    verified = _fixture_received_record()
    verified["external_decision_verified"] = True
    _expect_record_error(verified, "Decision-record external verification promotion")


def test_redaction_marker_in_decision_record_fails_closed():
    secret = _fixture_received_record()
    secret["signature_ref"] = "signature:Bearer-token"
    _expect_record_error(secret, "Secret marker in decision record")

    identity = _fixture_received_record()
    identity["decision_basis"]["finding_ids"] = ["finding:@raw-contact"]
    _expect_record_error(identity, "Raw identity marker in decision record")


def test_stale_future_and_hash_mismatch_poll_fail_closed_without_mutation():
    lifecycle = DecisionLifecycle(_fixture_received_record(), now=NOW)
    initial_state = lifecycle.state
    initial_revision = lifecycle.revision

    stale = lifecycle.poll(
        _response(
            decision_id=lifecycle.decision_id,
            revision=0,
            status="PENDING_EXTERNAL_VERIFICATION",
            observed_at=NOW - timedelta(seconds=301),
        ),
        now=NOW,
    )
    assert stale["result"] == STALE_RESPONSE_REJECTED

    future = lifecycle.poll(
        _response(
            decision_id=lifecycle.decision_id,
            revision=0,
            status="PENDING_EXTERNAL_VERIFICATION",
            observed_at=NOW + timedelta(seconds=61),
        ),
        now=NOW,
    )
    assert future["result"] == STALE_RESPONSE_REJECTED

    _expect_lifecycle_error(
        lambda: lifecycle.poll(
            _response(
                decision_id=lifecycle.decision_id,
                revision=0,
                status="PENDING_EXTERNAL_VERIFICATION",
                observed_at=NOW,
            ),
            now=NOW,
            known_event_hash="d" * 64,
        ),
        "Poll event-hash mismatch",
    )
    _expect_lifecycle_error(
        lambda: lifecycle.poll(
            _response(
                decision_id=lifecycle.decision_id,
                revision=0,
                status="DECISION_PENDING_EXTERNAL_VERIFICATION",
                observed_at=NOW,
            ),
            now=NOW,
        ),
        "Internal lifecycle status used as external wire status",
    )
    assert lifecycle.state == initial_state
    assert lifecycle.revision == initial_revision
    print("[P4 Read-back] Stale/future/hash-mismatch polls preserve local state: PASSED")


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


def test_lifecycle_snapshot_boundary_mutation_is_isolated():
    lifecycle = DecisionLifecycle(_fixture_received_record(), now=NOW)
    snapshot = lifecycle.snapshot()
    snapshot["authorization_boundary"]["production_authorized"] = True
    snapshot["events"][0]["to_state"] = "AUTHORIZED_BY_EXTERNAL_OWNER"
    status = lifecycle.status(now=NOW)
    status["authorization_boundary"]["production_authorized"] = True
    assert lifecycle.status(now=NOW)["authorization_boundary"]["production_authorized"] is False
    assert lifecycle.audit_chain_valid() is True
    print("[P4 Read-back] Snapshot/status boundary mutation is isolated: PASSED")


def test_lifecycle_audit_tamper_is_detected():
    lifecycle = DecisionLifecycle(_fixture_received_record(), now=NOW)
    original = lifecycle._events[0]
    lifecycle._events[0] = replace(original, to_state="AUTHORIZED_BY_EXTERNAL_OWNER")
    assert lifecycle.audit_chain_valid() is False
    print("[P4 Read-back] Audit-chain tamper is detected: PASSED")


def run() -> None:
    tests = [
        test_readback_guard_is_verified_without_authorization,
        test_local_snapshot_mutation_fails_closed,
        test_appointment_dependency_mutation_fails_closed,
        test_reviewer_handoff_dependency_mutation_fails_closed,
        test_received_record_malformed_and_authorization_mutations_fail_closed,
        test_redaction_marker_in_decision_record_fails_closed,
        test_stale_future_and_hash_mismatch_poll_fail_closed_without_mutation,
        test_local_update_and_external_response_cannot_promote_authority,
        test_lifecycle_snapshot_boundary_mutation_is_isolated,
        test_lifecycle_audit_tamper_is_detected,
    ]
    for test in tests:
        test()
    print(f"[P4 Read-back] focused/adversarial tests: {len(tests)} PASSED")
    print("P4_REVIEWER_READBACK_DECISION_GUARD_TESTS_PASSED")


if __name__ == "__main__":
    run()
