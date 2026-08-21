"""Focused/adversarial tests for durable worker replay contract."""

from durable_worker_replay_contract import (
    WorkerReplayCode,
    WorkerReplayDecision,
    classify_job,
    evaluate_dead_letter_replay,
    run_rehearsal,
)


def test_rehearsal_covers_lease_restart_dead_letter_and_backup_restore():
    report = run_rehearsal()
    assert report["contract"] == "DURABLE_WORKER_REPLAY_CONTRACT_V1"
    assert report["mode"] == "SOFTWARE_FIXTURE"
    assert report["read_only_external_boundary"] is True
    assert report["external_transmission_performed"] is False
    assert report["clinical_state_mutation_performed"] is False
    assert report["runtime_replay_executed"] is False
    assert report["authorization_boundary"] == {
        "external_authority": False,
        "production_authorized": False,
        "runtime_authority": "NONE",
    }
    assert report["lease_recovery"]["blocked_classification"] == WorkerReplayCode.LEASE_EXPIRED_REQUIRES_RECONCILIATION
    assert report["lease_recovery"]["requeued_status"] == "QUEUED"
    assert report["lease_recovery"]["restart_health"]["audit_chain_valid"] is True
    assert report["dead_letter"]["classification"] == WorkerReplayCode.RETRY_LIMIT_EXCEEDED_DEAD_LETTER
    assert report["dead_letter"]["confirmation_required"]["decision"] == WorkerReplayDecision.OPERATOR_CONFIRMATION_REQUIRED
    assert report["dead_letter"]["confirmation_required"]["replay_executed"] is False
    assert report["dead_letter"]["replay_eligible"]["decision"] == WorkerReplayDecision.SOFTWARE_REPLAY_ELIGIBLE
    assert report["dead_letter"]["replay_eligible"]["replay_permitted"] is True
    assert report["dead_letter"]["replay_eligible"]["replay_executed"] is False
    assert report["backup_restore"]["restore_result"]["binding_verified"] is True
    assert report["backup_restore"]["restore_result"]["worker_queue_restore_status"] == "SOFTWARE_RESTORE_VERIFIED"
    assert report["backup_restore"]["restored_dead_letter_classification"] == WorkerReplayCode.RETRY_LIMIT_EXCEEDED_DEAD_LETTER
    assert report["backup_restore"]["restored_lease_status"] == "QUEUED"
    assert report["backup_restore"]["restored_health"]["journal_mode"] == "wal"
    assert report["backup_restore"]["restored_health"]["synchronous"] == 2
    assert report["backup_restore"]["restored_health"]["audit_chain_valid"] is True


def test_non_dead_letter_job_cannot_enter_dead_letter_replay():
    job = {
        "job_id": "job-opaque-queued-001",
        "status": "QUEUED",
        "attempts": 1,
        "last_error": "RETRYABLE_FAILURE",
    }
    assert classify_job(job) == WorkerReplayCode.RETRYABLE_FAILURE_RETAINED
    decision = evaluate_dead_letter_replay(job, operator_confirmation_present=True)
    assert decision.decision == WorkerReplayDecision.RECONCILIATION_REQUIRED
    assert decision.replay_permitted is False
    assert decision.replay_executed is False


def test_authorization_mutation_fails_closed_even_with_confirmation():
    job = {
        "job_id": "job-opaque-dead-002",
        "status": "FAILED",
        "attempts": 3,
        "last_error": "RETRY_LIMIT_EXCEEDED",
    }
    decision = evaluate_dead_letter_replay(
        job,
        operator_confirmation_present=True,
        authorization_boundary={
            "external_authority": True,
            "production_authorized": True,
            "runtime_authority": "WORKER",
        },
    )
    assert decision.decision == WorkerReplayDecision.RECONCILIATION_REQUIRED
    assert decision.remediation_code == WorkerReplayCode.AUTHORIZATION_BOUNDARY_LOCKED
    assert decision.resume_permitted is False
    assert decision.replay_permitted is False
    assert decision.replay_executed is False
    assert decision.production_authorized is False
    assert decision.external_authority is False


def test_opaque_job_reference_is_redacted_in_replay_decision():
    job = {
        "job_id": "job-opaque-dead-003",
        "status": "FAILED",
        "attempts": 3,
        "last_error": "RETRY_LIMIT_EXCEEDED",
    }
    decision = evaluate_dead_letter_replay(job, operator_confirmation_present=False)
    assert job["job_id"] not in str(decision.to_dict())
    assert decision.opaque_refs["job_ref"].startswith("job:")


def run() -> None:
    tests = [
        value for name, value in globals().items()
        if name.startswith("test_") and callable(value)
    ]
    for test in tests:
        test()
    print(f"[WorkerReplay] focused/adversarial tests: {len(tests)} PASSED")
    print("DURABLE_WORKER_REPLAY_CONTRACT_TESTS_PASSED")


if __name__ == "__main__":
    run()
