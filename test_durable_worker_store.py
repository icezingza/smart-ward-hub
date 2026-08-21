from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile

from durable_worker_store import (
    DurableWorkerIdempotencyConflict,
    DurableWorkerStateError,
    DurableWorkerStore,
    DurableWorkerStoreError,
)


class FixedClock:
    def __init__(self) -> None:
        self.value = datetime(2026, 8, 21, 11, 0, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.value

    def advance(self, seconds: int) -> None:
        self.value += timedelta(seconds=seconds)


def expect_error(error_type, callback) -> None:
    try:
        callback()
    except error_type:
        return
    raise AssertionError(f"expected {error_type.__name__}")


def submit(store: DurableWorkerStore, job_id: str, key: str, *, max_attempts: int = 3) -> dict:
    return store.submit(
        job_id=job_id,
        job_type="BACKUP_REPORT",
        args={"report_kind": "daily", "format": "json", "scope_ref": "ward-04"},
        idempotency_key=key,
        requester_role="reliability_operator",
        approver_role="security_auditor",
        approval_ref="approval-ref-001",
        max_attempts=max_attempts,
    )


def test_wal_restart_claim_and_complete() -> None:
    clock = FixedClock()
    with tempfile.TemporaryDirectory() as directory:
        db_path = str(Path(directory) / "worker.db")
        store = DurableWorkerStore(db_path, lease_seconds=10, clock=clock)
        job = submit(store, "durable-job-001", "durable-idem-001")
        assert job["status"] == "QUEUED"
        assert store.health()["journal_mode"] == "wal"
        assert store.health()["synchronous"] == 2
        assert store.health()["integrity_check"] == "ok"
        store.close()

        reopened = DurableWorkerStore(db_path, lease_seconds=10, clock=clock)
        assert reopened.get("durable-job-001")["status"] == "QUEUED"
        claimed = reopened.claim(job_id="durable-job-001", worker_id="worker-a", now=clock())
        assert claimed["status"] == "RUNNING" and claimed["attempts"] == 1
        completed = reopened.complete(job_id="durable-job-001", worker_id="worker-a", result={"report_kind": "daily", "scope_ref": "ward-04"}, now=clock())
        assert completed["status"] == "SUCCEEDED"
        assert reopened.health()["audit_chain_valid"] is True
        reopened.close()

        final = DurableWorkerStore(db_path, lease_seconds=10, clock=clock)
        assert final.get("durable-job-001")["status"] == "SUCCEEDED"
        final.close()
    print("[Durable Worker] WAL/FULL restart persistence, claim and completion: PASSED")


def test_idempotency_and_boundary_rejection() -> None:
    clock = FixedClock()
    with tempfile.TemporaryDirectory() as directory:
        store = DurableWorkerStore(str(Path(directory) / "worker.db"), clock=clock)
        first = submit(store, "durable-job-002", "durable-idem-002")
        replay = submit(store, "durable-job-002", "durable-idem-002")
        assert first["fingerprint"] == replay["fingerprint"]
        expect_error(
            DurableWorkerIdempotencyConflict,
            lambda: store.submit(
                job_id="durable-job-003",
                job_type="BACKUP_REPORT",
                args={"report_kind": "other"},
                idempotency_key="durable-idem-002",
                requester_role="reliability_operator",
                approver_role="security_auditor",
                approval_ref="approval-ref-001",
            ),
        )
        expect_error(
            DurableWorkerStoreError,
            lambda: store.submit(
                job_id="durable-job-004",
                job_type="BACKUP_REPORT",
                args={"patient_token": "must-not-enter"},
                idempotency_key="durable-idem-004",
                requester_role="reliability_operator",
                approver_role="security_auditor",
                approval_ref="approval-ref-001",
            ),
        )
        expect_error(
            DurableWorkerStoreError,
            lambda: store.submit(
                job_id="durable-job-005",
                job_type="BACKUP_REPORT",
                args={"report_kind": "daily"},
                idempotency_key="durable-idem-005",
                requester_role="reliability_operator",
                approver_role="security_auditor",
                approval_ref="approval-ref-001",
                clinical_state_mutation=True,
            ),
        )
        store.close()
    print("[Durable Worker] Idempotency, PII and clinical boundary rejection: PASSED")


def test_retry_bound_and_stale_reconciliation() -> None:
    clock = FixedClock()
    with tempfile.TemporaryDirectory() as directory:
        store = DurableWorkerStore(str(Path(directory) / "worker.db"), lease_seconds=10, clock=clock)
        submit(store, "durable-job-006", "durable-idem-006", max_attempts=2)
        store.claim(job_id="durable-job-006", worker_id="worker-a", now=clock())
        retried = store.fail(job_id="durable-job-006", worker_id="worker-a", retryable=True, now=clock())
        assert retried["status"] == "QUEUED" and retried["attempts"] == 1
        store.claim(job_id="durable-job-006", worker_id="worker-a", now=clock())
        exhausted = store.fail(job_id="durable-job-006", worker_id="worker-a", retryable=True, now=clock())
        assert exhausted["status"] == "FAILED" and exhausted["last_error"] == "RETRY_LIMIT_EXCEEDED"

        submit(store, "durable-job-007", "durable-idem-007")
        store.claim(job_id="durable-job-007", worker_id="worker-a", now=clock())
        clock.advance(11)
        blocked = store.recover_expired_leases(actor_role="control_room_coordinator", reconciliation_ref="reconcile-001", now=clock())
        assert blocked == ["durable-job-007"]
        requeued = store.reconcile(job_id="durable-job-007", decision="REQUEUE", actor_role="control_room_coordinator", reconciliation_ref="reconcile-002", now=clock())
        assert requeued["status"] == "QUEUED"
        completed = store.claim(job_id="durable-job-007", worker_id="worker-b", now=clock())
        assert completed["status"] == "RUNNING"
        result = store.complete(job_id="durable-job-007", worker_id="worker-b", result={"ok": True}, now=clock())
        assert result["status"] == "SUCCEEDED"
        store.close()
    print("[Durable Worker] Bounded retry, stale lease block and explicit requeue: PASSED")


def test_expired_completion_fails_closed_and_concurrent_claim_serializes() -> None:
    clock = FixedClock()
    with tempfile.TemporaryDirectory() as directory:
        db_path = str(Path(directory) / "worker.db")
        first = DurableWorkerStore(db_path, lease_seconds=10, clock=clock)
        second = DurableWorkerStore(db_path, lease_seconds=10, clock=clock)
        submit(first, "durable-job-008", "durable-idem-008")
        results: list[str] = []

        def do_claim(item: tuple[str, DurableWorkerStore]) -> str:
            label, store = item
            try:
                store.claim(job_id="durable-job-008", worker_id=f"worker-{label}", now=clock())
                return f"CLAIMED_{label}"
            except DurableWorkerStateError:
                return "REJECTED"

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(do_claim, (("first", first), ("second", second))))
        assert sum(result.startswith("CLAIMED_") for result in results) == 1
        winner = "first" if "CLAIMED_first" in results else "second"
        owner_store = first if winner == "first" else second
        owner_id = f"worker-{winner}"
        clock.advance(11)
        expect_error(
            DurableWorkerStateError,
            lambda: owner_store.complete(job_id="durable-job-008", worker_id=owner_id, result={"ok": True}, now=clock()),
        )
        assert owner_store.get("durable-job-008")["status"] == "BLOCKED"
        assert owner_store.verify_audit_chain() is True
        owner_store._connection.execute("UPDATE worker_audit SET details_json = '{\"tampered\":true}' WHERE event_seq = 1")
        assert owner_store.verify_audit_chain() is False
        owner_store._connection.execute("UPDATE worker_audit SET details_json = '{broken' WHERE event_seq = 1")
        assert owner_store.verify_audit_chain() is False
        assert owner_store.health()["audit_chain_valid"] is False
        first.close()
        second.close()
    print("[Durable Worker] Concurrent claim serialization, expired completion stop and audit tamper detection: PASSED")


def run() -> None:
    test_wal_restart_claim_and_complete()
    test_idempotency_and_boundary_rejection()
    test_retry_bound_and_stale_reconciliation()
    test_expired_completion_fails_closed_and_concurrent_claim_serializes()
    print("DURABLE_WORKER_STORE_TESTS_PASSED")


if __name__ == "__main__":
    run()
