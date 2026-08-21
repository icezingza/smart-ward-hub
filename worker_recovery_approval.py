"""Operator approval/read-back contract for worker recovery evidence.

This contract validates a software-rehearsal approval record against a
redacted worker recovery transcript. It never authorizes production, clinical,
external, or runtime replay and never executes a worker.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import re
from typing import Any, Mapping

from worker_recovery_transcript import build_worker_recovery_transcript


SCHEMA_VERSION = "smart-ward-worker-recovery-approval-v1"
READBACK_CONFIRMATION = "I_UNDERSTAND_SOFTWARE_REHEARSAL_RESUME"
TEMPLATE_STATUS = "READBACK_REQUIRED"
APPROVED_STATUS = "APPROVED_FOR_SOFTWARE_REHEARSAL"
REJECTED_STATUS = "REJECTED_BOUNDARY"
AUTHORIZATION_BOUNDARY = {
    "external_authority": "NONE",
    "clinical_validation_authorized": False,
    "production_authorized": False,
    "runtime_authority": "NONE",
    "pilot_gate_status": "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION",
}
REQUESTER_ROLES = {"reliability_operator", "control_room_coordinator"}
APPROVER_ROLES = {"control_room_coordinator", "security_auditor"}
READBACK_ROLES = {"security_auditor", "control_room_coordinator"}
OPAQUE_REF = re.compile(r"^[A-Za-z][A-Za-z0-9._:-]{2,127}$")
HEX64 = re.compile(r"^[a-f0-9]{64}$")
RAW_MARKER = re.compile(
    r"(?i)(hn[-_]?\d|an[-_]?\d|mrn|patient[_-]?(?:id|token|name)|hospital[_-]?number|@|-----BEGIN|private[_-]?key|secret|password|api[_-]?key)"
)


class ApprovalValidationError(ValueError):
    """Raised when an approval/read-back record fails closed."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ApprovalValidationError(message)


def _ref(value: Any, field: str) -> str:
    _require(isinstance(value, str) and OPAQUE_REF.fullmatch(value) is not None, f"{field}_must_be_opaque")
    _require(RAW_MARKER.search(value) is None, f"{field}_contains_unsafe_marker")
    return value


def _sha(value: Any, field: str) -> str:
    _require(isinstance(value, str) and HEX64.fullmatch(value) is not None, f"{field}_must_be_sha256")
    return value


def _utc(value: Any, field: str) -> str:
    _require(isinstance(value, str), f"{field}_must_be_timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ApprovalValidationError(f"{field}_invalid") from exc
    _require(parsed.tzinfo is not None and parsed.utcoffset() is not None, f"{field}_must_be_timezone_aware")
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _safe_text(value: Any, field: str, max_length: int = 512) -> str:
    _require(isinstance(value, str) and value.strip() and len(value) <= max_length, f"{field}_invalid")
    _require(RAW_MARKER.search(value) is None, f"{field}_contains_unsafe_marker")
    return value


def transcript_sha256(transcript: list[dict[str, Any]]) -> str:
    _require(isinstance(transcript, list) and transcript, "transcript_required")
    encoded = json.dumps(transcript, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def queue_binding_sha256(last_event_details: Mapping[str, Any]) -> str:
    _require(isinstance(last_event_details, Mapping), "queue_binding_details_required")
    encoded = json.dumps(dict(last_event_details), sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _exact_keys(payload: Mapping[str, Any], expected: set[str]) -> None:
    unknown = sorted(set(payload) - expected)
    missing = sorted(expected - set(payload))
    _require(not unknown and not missing, f"payload_fields_mismatch:unknown={unknown},missing={missing}")


def approval_template() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "approval_id": "PENDING_EXTERNAL_APPOINTMENT",
        "transcript_ref": "PENDING_EXTERNAL_APPOINTMENT",
        "transcript_sha256": "0" * 64,
        "queue_backup_ref": "PENDING_EXTERNAL_APPOINTMENT",
        "queue_binding_sha256": "0" * 64,
        "reconciliation_ref": "PENDING_EXTERNAL_APPOINTMENT",
        "requester_role": "PENDING_EXTERNAL_APPOINTMENT",
        "approver_role": "PENDING_EXTERNAL_APPOINTMENT",
        "readback_role": "PENDING_EXTERNAL_APPOINTMENT",
        "approval_timestamp_utc": "PENDING_EXTERNAL_APPOINTMENT",
        "readback_timestamp_utc": "PENDING_EXTERNAL_APPOINTMENT",
        "approval_summary": "PENDING_EXTERNAL_APPOINTMENT",
        "approval_confirmation": "PENDING_EXTERNAL_APPOINTMENT",
        "readback_confirmation": "PENDING_EXTERNAL_APPOINTMENT",
        "decision": TEMPLATE_STATUS,
        "scope": "SOFTWARE_REHEARSAL_ONLY",
        "replay_execution_requested": False,
        "replay_executed": False,
        "authorization_boundary": deepcopy(AUTHORIZATION_BOUNDARY),
        "external_execution_authorized": False,
        "production_authorized": False,
        "clinical_validation_authorized": False,
        "evidence_class": "LOCAL_TEMPLATE",
    }


def _validate_boundary(payload: Mapping[str, Any]) -> None:
    _require(payload.get("authorization_boundary") == AUTHORIZATION_BOUNDARY, "authorization_boundary_mutated")
    _require(payload.get("external_execution_authorized") is False, "external_execution_authorized_mutated")
    _require(payload.get("production_authorized") is False, "production_authorized_mutated")
    _require(payload.get("clinical_validation_authorized") is False, "clinical_validation_authorized_mutated")
    _require(payload.get("scope") == "SOFTWARE_REHEARSAL_ONLY", "scope_must_be_software_only")
    _require(payload.get("replay_execution_requested") is False, "replay_execution_request_forbidden")
    _require(payload.get("replay_executed") is False, "replay_execution_forbidden")


def validate_readback(payload: Mapping[str, Any], transcript_report: Mapping[str, Any]) -> dict[str, Any]:
    """Validate an approval/read-back record against a transcript report."""
    _require(isinstance(payload, Mapping), "payload_must_be_object")
    expected_keys = set(approval_template())
    _exact_keys(payload, expected_keys)
    _require(payload.get("schema_version") == SCHEMA_VERSION, "schema_version_mismatch")
    _validate_boundary(payload)
    transcript = transcript_report.get("transcript")
    _require(transcript_report.get("transcript_integrity_valid") is True, "transcript_integrity_required")
    expected_transcript_sha = transcript_sha256(transcript)
    _require(payload.get("transcript_sha256") == expected_transcript_sha, "transcript_binding_mismatch")
    _sha(payload.get("transcript_sha256"), "transcript_sha256")
    _sha(payload.get("queue_binding_sha256"), "queue_binding_sha256")
    _require(isinstance(transcript, list) and transcript, "transcript_required")
    last_event = transcript[-1]
    _require(last_event.get("event_type") == "QUEUE_BACKUP_BINDING_VERIFIED", "queue_binding_event_required")
    last_details = last_event.get("details")
    _require(isinstance(last_details, Mapping), "queue_binding_details_required")
    _require(payload.get("queue_backup_ref") == last_details.get("backup_ref"), "queue_backup_ref_mismatch")
    _require(payload.get("queue_binding_sha256") == queue_binding_sha256(last_details), "queue_binding_mismatch")
    for field in ("approval_id", "transcript_ref", "queue_backup_ref", "reconciliation_ref"):
        _ref(payload.get(field), field)
    for field in ("requester_role", "approver_role", "readback_role"):
        _require(isinstance(payload.get(field), str) and not RAW_MARKER.search(payload[field]), f"{field}_invalid")
    requester = payload["requester_role"]
    approver = payload["approver_role"]
    readback = payload["readback_role"]
    _require(requester in REQUESTER_ROLES, "requester_role_not_allowlisted")
    _require(approver in APPROVER_ROLES, "approver_role_not_allowlisted")
    _require(readback in READBACK_ROLES, "readback_role_not_allowlisted")
    _require(len({requester, approver, readback}) == 3, "actor_separation_required")
    approval_time = _utc(payload.get("approval_timestamp_utc"), "approval_timestamp_utc")
    readback_time = _utc(payload.get("readback_timestamp_utc"), "readback_timestamp_utc")
    _require(approval_time <= readback_time, "readback_must_follow_approval")
    _safe_text(payload.get("approval_summary"), "approval_summary")
    _require(payload.get("approval_confirmation") == READBACK_CONFIRMATION, "approval_confirmation_required")
    _require(payload.get("readback_confirmation") == READBACK_CONFIRMATION, "readback_confirmation_required")
    _require(payload.get("decision") in {TEMPLATE_STATUS, APPROVED_STATUS, REJECTED_STATUS}, "decision_not_allowlisted")
    if payload["decision"] == APPROVED_STATUS:
        _require(payload["evidence_class"] == "LOCAL_SOFTWARE_SIMULATION", "approved_evidence_class_invalid")
    else:
        _require(payload["evidence_class"] in {"LOCAL_TEMPLATE", "LOCAL_SOFTWARE_SIMULATION"}, "evidence_class_invalid")
    _require(payload.get("transcript_ref") == transcript_report.get("correlation_ref"), "transcript_ref_mismatch")
    return {
        "valid": True,
        "decision": payload["decision"],
        "software_rehearsal_only": True,
        "replay_execution_requested": False,
        "replay_executed": False,
        "actor_separation_valid": True,
        "transcript_binding_valid": True,
        "queue_binding_format_valid": True,
        "authorization_promoted": False,
        "external_execution_authorized": False,
        "production_authorized": False,
        "clinical_validation_authorized": False,
        "authorization_boundary": deepcopy(AUTHORIZATION_BOUNDARY),
    }


def build_approval_readback() -> dict[str, Any]:
    """Build a deterministic, non-authorizing approval/read-back snapshot."""
    transcript_report = build_worker_recovery_transcript()
    transcript = transcript_report["transcript"]
    last_details = transcript[-1]["details"]
    payload = approval_template()
    payload.update(
        {
            "approval_id": "approval:worker-recovery-001",
            "transcript_ref": transcript_report["correlation_ref"],
            "transcript_sha256": transcript_sha256(transcript),
            "queue_backup_ref": last_details["backup_ref"],
            "queue_binding_sha256": queue_binding_sha256(last_details),
            "reconciliation_ref": transcript[0]["details"]["reconciliation_ref"],
            "requester_role": "reliability_operator",
            "approver_role": "control_room_coordinator",
            "readback_role": "security_auditor",
            "approval_timestamp_utc": "2026-08-22T00:00:05Z",
            "readback_timestamp_utc": "2026-08-22T00:00:10Z",
            "approval_summary": "Approve software rehearsal evidence read-back only; do not execute replay or production resume.",
            "approval_confirmation": READBACK_CONFIRMATION,
            "readback_confirmation": READBACK_CONFIRMATION,
            "decision": APPROVED_STATUS,
            "evidence_class": "LOCAL_SOFTWARE_SIMULATION",
        }
    )
    validation = validate_readback(payload, transcript_report)
    return {
        "schema_version": SCHEMA_VERSION,
        "approval": payload,
        "validation": validation,
        "transcript_integrity_valid": transcript_report["transcript_integrity_valid"],
        "read_only": True,
        "replay_executed": False,
        "production_authorized": False,
        "clinical_validation_authorized": False,
        "external_authority": "NONE",
        "runtime_authority": "NONE",
        "pilot_gate_status": "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION",
        "claim_boundary": {
            "status": "CONTROLLED_PRODUCTION_PROTOTYPE",
            "functional_verification": "PASSED",
            "clinical_validation": "PENDING",
            "production_ready": False,
        },
    }


if __name__ == "__main__":
    print(json.dumps(build_approval_readback(), sort_keys=True, indent=2))
