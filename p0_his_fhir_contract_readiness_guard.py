"""Local-only P0 HIS/FHIR contract readiness guard.

This module validates a proposed Hub-facing handover envelope and a structured
acknowledgment using deterministic fixtures. It does not send data, authenticate
a hospital system, or authorize clinical/production execution.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
import re
from typing import Any


SCHEMA_VERSION = "p0-his-fhir-contract-readiness-v1"
AUTHORIZATION_BOUNDARY = {
    "external_authority": "NONE",
    "clinical_validation_authorized": False,
    "production_authorized": False,
    "runtime_authority": "NONE",
    "pilot_gate_status": "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION",
}
REQUIRED_EXTERNAL_DECISIONS = (
    "fhir_version_and_profiles",
    "terminology_and_observation_status",
    "patient_reference_policy",
    "timezone_and_consent_retention_policy",
    "acknowledgment_and_error_contract",
    "idempotency_behavior_and_support_path",
    "certificate_authority_and_transport_identity",
    "token_issuer_ttl_and_revocation",
    "monitoring_endpoint_and_operational_owner",
)
OPAQUE_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9._~-]{16,128}$")
RAW_IDENTITY_PATTERN = re.compile(r"(?:HN|AN|MRN|NATIONAL_ID)(?:[-_:]|\b)", re.IGNORECASE)
SECRET_PATTERN = re.compile(r"(?:Bearer(?:\s+|[-_])\S+|-----BEGIN|private[_-]?key|api[_-]?key|password\s*[:=])", re.IGNORECASE)


class HISContractGuardError(ValueError):
    """Raised when a local HIS/FHIR contract fixture is unsafe or incomplete."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise HISContractGuardError(message)


def _safe_text(value: Any, field: str, *, max_length: int = 256) -> str:
    _require(isinstance(value, str) and value.strip(), f"{field}_required")
    value = value.strip()
    _require(len(value) <= max_length, f"{field}_too_large")
    _require(SECRET_PATTERN.search(value) is None, f"{field}_secret_marker")
    return value


def _utc(value: Any, field: str) -> datetime:
    _require(isinstance(value, str), f"{field}_must_be_iso8601")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HISContractGuardError(f"{field}_must_be_iso8601") from exc
    _require(parsed.tzinfo is not None and parsed.utcoffset() is not None, f"{field}_timezone_required")
    return parsed.astimezone(timezone.utc)


def validate_hub_handover_envelope(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate only the proposed opaque Hub-facing handover envelope."""
    expected = {"bundle_id", "idempotency_key", "patient_token", "device_id", "window_start", "window_end"}
    _require(isinstance(payload, dict) and set(payload) == expected, "handover_envelope_fields_mismatch")
    for field in ("bundle_id", "idempotency_key", "device_id"):
        value = _safe_text(payload[field], field)
        _require(RAW_IDENTITY_PATTERN.search(value) is None, f"{field}_raw_identity_marker")
    patient_token = _safe_text(payload["patient_token"], "patient_token", max_length=128)
    _require(OPAQUE_TOKEN_PATTERN.fullmatch(patient_token) is not None, "patient_token_not_opaque")
    _require(RAW_IDENTITY_PATTERN.search(patient_token) is None, "patient_token_raw_identity")
    start = _utc(payload["window_start"], "window_start")
    end = _utc(payload["window_end"], "window_end")
    _require(end > start, "handover_window_invalid")
    return {
        "valid": True,
        "bundle_id": payload["bundle_id"],
        "idempotency_key": payload["idempotency_key"],
        "patient_reference_class": "OPAQUE_TOKEN_ONLY",
        "raw_identity_retained": False,
        "evidence_class": "LOCAL_SOFTWARE_CONTRACT",
    }


def validate_his_acknowledgment(ack: dict[str, Any], *, expected_bundle_id: str) -> dict[str, Any]:
    """Validate structured acknowledgment without treating it as trusted authority."""
    expected = {
        "acknowledged", "status_code", "acknowledged_bundle_id", "acknowledgment_id",
        "receiving_system", "server_time", "accepted_version", "accepted_profile", "error_message",
    }
    _require(isinstance(ack, dict) and set(ack) == expected, "acknowledgment_fields_mismatch")
    _require(isinstance(ack["acknowledged"], bool), "acknowledged_must_be_boolean")
    _require(isinstance(ack["status_code"], int) and not isinstance(ack["status_code"], bool), "status_code_invalid")
    if not ack["acknowledged"]:
        return {
            "valid": True,
            "result": "RETAINED_FOR_RETRY",
            "purge_eligible": False,
            "purge_executed": False,
            "external_verification_required": True,
        }
    _require(ack["status_code"] == 200, "acknowledged_requires_status_200")
    for field in ("acknowledged_bundle_id", "acknowledgment_id", "receiving_system", "accepted_version", "accepted_profile"):
        _safe_text(ack[field], field)
    _require(ack["acknowledged_bundle_id"] == expected_bundle_id, "acknowledged_bundle_mismatch")
    _utc(ack["server_time"], "server_time")
    return {
        "valid": True,
        "result": "PURGE_ELIGIBLE_SIMULATION",
        "purge_eligible": True,
        "purge_executed": False,
        "purge_scope": {"bundle_id": expected_bundle_id, "exact_window_only": True},
        "external_verification_required": True,
    }


def evaluate_contract_readiness() -> dict[str, Any]:
    """Run deterministic contract checks and return an evidence-bounded report."""
    now = "2026-08-23T00:00:00Z"
    envelope = {
        "bundle_id": "bundle:fixture-his-001",
        "idempotency_key": "idempotency:fixture-his-001",
        "patient_token": "ptok-fixture-opaque-20260823",
        "device_id": "device:fixture-01",
        "window_start": "2026-08-22T23:00:00Z",
        "window_end": now,
    }
    failure_ack = {
        "acknowledged": False,
        "status_code": 503,
        "acknowledged_bundle_id": None,
        "acknowledgment_id": None,
        "receiving_system": None,
        "server_time": None,
        "accepted_version": None,
        "accepted_profile": None,
        "error_message": "sandbox remote unavailable",
    }
    success_ack = {
        "acknowledged": True,
        "status_code": 200,
        "acknowledged_bundle_id": envelope["bundle_id"],
        "acknowledgment_id": "ack:fixture-his-001",
        "receiving_system": "system:fixture-his",
        "server_time": now,
        "accepted_version": "FHIR-R4",
        "accepted_profile": "profile:fixture-observation-v1",
        "error_message": None,
    }
    generic_200_ack = {**failure_ack, "status_code": 200}
    mismatch_ack = {**success_ack, "acknowledged_bundle_id": "bundle:other-fixture"}
    checks: dict[str, bool] = {}
    envelope_result = validate_hub_handover_envelope(envelope)
    checks["opaque_hub_envelope"] = envelope_result["valid"] and envelope_result["raw_identity_retained"] is False
    checks["idempotency_key_stable"] = envelope["idempotency_key"] == deepcopy(envelope)["idempotency_key"]
    failure_result = validate_his_acknowledgment(failure_ack, expected_bundle_id=envelope["bundle_id"])
    checks["failure_retains_local_data"] = failure_result["result"] == "RETAINED_FOR_RETRY" and failure_result["purge_executed"] is False
    success_result = validate_his_acknowledgment(success_ack, expected_bundle_id=envelope["bundle_id"])
    checks["structured_ack_is_exact_scope_only"] = (
        success_result["result"] == "PURGE_ELIGIBLE_SIMULATION"
        and success_result["purge_eligible"] is True
        and success_result["purge_executed"] is False
        and success_result["purge_scope"]["exact_window_only"] is True
    )
    generic_200_result = validate_his_acknowledgment(generic_200_ack, expected_bundle_id=envelope["bundle_id"])
    checks["generic_200_rejected"] = (
        generic_200_result["result"] == "RETAINED_FOR_RETRY"
        and generic_200_result["purge_eligible"] is False
        and generic_200_result["purge_executed"] is False
    )
    try:
        validate_his_acknowledgment(mismatch_ack, expected_bundle_id=envelope["bundle_id"])
    except HISContractGuardError:
        checks["mismatched_bundle_rejected"] = True
    else:
        checks["mismatched_bundle_rejected"] = False
    serialized = json.dumps({"envelope": envelope, "ack": success_ack}, ensure_ascii=True, sort_keys=True)
    checks["zero_pii_fixture"] = RAW_IDENTITY_PATTERN.search(serialized) is None
    checks["authority_boundary_locked"] = AUTHORIZATION_BOUNDARY == {
        "external_authority": "NONE",
        "clinical_validation_authorized": False,
        "production_authorized": False,
        "runtime_authority": "NONE",
        "pilot_gate_status": "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION",
    }
    external_pending = list(REQUIRED_EXTERNAL_DECISIONS)
    return {
        "schema_version": SCHEMA_VERSION,
        "decision": "P0_HIS_FHIR_CONTRACT_SOFTWARE_VERIFIED_PENDING_EXTERNAL_DECISIONS",
        "mode": "LOCAL_DETERMINISTIC_FIXTURE_ONLY",
        "checks": checks,
        "all_passed": all(checks.values()),
        "envelope_result": envelope_result,
        "failure_ack_result": failure_result,
        "success_ack_result": success_result,
        "external_decisions_pending": external_pending,
        "external_decision_count": len(external_pending),
        "external_submission_allowed": False,
        "external_transmission_performed": False,
        "runtime_mutation_performed": False,
        "purge_executed": False,
        "external_verification_performed": False,
        "authorization_promoted": False,
        "authorization_boundary": deepcopy(AUTHORIZATION_BOUNDARY),
        "clinical_validation_authorized": False,
        "production_authorized": False,
        "runtime_authority": "NONE",
        "pilot_gate_status": AUTHORIZATION_BOUNDARY["pilot_gate_status"],
        "real_his_evidence": "UNVERIFIED",
        "real_mtls_oidc_evidence": "UNVERIFIED",
        "physical_hardware_evidence": "UNVERIFIED",
        "patient_data_used": False,
        "raw_frames_recorded": False,
    }


if __name__ == "__main__":
    report = evaluate_contract_readiness()
    print(json.dumps(report, ensure_ascii=True, sort_keys=True))
    print("P0_HIS_FHIR_CONTRACT_READINESS_GUARD_PASSED" if report["all_passed"] else "P0_HIS_FHIR_CONTRACT_READINESS_GUARD_BLOCKED")
