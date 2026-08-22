"""Read-only consistency gate for the P2-005 worker-control evidence chain."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from typing import Any

from cross_package_evidence_binding import check_repository
from durable_worker_replay_contract import run_rehearsal
from worker_control_plane import WorkerControlPlane
from worker_recovery_approval import build_approval_readback
from worker_recovery_transcript import build_worker_recovery_transcript


ROOT = Path(__file__).resolve().parent
FREEZE_PATH = Path("evals/micro_rag/evidence/release-candidate-freeze-20260820.json")
EXPECTED_BOUNDARY = {
    "external_authority": "NONE",
    "clinical_validation_authorized": False,
    "production_authorized": False,
    "runtime_authority": "NONE",
    "pilot_gate_status": "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION",
}
FORBIDDEN_MARKERS = (
    "HN-",
    "AN-",
    "MRN",
    "patient_id",
    "patient_token",
    "patient_name",
    "private key",
    "bearer ",
    "password",
    "api_key",
    "@",
)


class WorkerConsistencyError(ValueError):
    """Raised when a worker consistency input cannot be evaluated safely."""


class FixedClock:
    def __init__(self) -> None:
        self.value = datetime(2026, 8, 22, 12, 0, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.value

    def advance(self, seconds: int) -> None:
        self.value += timedelta(seconds=seconds)


def _in_process_rehearsal() -> dict[str, Any]:
    clock = FixedClock()
    plane = WorkerControlPlane(
        handlers={
            "backup.report": lambda args: {"report_kind": args.get("report_kind", "summary"), "scope_ref": args.get("scope_ref", "none")},
            "evidence.report": lambda args: {"report_kind": args.get("report_kind", "summary"), "scope_ref": args.get("scope_ref", "none")},
        },
        lease_seconds=10,
        clock=clock,
    )
    submitted = plane.submit(
        job_id="job-consistency-success-001",
        job_type="BACKUP_REPORT",
        args={"report_kind": "daily", "format": "json", "scope_ref": "ward-04"},
        idempotency_key="idem-consistency-success-001",
        requester_role="reliability_operator",
        approver_role="security_auditor",
        approval_ref="approval-consistency-001",
        max_attempts=3,
        now=clock(),
    )
    replay = plane.submit(
        job_id="job-consistency-success-001",
        job_type="BACKUP_REPORT",
        args={"report_kind": "daily", "format": "json", "scope_ref": "ward-04"},
        idempotency_key="idem-consistency-success-001",
        requester_role="reliability_operator",
        approver_role="security_auditor",
        approval_ref="approval-consistency-001",
        max_attempts=3,
        now=clock(),
    )
    succeeded = plane.run_once(job_id=submitted["job_id"], worker_id="worker-consistency-001", now=clock())

    stale_clock = FixedClock()
    stale_plane = WorkerControlPlane(
        handlers={"backup.report": lambda args: {"ok": True}},
        lease_seconds=10,
        clock=stale_clock,
    )
    stale_plane.submit(
        job_id="job-consistency-stale-001",
        job_type="BACKUP_REPORT",
        args={"report_kind": "daily", "scope_ref": "ward-04"},
        idempotency_key="idem-consistency-stale-001",
        requester_role="reliability_operator",
        approver_role="security_auditor",
        approval_ref="approval-consistency-002",
        now=stale_clock(),
    )
    stale_plane.claim(job_id="job-consistency-stale-001", worker_id="worker-consistency-stale", now=stale_clock())
    stale_clock.advance(11)
    blocked = stale_plane.recover_stale_leases(
        actor_role="control_room_coordinator",
        reconciliation_ref="reconcile-consistency-001",
        now=stale_clock(),
    )
    reconciled = stale_plane.reconcile(
        job_id=blocked[0],
        decision="REQUEUE",
        actor_role="reliability_operator",
        reconciliation_ref="reconcile-consistency-002",
        now=stale_clock(),
    )
    recovered = stale_plane.run_once(job_id=blocked[0], worker_id="worker-consistency-recovered", now=stale_clock())
    return {
        "submitted_status": submitted["status"],
        "idempotent_replay_fingerprint_equal": replay["fingerprint"] == submitted["fingerprint"],
        "success_status": succeeded["status"],
        "success_attempts": succeeded["attempts"],
        "stale_job_blocked": blocked == ["job-consistency-stale-001"],
        "stale_reconciled_status": reconciled["status"],
        "stale_recovered_status": recovered["status"],
        "audit_chain_valid": plane.verify_audit_chain() and stale_plane.verify_audit_chain(),
    }


def evaluate_worker_consistency(*, root: Path = ROOT) -> dict[str, Any]:
    checks: dict[str, bool] = {}
    remediation_codes: list[str] = []

    in_process = _in_process_rehearsal()
    checks["in_process_allowlisted_idempotent_success"] = (
        in_process["submitted_status"] == "QUEUED"
        and in_process["idempotent_replay_fingerprint_equal"] is True
        and in_process["success_status"] == "SUCCEEDED"
        and in_process["success_attempts"] == 1
    )
    if not checks["in_process_allowlisted_idempotent_success"]:
        remediation_codes.append("IN_PROCESS_CONTRACT_MISMATCH")
    checks["in_process_stale_lease_recovery"] = (
        in_process["stale_job_blocked"] is True
        and in_process["stale_reconciled_status"] == "QUEUED"
        and in_process["stale_recovered_status"] == "SUCCEEDED"
        and in_process["audit_chain_valid"] is True
    )
    if not checks["in_process_stale_lease_recovery"]:
        remediation_codes.append("IN_PROCESS_RECOVERY_MISMATCH")

    durable = run_rehearsal()
    checks["durable_fixture_replay_boundary"] = (
        durable.get("contract") == "DURABLE_WORKER_REPLAY_CONTRACT_V1"
        and durable.get("mode") == "SOFTWARE_FIXTURE"
        and durable.get("read_only_external_boundary") is True
        and durable.get("runtime_replay_executed") is False
        and durable.get("external_transmission_performed") is False
        and durable.get("clinical_state_mutation_performed") is False
    )
    if not checks["durable_fixture_replay_boundary"]:
        remediation_codes.append("DURABLE_FIXTURE_BOUNDARY_INVALID")
    checks["durable_lease_and_dead_letter_semantics"] = (
        durable.get("lease_recovery", {}).get("blocked_classification") == "LEASE_EXPIRED_REQUIRES_RECONCILIATION"
        and durable.get("lease_recovery", {}).get("requeued_status") == "QUEUED"
        and durable.get("dead_letter", {}).get("classification") == "RETRY_LIMIT_EXCEEDED_DEAD_LETTER"
        and durable.get("dead_letter", {}).get("confirmation_required", {}).get("replay_permitted") is False
        and durable.get("dead_letter", {}).get("replay_eligible", {}).get("replay_permitted") is True
        and durable.get("dead_letter", {}).get("replay_eligible", {}).get("replay_executed") is False
    )
    if not checks["durable_lease_and_dead_letter_semantics"]:
        remediation_codes.append("DURABLE_REPLAY_SEMANTICS_MISMATCH")
    restored_health = durable.get("backup_restore", {}).get("restored_health", {})
    checks["durable_backup_restore_integrity"] = (
        durable.get("backup_restore", {}).get("restore_result", {}).get("binding_verified") is True
        and durable.get("backup_restore", {}).get("restore_result", {}).get("worker_queue_restore_status") == "SOFTWARE_RESTORE_VERIFIED"
        and durable.get("backup_restore", {}).get("restored_dead_letter_classification") == "RETRY_LIMIT_EXCEEDED_DEAD_LETTER"
        and durable.get("backup_restore", {}).get("restored_lease_status") == "QUEUED"
        and restored_health.get("journal_mode") == "wal"
        and restored_health.get("synchronous") == 2
        and restored_health.get("integrity_check") == "ok"
        and restored_health.get("audit_chain_valid") is True
    )
    if not checks["durable_backup_restore_integrity"]:
        remediation_codes.append("DURABLE_BACKUP_RESTORE_INVALID")

    transcript = build_worker_recovery_transcript()
    checks["transcript_redacted_and_integrity_valid"] = (
        transcript.get("schema_version") == "smart-ward-worker-recovery-transcript-v1"
        and transcript.get("transcript_integrity_valid") is True
        and len(transcript.get("transcript", [])) == 5
        and transcript.get("read_only") is True
        and transcript.get("execution_performed") is False
        and transcript.get("replay_executed") is False
        and transcript.get("raw_worker_identifiers_exported") is False
    )
    if not checks["transcript_redacted_and_integrity_valid"]:
        remediation_codes.append("WORKER_TRANSCRIPT_INVALID")

    approval = build_approval_readback()
    validation = approval.get("validation", {})
    approval_payload = approval.get("approval", {})
    checks["approval_readback_bound_and_separated"] = (
        approval.get("schema_version") == "smart-ward-worker-recovery-approval-v1"
        and validation.get("valid") is True
        and validation.get("actor_separation_valid") is True
        and validation.get("transcript_binding_valid") is True
        and approval_payload.get("requester_role") != approval_payload.get("approver_role")
        and approval_payload.get("approver_role") != approval_payload.get("readback_role")
        and approval.get("read_only") is True
        and approval.get("replay_executed") is False
    )
    if not checks["approval_readback_bound_and_separated"]:
        remediation_codes.append("WORKER_APPROVAL_READBACK_INVALID")

    binding = check_repository(root, verify_revision_ancestry=True)
    checks["cross_package_binding_bound"] = (
        binding.get("decision") == "BOUND"
        and binding.get("remediation_codes") == ["EVIDENCE_PACKAGES_BOUND"]
        and binding.get("read_only") is True
        and binding.get("external_transmission_performed") is False
        and all(value is True for value in binding.get("checks", {}).values())
    )
    if not checks["cross_package_binding_bound"]:
        remediation_codes.append("CROSS_PACKAGE_BINDING_NOT_BOUND")

    child_boundary_values = [
        durable.get("authorization_boundary"),
        transcript,
        approval,
        binding.get("authorization_boundary"),
    ]
    checks["authorization_and_claim_boundary_locked"] = (
        durable.get("authorization_boundary") == {
            "external_authority": False,
            "production_authorized": False,
            "runtime_authority": "NONE",
        }
        and transcript.get("external_authority") == "NONE"
        and transcript.get("production_authorized") is False
        and transcript.get("clinical_validation_authorized") is False
        and approval.get("external_authority") == "NONE"
        and approval.get("production_authorized") is False
        and approval.get("clinical_validation_authorized") is False
        and binding.get("authorization_boundary") == EXPECTED_BOUNDARY
    )
    if not checks["authorization_and_claim_boundary_locked"]:
        remediation_codes.append("WORKER_AUTHORIZATION_BOUNDARY_MUTATED")

    serialized = json.dumps(
        {
            "in_process": in_process,
            "durable": durable,
            "transcript": transcript,
            "approval": approval,
            "binding": binding,
        },
        sort_keys=True,
        ensure_ascii=True,
    ).lower()
    checks["redaction_boundary_clean"] = not any(marker.lower() in serialized for marker in FORBIDDEN_MARKERS)
    if not checks["redaction_boundary_clean"]:
        remediation_codes.append("WORKER_EVIDENCE_REDACTION_FAILED")

    checks["freeze_bound_revision_present"] = (
        isinstance(binding.get("freeze_source_revision"), str)
        and len(binding["freeze_source_revision"]) == 40
        and all(character in "0123456789abcdef" for character in binding["freeze_source_revision"])
        and (root / FREEZE_PATH).is_file()
    )
    if not checks["freeze_bound_revision_present"]:
        remediation_codes.append("WORKER_FREEZE_REVISION_INVALID")

    remediation_codes = sorted(set(remediation_codes))
    decision = "P2_005_WORKER_CONTROL_CONSISTENCY_VERIFIED" if all(checks.values()) else "P2_005_WORKER_CONTROL_CONSISTENCY_BLOCKED"
    return {
        "schema_version": "p2-005-worker-control-consistency-v1",
        "evidence_type": "P2_005_WORKER_CONTROL_CONSISTENCY",
        "decision": decision,
        "checks": checks,
        "remediation_codes": remediation_codes,
        "in_process_summary": in_process,
        "durable_summary": {
            "mode": durable.get("mode"),
            "lease_blocked_classification": durable.get("lease_recovery", {}).get("blocked_classification"),
            "requeued_status": durable.get("lease_recovery", {}).get("requeued_status"),
            "dead_letter_classification": durable.get("dead_letter", {}).get("classification"),
            "replay_confirmation_decision": durable.get("dead_letter", {}).get("confirmation_required", {}).get("decision"),
            "replay_eligible_decision": durable.get("dead_letter", {}).get("replay_eligible", {}).get("decision"),
            "replay_executed": durable.get("runtime_replay_executed"),
            "restore_status": durable.get("backup_restore", {}).get("restore_result", {}).get("worker_queue_restore_status"),
            "journal_mode": restored_health.get("journal_mode"),
            "synchronous": restored_health.get("synchronous"),
        },
        "transcript_event_count": len(transcript.get("transcript", [])),
        "approval_validation_valid": validation.get("valid"),
        "cross_package_binding_decision": binding.get("decision"),
        "freeze_source_revision": binding.get("freeze_source_revision"),
        "external_authority": "NONE",
        "runtime_authority": "NONE",
        "clinical_validation": "PENDING",
        "production_ready": False,
        "hardware_evidence": "UNVERIFIED",
        "read_only": True,
        "runtime_mutation_performed": False,
        "external_transmission_performed": False,
        "external_submission_allowed": False,
        "authorization_promoted": False,
        "claim_boundary": "CONTROLLED_PRODUCTION_PROTOTYPE",
    }


if __name__ == "__main__":
    print(json.dumps(evaluate_worker_consistency(), ensure_ascii=True, indent=2, sort_keys=True))
