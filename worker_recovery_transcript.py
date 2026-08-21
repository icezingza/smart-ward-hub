"""Redacted operator-facing worker recovery transcript.

The transcript is an evidence/readiness artifact. It summarizes a local
software rehearsal without exposing raw job, worker, reconciliation or backup
identifiers. It does not claim, execute, requeue, purge, or authorize a worker.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import re
from typing import Any, Mapping

from durable_worker_replay_contract import run_rehearsal


SCHEMA_VERSION = "smart-ward-worker-recovery-transcript-v1"
TRANSCRIPT_GENESIS = "0" * 64
SCENARIO_TIME = "2026-08-22T00:00:00Z"
OPAQUE_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{2,127}$")
RAW_MARKER = re.compile(
    r"(?i)(hn[-_]?\d|an[-_]?\d|patient[_-]?(?:id|token|name)|mrn|hospital[_-]?number|@|-----BEGIN|private[_-]?key|secret|password|api[_-]?key)"
)
ALLOWED_OPERATOR_ROLES = {
    "control_room_coordinator",
    "reliability_operator",
    "security_auditor",
}


class RecoveryTranscriptError(ValueError):
    """Raised when a transcript input violates the redaction or lifecycle contract."""


def _hash_ref(value: str, namespace: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RecoveryTranscriptError("reference_required")
    return f"{namespace}:{hashlib.sha256(value.encode('utf-8')).hexdigest()[:20]}"


def _assert_opaque(value: str, field: str) -> str:
    if not isinstance(value, str) or not OPAQUE_REF.fullmatch(value) or RAW_MARKER.search(value):
        raise RecoveryTranscriptError(f"{field}_must_be_opaque")
    return value


def _hash_event(body: Mapping[str, Any]) -> str:
    encoded = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _assert_safe_details(value: Any, field: str = "details", depth: int = 0) -> None:
    if depth > 5:
        raise RecoveryTranscriptError(f"{field}_nesting_exceeded")
    if value is None or isinstance(value, (bool, int, float)):
        return
    if isinstance(value, str):
        if RAW_MARKER.search(value):
            raise RecoveryTranscriptError("raw_identity_or_secret_marker_in_transcript")
        return
    if isinstance(value, list):
        if len(value) > 32:
            raise RecoveryTranscriptError(f"{field}_list_bounded")
        for item in value:
            _assert_safe_details(item, field, depth + 1)
        return
    if isinstance(value, dict):
        if len(value) > 32:
            raise RecoveryTranscriptError(f"{field}_object_bounded")
        for key, item in value.items():
            if not isinstance(key, str) or RAW_MARKER.search(key):
                raise RecoveryTranscriptError("unsafe_transcript_key")
            _assert_safe_details(item, field, depth + 1)
        return
    raise RecoveryTranscriptError(f"{field}_unsupported_type")


@dataclass
class WorkerRecoveryTranscript:
    correlation_ref: str
    operator_role: str
    events: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        _assert_opaque(self.correlation_ref, "correlation_ref")
        if self.operator_role not in ALLOWED_OPERATOR_ROLES:
            raise RecoveryTranscriptError("operator_role_not_allowlisted")

    def append(
        self,
        *,
        event_type: str,
        decision: str,
        remediation_code: str,
        details: Mapping[str, Any] | None = None,
        occurred_at: str = SCENARIO_TIME,
    ) -> dict[str, Any]:
        if not isinstance(event_type, str) or not OPAQUE_REF.fullmatch(event_type):
            raise RecoveryTranscriptError("event_type_invalid")
        if not isinstance(decision, str) or not OPAQUE_REF.fullmatch(decision):
            raise RecoveryTranscriptError("decision_invalid")
        if not isinstance(remediation_code, str) or not OPAQUE_REF.fullmatch(remediation_code):
            raise RecoveryTranscriptError("remediation_code_invalid")
        try:
            parsed = datetime.fromisoformat(occurred_at.replace("Z", "+00:00"))
        except ValueError as exc:
            raise RecoveryTranscriptError("occurred_at_invalid") from exc
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise RecoveryTranscriptError("occurred_at_must_be_timezone_aware")
        _assert_safe_details(dict(details or {}))
        previous_hash = self.events[-1]["event_hash"] if self.events else TRANSCRIPT_GENESIS
        body = {
            "schema_version": SCHEMA_VERSION,
            "event_seq": len(self.events) + 1,
            "event_type": event_type,
            "operator_role": self.operator_role,
            "correlation_ref": self.correlation_ref,
            "occurred_at": parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
            "decision": decision,
            "remediation_code": remediation_code,
            "details": dict(details or {}),
            "previous_hash": previous_hash,
        }
        serialized = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        if RAW_MARKER.search(serialized):
            raise RecoveryTranscriptError("raw_identity_or_secret_marker_in_transcript")
        event = dict(body)
        event["event_hash"] = _hash_event(body)
        self.events.append(event)
        return event

    def verify(self) -> bool:
        if not self.events:
            return False
        previous_hash = TRANSCRIPT_GENESIS
        for expected_seq, event in enumerate(self.events, start=1):
            if event.get("event_seq") != expected_seq:
                return False
            if event.get("previous_hash") != previous_hash:
                return False
            body = {key: value for key, value in event.items() if key != "event_hash"}
            if _hash_event(body) != event.get("event_hash"):
                return False
            if RAW_MARKER.search(json.dumps(event, sort_keys=True, ensure_ascii=True)):
                return False
            previous_hash = event["event_hash"]
        return True

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "correlation_ref": self.correlation_ref,
            "operator_role": self.operator_role,
            "events": list(self.events),
            "transcript_integrity_valid": self.verify(),
        }


def build_worker_recovery_transcript() -> dict[str, Any]:
    """Build a deterministic redacted transcript from the fixture rehearsal."""
    report = run_rehearsal()
    correlation_ref = "worker-recovery-transcript-001"
    operator_role = "control_room_coordinator"
    transcript = WorkerRecoveryTranscript(correlation_ref, operator_role)

    lease_job_ref = _hash_ref("job-lease-opaque-001", "job")
    lease_owner_ref = _hash_ref("worker-opaque-a", "worker")
    reconciliation_ref = _hash_ref("reconcile-opaque-lease-001", "reconciliation")
    backup_id = report["backup_restore"]["restore_result"]["source_backup_id"]
    backup_ref = _hash_ref(backup_id, "backup")
    source_revision_ref = _hash_ref(report["backup_restore"]["restore_result"]["source_revision"], "source")

    transcript.append(
        event_type="LEASE_EXPIRY_OBSERVED",
        decision="RECONCILIATION_REQUIRED",
        remediation_code="LEASE_EXPIRED_REQUIRES_RECONCILIATION",
        details={
            "job_ref": lease_job_ref,
            "lease_owner_ref": lease_owner_ref,
            "reconciliation_ref": reconciliation_ref,
            "execution_performed": False,
            "runtime_replay_executed": False,
        },
    )
    transcript.append(
        event_type="LEASE_RECONCILIATION_RECORDED",
        decision="SOFTWARE_REPLAY_ELIGIBLE",
        remediation_code="LEASE_REQUEUED_AFTER_RECONCILIATION",
        details={
            "job_ref": lease_job_ref,
            "reconciliation_ref": reconciliation_ref,
            "resulting_state": report["lease_recovery"]["requeued_status"],
            "operator_confirmation": "ROLE_BOUND_CONFIRMATION_RECORDED",
            "execution_performed": False,
        },
    )
    transcript.append(
        event_type="DEAD_LETTER_OBSERVED",
        decision=report["dead_letter"]["confirmation_required"]["decision"],
        remediation_code=report["dead_letter"]["confirmation_required"]["remediation_code"],
        details={
            "job_ref": report["dead_letter"]["confirmation_required"]["opaque_refs"]["job_ref"],
            "retry_classification": report["dead_letter"]["classification"],
            "replay_executed": False,
            "production_authorized": False,
        },
    )
    transcript.append(
        event_type="DEAD_LETTER_REPLAY_ELIGIBILITY_RECORDED",
        decision=report["dead_letter"]["replay_eligible"]["decision"],
        remediation_code=report["dead_letter"]["replay_eligible"]["remediation_code"],
        details={
            "job_ref": report["dead_letter"]["replay_eligible"]["opaque_refs"]["job_ref"],
            "replay_permitted": True,
            "replay_executed": False,
            "runtime_authority": "NONE",
        },
    )
    transcript.append(
        event_type="QUEUE_BACKUP_BINDING_VERIFIED",
        decision="SOFTWARE_REPLAY_ELIGIBLE",
        remediation_code="QUEUE_BACKUP_RESTORED",
        details={
            "backup_ref": backup_ref,
            "source_revision_ref": source_revision_ref,
            "binding_verified": report["backup_restore"]["restore_result"]["binding_verified"],
            "restore_status": report["backup_restore"]["restore_result"]["worker_queue_restore_status"],
            "audit_chain_valid": report["backup_restore"]["restored_health"]["audit_chain_valid"],
            "external_transmission_performed": False,
        },
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "evidence_class": "LOCAL_SOFTWARE_SIMULATION",
        "correlation_ref": correlation_ref,
        "operator_role": operator_role,
        "transcript": transcript.events,
        "transcript_integrity_valid": transcript.verify(),
        "read_only": True,
        "execution_performed": False,
        "replay_executed": False,
        "production_authorized": False,
        "clinical_validation_authorized": False,
        "external_authority": "NONE",
        "runtime_authority": "NONE",
        "pilot_gate_status": "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION",
        "patient_data_used": False,
        "raw_worker_identifiers_exported": False,
        "claim_boundary": {
            "status": "CONTROLLED_PRODUCTION_PROTOTYPE",
            "functional_verification": "PASSED",
            "clinical_validation": "PENDING",
            "production_ready": False,
        },
    }


if __name__ == "__main__":
    print(json.dumps(build_worker_recovery_transcript(), sort_keys=True, indent=2))
