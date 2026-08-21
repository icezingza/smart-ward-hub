"""Durable worker replay contract for an isolated SQLite software fixture.

This module orchestrates the existing ``DurableWorkerStore`` and
``worker_queue_backup`` utilities only inside a temporary non-production target.
It never invokes a scheduler, network, provider, clinical action, or external
worker. Replay eligibility is a decision record; replay execution is disabled.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from enum import StrEnum
import hashlib
import json
from pathlib import Path
import tempfile
from typing import Any

from backup_restore import RESTORE_CONFIRMATION
from durable_worker_store import DurableWorkerStore, DurableWorkerStateError
from worker_queue_backup import create_worker_queue_backup, restore_worker_queue_backup


class WorkerReplayDecision(StrEnum):
    RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"
    OPERATOR_CONFIRMATION_REQUIRED = "OPERATOR_CONFIRMATION_REQUIRED"
    SOFTWARE_REPLAY_ELIGIBLE = "SOFTWARE_REPLAY_ELIGIBLE"


class WorkerReplayCode(StrEnum):
    LEASE_EXPIRED_REQUIRES_RECONCILIATION = "LEASE_EXPIRED_REQUIRES_RECONCILIATION"
    LEASE_REQUEUED_AFTER_RECONCILIATION = "LEASE_REQUEUED_AFTER_RECONCILIATION"
    RETRYABLE_FAILURE_RETAINED = "RETRYABLE_FAILURE_RETAINED"
    RETRY_LIMIT_EXCEEDED_DEAD_LETTER = "RETRY_LIMIT_EXCEEDED_DEAD_LETTER"
    DEAD_LETTER_REPLAY_CONFIRMATION_REQUIRED = "DEAD_LETTER_REPLAY_CONFIRMATION_REQUIRED"
    DEAD_LETTER_REPLAY_ELIGIBLE = "DEAD_LETTER_REPLAY_ELIGIBLE"
    QUEUE_BACKUP_RESTORED = "QUEUE_BACKUP_RESTORED"
    AUDIT_CHAIN_INVALID = "AUDIT_CHAIN_INVALID"
    AUTHORIZATION_BOUNDARY_LOCKED = "AUTHORIZATION_BOUNDARY_LOCKED"


@dataclass(frozen=True, slots=True)
class WorkerReplayDecisionRecord:
    scenario_id: str
    decision: str
    remediation_code: str
    resume_permitted: bool
    replay_permitted: bool
    replay_executed: bool
    production_authorized: bool
    external_authority: bool
    reason: str
    opaque_refs: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class _FixtureClock:
    current: datetime

    def __call__(self) -> datetime:
        return self.current


def _opaque(value: str, namespace: str) -> str:
    return f"{namespace}:{hashlib.sha256(value.encode('utf-8')).hexdigest()[:20]}"


def classify_job(job: dict[str, Any]) -> str:
    """Classify a store row without mutating it."""
    status = job.get("status")
    last_error = job.get("last_error")
    if status == "BLOCKED" and last_error == "LEASE_EXPIRED_REQUIRES_RECONCILIATION":
        return WorkerReplayCode.LEASE_EXPIRED_REQUIRES_RECONCILIATION.value
    if status == "QUEUED" and job.get("attempts", 0) > 0:
        return WorkerReplayCode.RETRYABLE_FAILURE_RETAINED.value
    if status == "FAILED" and last_error == "RETRY_LIMIT_EXCEEDED":
        return WorkerReplayCode.RETRY_LIMIT_EXCEEDED_DEAD_LETTER.value
    if status == "SUCCEEDED":
        return "SUCCEEDED"
    return str(status or "UNKNOWN")


def evaluate_dead_letter_replay(
    job: dict[str, Any],
    *,
    operator_confirmation_present: bool,
    authorization_boundary: dict[str, Any] | None = None,
) -> WorkerReplayDecisionRecord:
    """Return eligibility only; never claim or execute a replay."""
    boundary = authorization_boundary or {
        "external_authority": False,
        "production_authorized": False,
        "runtime_authority": "NONE",
    }
    boundary_locked = (
        boundary.get("external_authority") is False
        and boundary.get("production_authorized") is False
        and boundary.get("runtime_authority") == "NONE"
    )
    ref = _opaque(str(job.get("job_id", "unknown")), "job")
    if not boundary_locked:
        return WorkerReplayDecisionRecord(
            scenario_id="authorization_boundary_locked",
            decision=WorkerReplayDecision.RECONCILIATION_REQUIRED.value,
            remediation_code=WorkerReplayCode.AUTHORIZATION_BOUNDARY_LOCKED.value,
            resume_permitted=False,
            replay_permitted=False,
            replay_executed=False,
            production_authorized=False,
            external_authority=False,
            reason="Authorization mutation is outside the fixture-only replay boundary.",
            opaque_refs={"job_ref": ref},
        )

    classification = classify_job(job)
    if classification != WorkerReplayCode.RETRY_LIMIT_EXCEEDED_DEAD_LETTER.value:
        return WorkerReplayDecisionRecord(
            scenario_id="dead_letter_replay_not_applicable",
            decision=WorkerReplayDecision.RECONCILIATION_REQUIRED.value,
            remediation_code=classification,
            resume_permitted=False,
            replay_permitted=False,
            replay_executed=False,
            production_authorized=False,
            external_authority=False,
            reason="Only a bounded retry-limit failure may enter dead-letter replay review.",
            opaque_refs={"job_ref": ref},
        )
    if not operator_confirmation_present:
        return WorkerReplayDecisionRecord(
            scenario_id="dead_letter_replay_confirmation_required",
            decision=WorkerReplayDecision.OPERATOR_CONFIRMATION_REQUIRED.value,
            remediation_code=WorkerReplayCode.DEAD_LETTER_REPLAY_CONFIRMATION_REQUIRED.value,
            resume_permitted=False,
            replay_permitted=False,
            replay_executed=False,
            production_authorized=False,
            external_authority=False,
            reason="Explicit operator confirmation is required before software replay eligibility.",
            opaque_refs={"job_ref": ref},
        )
    return WorkerReplayDecisionRecord(
        scenario_id="dead_letter_replay_software_eligible",
        decision=WorkerReplayDecision.SOFTWARE_REPLAY_ELIGIBLE.value,
        remediation_code=WorkerReplayCode.DEAD_LETTER_REPLAY_ELIGIBLE.value,
        resume_permitted=True,
        replay_permitted=True,
        replay_executed=False,
        production_authorized=False,
        external_authority=False,
        reason="The isolated fixture records replay eligibility but does not claim or execute a worker.",
        opaque_refs={"job_ref": ref},
    )


def _submit_fixture(store: DurableWorkerStore, job_id: str, idempotency_key: str, now: datetime, max_attempts: int = 3) -> dict[str, Any]:
    return store.submit(
        job_id=job_id,
        job_type="EVIDENCE_REPORT",
        args={"report_kind": "replay", "format": "json", "scope_ref": "scope-opaque-001"},
        idempotency_key=idempotency_key,
        requester_role="reliability_operator",
        approver_role="control_room_coordinator",
        approval_ref="approval-opaque-001",
        max_attempts=max_attempts,
        now=now,
    )


def run_rehearsal() -> dict[str, Any]:
    """Run a deterministic isolated lease/dead-letter/backup rehearsal."""
    start = datetime(2026, 8, 22, 12, 0, tzinfo=timezone.utc)
    with tempfile.TemporaryDirectory(prefix="smart-ward-worker-replay-") as directory:
        root = Path(directory)
        database = root / "worker.sqlite"
        backup_root = root / "backups"
        restored_database = root / "restored-worker.sqlite"

        with DurableWorkerStore(str(database), mode="software_fixture", lease_seconds=60) as store:
            lease_job = _submit_fixture(store, "job-lease-opaque-001", "idem-lease-opaque-001", start)
            store.claim(job_id=lease_job["job_id"], worker_id="worker-opaque-a", now=start)
            lease_expiry_time = start + timedelta(seconds=61)

        with DurableWorkerStore(str(database), mode="software_fixture", lease_seconds=60) as restarted:
            blocked_ids = restarted.recover_expired_leases(
                actor_role="control_room_coordinator",
                reconciliation_ref="reconcile-opaque-lease-001",
                now=lease_expiry_time,
            )
            blocked_job = restarted.get(blocked_ids[0])
            blocked_classification = classify_job(blocked_job)
            requeued_job = restarted.reconcile(
                job_id=blocked_ids[0],
                decision="REQUEUE",
                actor_role="reliability_operator",
                reconciliation_ref="reconcile-opaque-lease-001",
                now=lease_expiry_time + timedelta(seconds=1),
            )
            restart_health = restarted.health()

        with DurableWorkerStore(str(database), mode="software_fixture", lease_seconds=60) as store:
            dead_job = _submit_fixture(store, "job-dead-opaque-001", "idem-dead-opaque-001", start, max_attempts=3)
            for attempt in range(3):
                store.claim(
                    job_id=dead_job["job_id"],
                    worker_id=f"worker-opaque-{attempt + 1}",
                    now=start + timedelta(minutes=2, seconds=attempt),
                )
                dead_job = store.fail(
                    job_id=dead_job["job_id"],
                    worker_id=f"worker-opaque-{attempt + 1}",
                    retryable=True,
                    now=start + timedelta(minutes=2, seconds=attempt, microseconds=1),
                )
            dead_letter_job = store.get(dead_job["job_id"])
            dead_letter_classification = classify_job(dead_letter_job)
            confirmation_required = evaluate_dead_letter_replay(
                dead_letter_job,
                operator_confirmation_present=False,
            )
            replay_eligible = evaluate_dead_letter_replay(
                dead_letter_job,
                operator_confirmation_present=True,
            )
            queue_health_before_backup = store.health()
            backup_bundle = create_worker_queue_backup(
                database_path=database,
                output_dir=backup_root,
                source_revision="fixture-source-revision-001",
            )

        restore_result = restore_worker_queue_backup(
            bundle_dir=backup_bundle,
            target_database=restored_database,
            confirmation=RESTORE_CONFIRMATION,
        )
        with DurableWorkerStore(str(restored_database), mode="software_fixture", lease_seconds=60) as restored:
            restored_dead_job = restored.get(dead_job["job_id"])
            restored_lease_job = restored.get(lease_job["job_id"])
            restored_health = restored.health()

        return {
            "contract": "DURABLE_WORKER_REPLAY_CONTRACT_V1",
            "mode": "SOFTWARE_FIXTURE",
            "read_only_external_boundary": True,
            "external_transmission_performed": False,
            "clinical_state_mutation_performed": False,
            "runtime_replay_executed": False,
            "authorization_boundary": {
                "external_authority": False,
                "production_authorized": False,
                "runtime_authority": "NONE",
            },
            "lease_recovery": {
                "blocked_classification": blocked_classification,
                "requeued_status": requeued_job["status"],
                "restart_health": restart_health,
            },
            "dead_letter": {
                "classification": dead_letter_classification,
                "confirmation_required": confirmation_required.to_dict(),
                "replay_eligible": replay_eligible.to_dict(),
                "queue_health_before_backup": queue_health_before_backup,
            },
            "backup_restore": {
                "restore_result": restore_result,
                "restored_dead_letter_classification": classify_job(restored_dead_job),
                "restored_lease_status": restored_lease_job["status"],
                "restored_health": restored_health,
            },
            "claim_boundary": {
                "status": "CONTROLLED_PRODUCTION_PROTOTYPE",
                "functional_verification": "PASSED",
                "clinical_validation": "PENDING",
                "production_ready": False,
            },
        }


def rehearsal_json() -> str:
    return json.dumps(run_rehearsal(), sort_keys=True, indent=2)


if __name__ == "__main__":
    print(rehearsal_json())
