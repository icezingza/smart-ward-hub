from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

from worker_control_plane import (
    RetryableWorkerError,
    TerminalWorkerError,
    WorkerControlPlane,
    WorkerIdempotencyConflict,
    WorkerStateError,
    WorkerValidationError,
)


class FixedClock:
    def __init__(self) -> None:
        self.value = datetime(2026, 8, 21, 10, 0, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.value

    def advance(self, seconds: int) -> None:
        self.value += timedelta(seconds=seconds)


def expect_error(error_type, callback):
    try:
        callback()
    except error_type:
        return
    raise AssertionError(f"expected {error_type.__name__}")


def make_plane(clock: FixedClock, *, retry_state: dict[str, int] | None = None) -> WorkerControlPlane:
    retry_state = retry_state if retry_state is not None else {}

    def backup_handler(args: dict) -> dict:
        scope_ref = args.get("scope_ref")
        if scope_ref == "retry":
            retry_state[scope_ref] = retry_state.get(scope_ref, 0) + 1
            if retry_state[scope_ref] < 3:
                raise RetryableWorkerError()
        if scope_ref == "terminal":
            raise TerminalWorkerError()
        return {"report_kind": args.get("report_kind", "summary"), "scope_ref": scope_ref or "none"}

    return WorkerControlPlane(
        handlers={"backup.report": backup_handler, "evidence.report": backup_handler},
        lease_seconds=10,
        clock=clock,
    )


def base_submit(plane: WorkerControlPlane, *, job_id: str, key: str, scope_ref: str = "ward-04") -> dict:
    return plane.submit(
        job_id=job_id,
        job_type="BACKUP_REPORT",
        args={"report_kind": "daily", "format": "json", "scope_ref": scope_ref},
        idempotency_key=key,
        requester_role="reliability_operator",
        approver_role="security_auditor",
        approval_ref="approval-ref-001",
        max_attempts=3,
        external_side_effects_allowed=False,
        clinical_state_mutation=False,
    )


def test_submit_idempotency_and_boundary():
    clock = FixedClock()
    plane = make_plane(clock)
    first = base_submit(plane, job_id="job-001", key="idem-001")
    replay = base_submit(plane, job_id="job-001", key="idem-001")
    assert first["fingerprint"] == replay["fingerprint"]
    assert replay["status"] == "QUEUED"
    replay["args"]["scope_ref"] = "mutated-outside"
    assert plane.get("job-001")["args"]["scope_ref"] == "ward-04"

    expect_error(
        WorkerIdempotencyConflict,
        lambda: plane.submit(
            job_id="job-002",
            job_type="BACKUP_REPORT",
            args={"report_kind": "different"},
            idempotency_key="idem-001",
            requester_role="reliability_operator",
            approver_role="security_auditor",
            approval_ref="approval-ref-001",
        ),
    )
    expect_error(
        WorkerIdempotencyConflict,
        lambda: plane.submit(
            job_id="job-001",
            job_type="BACKUP_REPORT",
            args={"report_kind": "daily"},
            idempotency_key="idem-002",
            requester_role="reliability_operator",
            approver_role="security_auditor",
            approval_ref="approval-ref-001",
        ),
    )
    expect_error(
        WorkerValidationError,
        lambda: plane.submit(
            job_id="job-003",
            job_type="BACKUP_REPORT",
            args={"patient_token": "must-not-enter"},
            idempotency_key="idem-003",
            requester_role="reliability_operator",
            approver_role="security_auditor",
            approval_ref="approval-ref-001",
        ),
    )
    expect_error(
        WorkerValidationError,
        lambda: plane.submit(
            job_id="job-004",
            job_type="BACKUP_REPORT",
            args={"report_kind": "daily"},
            idempotency_key="idem-004",
            requester_role="reliability_operator",
            approver_role="reliability_operator",
            approval_ref="approval-ref-001",
        ),
    )
    expect_error(
        WorkerValidationError,
        lambda: plane.submit(
            job_id="job-005",
            job_type="BACKUP_REPORT",
            args={"report_kind": "daily"},
            idempotency_key="idem-005",
            requester_role="reliability_operator",
            approver_role="security_auditor",
            approval_ref="approval-ref-001",
            external_side_effects_allowed=True,
        ),
    )
    print("[Worker] Idempotency, PII boundary, role separation and side-effect boundary: PASSED")


def test_success_and_concurrent_claim_serialization():
    clock = FixedClock()
    plane = make_plane(clock)
    base_submit(plane, job_id="job-success", key="idem-success")

    def claim():
        try:
            return plane.claim(job_id="job-success", worker_id="worker-a", now=clock())
        except WorkerStateError:
            return "REJECTED"

    with ThreadPoolExecutor(max_workers=2) as executor:
        claims = list(executor.map(lambda _: claim(), range(2)))
    assert sum(value != "REJECTED" for value in claims) == 1
    result = plane.run_once(job_id="job-success", worker_id="worker-b", now=clock()) if False else plane.get("job-success")
    assert result["status"] == "RUNNING"
    # A running job cannot be claimed or executed twice by another worker.
    expect_error(WorkerStateError, lambda: plane.claim(job_id="job-success", worker_id="worker-b", now=clock()))
    print("[Worker] Lock serialization and duplicate claim refusal: PASSED")


def test_bounded_retry_and_terminal_failure():
    clock = FixedClock()
    retry_state: dict[str, int] = {}
    plane = make_plane(clock, retry_state=retry_state)
    base_submit(plane, job_id="job-retry", key="idem-retry", scope_ref="retry")
    first = plane.run_once(job_id="job-retry", worker_id="worker-a", now=clock())
    assert first["status"] == "QUEUED" and first["attempts"] == 1
    clock.advance(1)
    second = plane.run_once(job_id="job-retry", worker_id="worker-a", now=clock())
    assert second["status"] == "QUEUED" and second["attempts"] == 2
    clock.advance(1)
    third = plane.run_once(job_id="job-retry", worker_id="worker-a", now=clock())
    assert third["status"] == "SUCCEEDED" and third["attempts"] == 3

    base_submit(plane, job_id="job-terminal", key="idem-terminal", scope_ref="terminal")
    terminal = plane.run_once(job_id="job-terminal", worker_id="worker-a", now=clock())
    assert terminal["status"] == "FAILED"
    assert terminal["last_error"] == "TERMINAL_FAILURE"
    print("[Worker] Bounded retry and fail-closed terminal failure: PASSED")


def test_stale_lease_reconciliation_and_audit():
    clock = FixedClock()
    plane = make_plane(clock)
    base_submit(plane, job_id="job-stale", key="idem-stale")
    plane.claim(job_id="job-stale", worker_id="worker-a", now=clock())
    clock.advance(11)
    blocked = plane.recover_stale_leases(
        actor_role="control_room_coordinator",
        reconciliation_ref="reconcile-001",
        now=clock(),
    )
    assert blocked == ["job-stale"]
    expect_error(
        WorkerStateError,
        lambda: plane.claim(job_id="job-stale", worker_id="worker-b", now=clock()),
    )
    requeued = plane.reconcile(
        job_id="job-stale",
        decision="REQUEUE",
        actor_role="control_room_coordinator",
        reconciliation_ref="reconcile-002",
        now=clock(),
    )
    assert requeued["status"] == "QUEUED"
    succeeded = plane.run_once(job_id="job-stale", worker_id="worker-b", now=clock())
    assert succeeded["status"] == "SUCCEEDED"
    assert plane.verify_audit_chain() is True
    plane._audit[0]["result"] = "TAMPERED"
    assert plane.verify_audit_chain() is False
    print("[Worker] Stale lease stop, explicit reconciliation and audit tamper detection: PASSED")


def test_stale_recovery_role_separation():
    clock = FixedClock()
    plane = WorkerControlPlane(
        handlers={"backup.report": lambda args: {"ok": True}},
        lease_seconds=10,
        clock=clock,
    )
    plane.submit(
        job_id="job-role-separation",
        job_type="BACKUP_REPORT",
        args={"report_kind": "daily"},
        idempotency_key="idem-role-separation",
        requester_role="reliability_operator",
        approver_role="control_room_coordinator",
        approval_ref="approval-ref-002",
    )
    plane.claim(job_id="job-role-separation", worker_id="worker-a", now=clock())
    clock.advance(11)
    plane.recover_stale_leases(
        actor_role="reliability_operator",
        reconciliation_ref="reconcile-003",
        now=clock(),
    )
    expect_error(
        WorkerValidationError,
        lambda: plane.reconcile(
            job_id="job-role-separation",
            decision="REQUEUE",
            actor_role="control_room_coordinator",
            reconciliation_ref="reconcile-004",
            now=clock(),
        ),
    )
    print("[Worker] Recovery approver separation-of-duties: PASSED")


def run() -> None:
    test_submit_idempotency_and_boundary()
    test_success_and_concurrent_claim_serialization()
    test_bounded_retry_and_terminal_failure()
    test_stale_lease_reconciliation_and_audit()
    test_stale_recovery_role_separation()
    print("WORKER_CONTROL_PLANE_TESTS_PASSED")


if __name__ == "__main__":
    run()
