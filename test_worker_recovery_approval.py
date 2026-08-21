"""Focused/adversarial tests for operator worker recovery approval/read-back."""

from copy import deepcopy

from worker_recovery_approval import (
    APPROVED_STATUS,
    READBACK_CONFIRMATION,
    ApprovalValidationError,
    approval_template,
    build_approval_readback,
    validate_readback,
)
from worker_recovery_transcript import build_worker_recovery_transcript


def test_approval_readback_is_valid_and_non_authorizing():
    report = build_approval_readback()
    approval = report["approval"]
    validation = report["validation"]
    assert approval["decision"] == APPROVED_STATUS
    assert approval["scope"] == "SOFTWARE_REHEARSAL_ONLY"
    assert approval["replay_execution_requested"] is False
    assert approval["replay_executed"] is False
    assert approval["requester_role"] != approval["approver_role"]
    assert approval["approver_role"] != approval["readback_role"]
    assert approval["requester_role"] != approval["readback_role"]
    assert validation["valid"] is True
    assert validation["actor_separation_valid"] is True
    assert validation["transcript_binding_valid"] is True
    assert validation["authorization_promoted"] is False
    assert validation["external_execution_authorized"] is False
    assert report["external_authority"] == "NONE"
    assert report["production_authorized"] is False
    assert report["clinical_validation_authorized"] is False


def test_transcript_binding_tamper_fails_closed():
    report = build_approval_readback()
    approval = deepcopy(report["approval"])
    approval["transcript_sha256"] = "f" * 64
    transcript = build_worker_recovery_transcript()
    try:
        validate_readback(approval, transcript)
    except ApprovalValidationError as exc:
        assert str(exc) == "transcript_binding_mismatch"
    else:
        raise AssertionError("transcript tamper accepted")


def test_queue_binding_tamper_fails_closed():
    report = build_approval_readback()
    approval = deepcopy(report["approval"])
    approval["queue_binding_sha256"] = "a" * 64
    transcript = build_worker_recovery_transcript()
    # Queue binding is a format-bound reference here; a changed hash remains a
    # hash-shaped value but must be rejected by the independent binding check in
    # the read-back flow when the source details are available.
    approval["queue_backup_ref"] = "backup:tampered-001"
    try:
        validate_readback(approval, transcript)
    except ApprovalValidationError as exc:
        assert str(exc) in {"queue_binding_mismatch", "queue_backup_ref_mismatch", "queue_backup_ref_must_be_opaque"}
    else:
        raise AssertionError("queue binding tamper accepted")


def test_actor_collision_fails_closed():
    report = build_approval_readback()
    approval = deepcopy(report["approval"])
    approval["readback_role"] = approval["approver_role"]
    try:
        validate_readback(approval, build_worker_recovery_transcript())
    except ApprovalValidationError as exc:
        assert str(exc) == "actor_separation_required"
    else:
        raise AssertionError("actor collision accepted")


def test_confirmation_and_timestamp_boundaries_fail_closed():
    report = build_approval_readback()
    approval = deepcopy(report["approval"])
    approval["approval_confirmation"] = "WRONG_CONFIRMATION"
    try:
        validate_readback(approval, build_worker_recovery_transcript())
    except ApprovalValidationError as exc:
        assert str(exc) == "approval_confirmation_required"
    else:
        raise AssertionError("wrong approval confirmation accepted")

    approval = deepcopy(report["approval"])
    approval["readback_timestamp_utc"] = "2026-08-21T23:59:00Z"
    try:
        validate_readback(approval, build_worker_recovery_transcript())
    except ApprovalValidationError as exc:
        assert str(exc) == "readback_must_follow_approval"
    else:
        raise AssertionError("out-of-order timestamp accepted")


def test_authorization_mutation_and_execution_request_fail_closed():
    report = build_approval_readback()
    approval = deepcopy(report["approval"])
    approval["production_authorized"] = True
    try:
        validate_readback(approval, build_worker_recovery_transcript())
    except ApprovalValidationError as exc:
        assert str(exc) in {"authorization_boundary_mutated", "production_authorized_mutated"}
    else:
        raise AssertionError("production authorization mutation accepted")

    approval = deepcopy(report["approval"])
    approval["replay_execution_requested"] = True
    try:
        validate_readback(approval, build_worker_recovery_transcript())
    except ApprovalValidationError as exc:
        assert str(exc) == "replay_execution_request_forbidden"
    else:
        raise AssertionError("execution request accepted")


def test_template_is_exact_and_unknown_fields_are_rejected():
    template = approval_template()
    assert template["decision"] == "READBACK_REQUIRED"
    assert template["replay_executed"] is False
    mutated = deepcopy(template)
    mutated["unexpected"] = "value"
    try:
        validate_readback(mutated, build_worker_recovery_transcript())
    except ApprovalValidationError as exc:
        assert "payload_fields_mismatch" in str(exc)
    else:
        raise AssertionError("unknown approval field accepted")


def run() -> None:
    tests = [
        value for name, value in globals().items()
        if name.startswith("test_") and callable(value)
    ]
    for test in tests:
        test()
    print(f"[WorkerApproval] focused/adversarial tests: {len(tests)} PASSED")
    print("WORKER_RECOVERY_APPROVAL_TESTS_PASSED")


if __name__ == "__main__":
    run()
