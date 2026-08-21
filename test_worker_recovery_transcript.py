"""Focused/adversarial tests for redacted operator worker recovery transcript."""

from worker_recovery_transcript import (
    RecoveryTranscriptError,
    WorkerRecoveryTranscript,
    build_worker_recovery_transcript,
)


def test_transcript_contains_required_recovery_lifecycle_and_is_redacted():
    report = build_worker_recovery_transcript()
    assert report["schema_version"] == "smart-ward-worker-recovery-transcript-v1"
    assert report["evidence_class"] == "LOCAL_SOFTWARE_SIMULATION"
    assert report["read_only"] is True
    assert report["execution_performed"] is False
    assert report["replay_executed"] is False
    assert report["production_authorized"] is False
    assert report["clinical_validation_authorized"] is False
    assert report["external_authority"] == "NONE"
    assert report["runtime_authority"] == "NONE"
    assert report["transcript_integrity_valid"] is True
    assert report["raw_worker_identifiers_exported"] is False
    event_types = [event["event_type"] for event in report["transcript"]]
    assert event_types == [
        "LEASE_EXPIRY_OBSERVED",
        "LEASE_RECONCILIATION_RECORDED",
        "DEAD_LETTER_OBSERVED",
        "DEAD_LETTER_REPLAY_ELIGIBILITY_RECORDED",
        "QUEUE_BACKUP_BINDING_VERIFIED",
    ]
    serialized = str(report)
    for raw in (
        "job-lease-opaque-001",
        "worker-opaque-a",
        "reconcile-opaque-lease-001",
        "patient_token",
        "HN-",
        "PRIVATE KEY",
    ):
        assert raw not in serialized


def test_transcript_tamper_is_detected():
    transcript = WorkerRecoveryTranscript(
        correlation_ref="worker-recovery-test-001",
        operator_role="control_room_coordinator",
    )
    transcript.append(
        event_type="STATUS_OBSERVED",
        decision="RECONCILIATION_REQUIRED",
        remediation_code="LEASE_EXPIRED_REQUIRES_RECONCILIATION",
        details={"execution_performed": False},
    )
    assert transcript.verify() is True
    transcript.events[0]["decision"] = "SOFTWARE_REPLAY_ELIGIBLE"
    assert transcript.verify() is False


def test_raw_identifier_or_unsafe_operator_role_is_rejected():
    try:
        WorkerRecoveryTranscript(
            correlation_ref="HN-2026-8901",
            operator_role="control_room_coordinator",
        )
    except RecoveryTranscriptError:
        pass
    else:
        raise AssertionError("raw correlation reference accepted")

    try:
        WorkerRecoveryTranscript(
            correlation_ref="worker-recovery-test-002",
            operator_role="patient_operator",
        )
    except RecoveryTranscriptError:
        pass
    else:
        raise AssertionError("unsafe operator role accepted")


def test_transcript_rejects_secret_or_identity_markers_in_details():
    transcript = WorkerRecoveryTranscript(
        correlation_ref="worker-recovery-test-003",
        operator_role="security_auditor",
    )
    try:
        transcript.append(
            event_type="STATUS_OBSERVED",
            decision="RECONCILIATION_REQUIRED",
            remediation_code="AUDIT_CHAIN_INVALID",
            details={"notes": "private_key material must not appear"},
        )
    except RecoveryTranscriptError:
        pass
    else:
        raise AssertionError("secret marker accepted in transcript details")


def run() -> None:
    tests = [
        value for name, value in globals().items()
        if name.startswith("test_") and callable(value)
    ]
    for test in tests:
        test()
    print(f"[WorkerTranscript] focused/adversarial tests: {len(tests)} PASSED")
    print("WORKER_RECOVERY_TRANSCRIPT_TESTS_PASSED")


if __name__ == "__main__":
    run()
