from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import re
from typing import Any


SCHEMA_VERSION = "wave1-external-evidence-intake-v1"
PROJECT = "smart-ward-hub"
REPOSITORY = "icezingza/smart-ward-hub"
FREEZE_REFERENCE = "TOP_LEVEL_RELEASE_FREEZE"
PENDING = "PENDING_EXTERNAL_APPOINTMENT"
ZERO_SHA256 = "0" * 64

AUTHORIZATION_BOUNDARY = {
    "external_authority": "NONE",
    "clinical_validation_authorized": False,
    "production_authorized": False,
    "runtime_authority": "NONE",
    "pilot_gate_status": "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION",
}

PREREQUISITES: tuple[dict[str, Any], ...] = (
    {"id": "wave0_signed_scope", "track": "WAVE_0_GOVERNANCE", "owner_roles": ["external_coordinator", "clinical_owner"], "required_evidence": "signed scope hash, data boundary, purpose and independent read-back"},
    {"id": "wave0_approved_test_window", "track": "WAVE_0_GOVERNANCE", "owner_roles": ["external_coordinator", "stop_authority"], "required_evidence": "timezone-aware approved window, allowlist and expiry"},
    {"id": "wave0_named_stop_authority", "track": "WAVE_0_GOVERNANCE", "owner_roles": ["stop_authority"], "required_evidence": "appointment, stop-rule and notification/read-back reference"},
    {"id": "wave0_rollback_owner", "track": "WAVE_0_GOVERNANCE", "owner_roles": ["rollback_owner"], "required_evidence": "target revision, owner approval and restore-drill reference"},
    {"id": "wave0_independent_verifier", "track": "WAVE_0_GOVERNANCE", "owner_roles": ["independent_verifier"], "required_evidence": "independent appointment and read-back channel"},
    {"id": "gv04_nonproduction_idp", "track": "GV-04_IDENTITY_TRANSPORT", "owner_roles": ["security_owner", "idp_owner"], "required_evidence": "redacted discovery/JWKS hash, tenant scope and test identity references"},
    {"id": "gv04_certificate_owner", "track": "GV-04_IDENTITY_TRANSPORT", "owner_roles": ["certificate_owner", "security_owner"], "required_evidence": "certificate fingerprints, chain and rotation/revocation transcript"},
    {"id": "gv04_network_acl", "track": "GV-04_IDENTITY_TRANSPORT", "owner_roles": ["network_security_owner"], "required_evidence": "allow and deny transcript for isolated ACL"},
    {"id": "gv08_custody_owner", "track": "GV-08_DEVICE_TRUST", "owner_roles": ["custody_owner", "oem_or_hsm_owner"], "required_evidence": "custody appointment and manufacturer/HSM boundary"},
    {"id": "gv08_dual_control_ceremony", "track": "GV-08_DEVICE_TRUST", "owner_roles": ["custody_owner", "second_approver", "independent_verifier"], "required_evidence": "dual-control ceremony and public-key fingerprint read-back"},
    {"id": "gv08_revocation_distribution", "track": "GV-08_DEVICE_TRUST", "owner_roles": ["custody_owner", "security_owner"], "required_evidence": "revocation/lost-device propagation and recovery transcript"},
    {"id": "gv06_acer_fixture", "track": "GV-06_ACER_BENCH", "owner_roles": ["reliability_owner", "acer_host_operator"], "required_evidence": "dedicated Acer fixture, driver, time source and isolation"},
    {"id": "gv06_loopback_fixture", "track": "GV-06_ACER_BENCH", "owner_roles": ["reliability_owner", "physical_fixture_owner"], "required_evidence": "isolated USB-serial loopback and S-001..S-015 window"},
    {"id": "gv06_operator_confirmation", "track": "GV-06_ACER_BENCH", "owner_roles": ["reliability_owner"], "required_evidence": "I_HAVE_A_NONPRODUCTION_LOOPBACK attestation bound to fixture/window"},
    {"id": "gv06_physical_witness", "track": "GV-06_ACER_BENCH", "owner_roles": ["independent_physical_witness"], "required_evidence": "witnessed physical bench, power/recovery and S-001..S-015 read-back"},
)
PREREQUISITE_IDS = tuple(item["id"] for item in PREREQUISITES)
PREREQUISITE_DEFINITIONS = {item["id"]: item for item in PREREQUISITES}

OPAQUE_REF = re.compile(r"^(?:opaque|org|approval|artifact|evidence|scope|window|incident|rollback|owner|role|custody|fixture|witness|readback|allowlist|tenant|certificate|acl|revision|package):[A-Za-z0-9._-]{1,180}$")
HEX_SHA256 = re.compile(r"^[a-f0-9]{64}$")
RAW_IDENTITY = re.compile(r"(?:@|(?<![A-Za-z0-9])\+?\d[\d\s().-]{7,}\d(?![A-Za-z0-9])|\b(?:mr|mrs|ms|นาย|นาง|นางสาว)\b|\b(?:HN|AN|MRN|NATIONAL_ID)(?:\s*[-_:]\s*[A-Z0-9-]{2,}|\s+\d[A-Z0-9-]{1,})\b)", re.IGNORECASE)
SECRET_MARKER = re.compile(r"(?:BEGIN (?:RSA|EC|OPENSSH|DSA|PRIVATE) KEY|Bearer(?:\s+|[-_])\S+|(?:password|secret|token|private_key|seed|api[_-]?key)(?:\s*[:=]|[-_])\S+)", re.IGNORECASE)
FORBIDDEN_CLAIMS = re.compile(r"(?:clinical-ready|production-ready|tamper-proof|HIPAA/PDPA compliant 100%)", re.IGNORECASE)


class IntakeValidationError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise IntakeValidationError(message)


def _exact_keys(value: Any, expected: set[str], field: str) -> None:
    _require(isinstance(value, dict), f"{field} must be an object")
    unknown = sorted(set(value) - expected)
    missing = sorted(expected - set(value))
    _require(not unknown and not missing, f"{field} fields mismatch: unknown={unknown}, missing={missing}")


def _safe_text(value: Any, field: str, *, max_length: int = 512) -> str:
    _require(isinstance(value, str) and value.strip(), f"{field} must be non-empty text")
    _require(len(value) <= max_length, f"{field} too large")
    _require(RAW_IDENTITY.search(value) is None, f"{field} must not contain raw identity/contact data")
    _require(SECRET_MARKER.search(value) is None, f"{field} must not contain secret material")
    _require(FORBIDDEN_CLAIMS.search(value) is None, f"{field} must not contain forbidden claim")
    return value


def _ref(value: Any, field: str, *, allow_pending: bool = False) -> str:
    _require(isinstance(value, str) and value.strip(), f"{field} must be a non-empty string")
    if allow_pending and value == PENDING:
        return value
    _require(OPAQUE_REF.fullmatch(value) is not None, f"{field} must be an opaque typed reference")
    _safe_text(value, field, max_length=192)
    return value


def _utc(value: Any, field: str, *, allow_pending: bool = False) -> str | None:
    if allow_pending and value == PENDING:
        return None
    _require(isinstance(value, str), f"{field} must be an ISO-8601 string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise IntakeValidationError(f"{field} must be a valid ISO-8601 timestamp") from exc
    _require(parsed.tzinfo is not None and parsed.utcoffset() is not None, f"{field} must be timezone-aware")
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _sha(value: Any, field: str, *, allow_zero: bool = False) -> str:
    _require(isinstance(value, str), f"{field} must be a string")
    if allow_zero and value == ZERO_SHA256:
        return value
    _require(HEX_SHA256.fullmatch(value) is not None, f"{field} must be lowercase SHA-256")
    return value


def _boundary(payload: dict[str, Any]) -> None:
    _require(payload.get("authorization_boundary") == AUTHORIZATION_BOUNDARY, "authorization boundary must remain locked")
    _require(payload.get("external_execution_authorized") is False, "local intake cannot authorize external execution")
    _require(payload.get("production_authorized") is False, "local intake cannot authorize production")
    _require(payload.get("clinical_validation_authorized") is False, "local intake cannot authorize clinical validation")
    _require(payload.get("execution_status") == "NOT_STARTED", "execution status must remain NOT_STARTED")


def _template_item(definition: dict[str, Any]) -> dict[str, Any]:
    return {
        "prerequisite_id": definition["id"],
        "track": definition["track"],
        "owner_roles": list(definition["owner_roles"]),
        "required_evidence": definition["required_evidence"],
        "status": "MISSING_EXTERNAL",
        "owner_ref": PENDING,
        "evidence_ref": PENDING,
        "observed_at_utc": PENDING,
        "artifact_sha256": ZERO_SHA256,
        "redaction": "PENDING",
        "independent_readback_ref": PENDING,
    }


def template() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "package_id": PENDING,
        "project": PROJECT,
        "repository": REPOSITORY,
        "source_revision": PENDING,
        "freeze_manifest_sha256": FREEZE_REFERENCE,
        "readiness": "READY_FOR_OWNER_APPOINTMENT",
        "submission_status": "NOT_SUBMITTED",
        "execution_status": "NOT_STARTED",
        "external_execution_authorized": False,
        "production_authorized": False,
        "clinical_validation_authorized": False,
        "independent_verification_required": True,
        "evidence_class": "SOFTWARE_VERIFIED/SIMULATION_ONLY",
        "authorization_boundary": deepcopy(AUTHORIZATION_BOUNDARY),
        "prerequisites": [_template_item(definition) for definition in PREREQUISITES],
    }


def _validate_common(payload: dict[str, Any]) -> None:
    expected_top = {
        "schema_version", "package_id", "project", "repository", "source_revision", "freeze_manifest_sha256",
        "readiness", "submission_status", "execution_status", "external_execution_authorized", "production_authorized",
        "clinical_validation_authorized", "independent_verification_required", "evidence_class", "authorization_boundary", "prerequisites",
    }
    _exact_keys(payload, expected_top, "payload")
    _require(payload.get("schema_version") == SCHEMA_VERSION, "schema_version mismatch")
    _require(payload.get("project") == PROJECT, "project mismatch")
    _require(payload.get("repository") == REPOSITORY, "repository mismatch")
    _require(payload.get("freeze_manifest_sha256") == FREEZE_REFERENCE, "freeze reference must use top-level binding")
    _boundary(payload)
    _require(payload.get("independent_verification_required") is True, "independent_verification_required must be true")
    _require(payload.get("evidence_class") in {"SOFTWARE_VERIFIED/SIMULATION_ONLY", "EXTERNAL_UNVERIFIED"}, "unsupported evidence class")
    prerequisites = payload.get("prerequisites")
    _require(isinstance(prerequisites, list) and len(prerequisites) == len(PREREQUISITES), "exactly 15 prerequisites are required")
    ids = [item.get("prerequisite_id") for item in prerequisites if isinstance(item, dict)]
    _require(tuple(ids) == PREREQUISITE_IDS, "prerequisite coverage/order mismatch")
    for item, definition in zip(prerequisites, PREREQUISITES):
        _exact_keys(item, {"prerequisite_id", "track", "owner_roles", "required_evidence", "status", "owner_ref", "evidence_ref", "observed_at_utc", "artifact_sha256", "redaction", "independent_readback_ref"}, f"prerequisites.{definition['id']}")
        _require(item["track"] == definition["track"], f"{definition['id']}:track mismatch")
        _require(item["owner_roles"] == definition["owner_roles"], f"{definition['id']}:owner roles mismatch")
        _require(item["required_evidence"] == definition["required_evidence"], f"{definition['id']}:required evidence mismatch")
        _safe_text(item["required_evidence"], f"{definition['id']}.required_evidence")
        _require(item["status"] in {"MISSING_EXTERNAL", "RECEIVED_EXTERNAL_UNVERIFIED", "SOFTWARE_VERIFIED"}, f"{definition['id']}:unsupported status")


def _validate_template(payload: dict[str, Any]) -> dict[str, Any]:
    _require(payload.get("readiness") == "READY_FOR_OWNER_APPOINTMENT", "template readiness mismatch")
    _require(payload.get("submission_status") == "NOT_SUBMITTED", "template submission must remain NOT_SUBMITTED")
    _require(payload.get("package_id") == PENDING, "template package_id must remain pending")
    _require(payload.get("source_revision") == PENDING, "template source_revision must remain pending")
    for definition, item in zip(PREREQUISITES, payload["prerequisites"]):
        _require(item == _template_item(definition), f"{definition['id']}:template item must remain blank-safe")
    return {"valid": True, "mode": "TEMPLATE_ONLY", "readiness": "READY_FOR_OWNER_APPOINTMENT", "execution_ready": False, "external_execution_authorized": False, "missing_count": 15}


def _validate_submission(payload: dict[str, Any]) -> dict[str, Any]:
    _require(payload.get("readiness") == "READY_FOR_OWNER_APPOINTMENT", "local intake cannot claim external execution readiness")
    _require(payload.get("submission_status") == "EXTERNAL_EVIDENCE_RECEIVED", "submission_status mismatch")
    _ref(payload.get("package_id"), "package_id")
    _ref(payload.get("source_revision"), "source_revision")
    prerequisites = payload["prerequisites"]
    seen_evidence: set[str] = set()
    received = 0
    for item in prerequisites:
        status = item["status"]
        if status == "MISSING_EXTERNAL":
            _require(item["owner_ref"] == PENDING, f"{item['prerequisite_id']}:missing owner must remain pending")
            _require(item["evidence_ref"] == PENDING, f"{item['prerequisite_id']}:missing evidence must remain pending")
            _require(item["observed_at_utc"] == PENDING, f"{item['prerequisite_id']}:missing timestamp must remain pending")
            _require(item["artifact_sha256"] == ZERO_SHA256, f"{item['prerequisite_id']}:missing hash must remain blank-safe")
            _require(item["redaction"] == "PENDING", f"{item['prerequisite_id']}:missing redaction must remain pending")
            _require(item["independent_readback_ref"] == PENDING, f"{item['prerequisite_id']}:missing read-back must remain pending")
            continue
        received += 1
        _ref(item["owner_ref"], f"{item['prerequisite_id']}.owner_ref")
        evidence_ref = _ref(item["evidence_ref"], f"{item['prerequisite_id']}.evidence_ref")
        _require(evidence_ref not in seen_evidence, "duplicate evidence_ref is not allowed")
        seen_evidence.add(evidence_ref)
        _utc(item["observed_at_utc"], f"{item['prerequisite_id']}.observed_at_utc")
        _sha(item["artifact_sha256"], f"{item['prerequisite_id']}.artifact_sha256")
        _require(item["redaction"] == "PASS", f"{item['prerequisite_id']}.redaction must be PASS")
        _ref(item["independent_readback_ref"], f"{item['prerequisite_id']}.independent_readback_ref")
    return {
        "valid": True,
        "mode": "SUBMITTED_EXTERNAL_INTAKE",
        "readiness": "READY_FOR_OWNER_APPOINTMENT",
        "execution_ready": False,
        "external_execution_authorized": False,
        "received_count": received,
        "missing_count": len(PREREQUISITES) - received,
    }


def validate(payload: dict[str, Any], *, template_only: bool = False) -> dict[str, Any]:
    _require(isinstance(payload, dict), "payload must be an object")
    _validate_common(payload)
    if template_only:
        return _validate_template(payload)
    return _validate_submission(payload)


def canonical_sha256(payload: dict[str, Any]) -> str:
    candidate = deepcopy(payload)
    candidate.pop("canonical_sha256", None)
    encoded = json.dumps(candidate, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


__all__ = [
    "AUTHORIZATION_BOUNDARY",
    "FREEZE_REFERENCE",
    "IntakeValidationError",
    "PREREQUISITES",
    "SCHEMA_VERSION",
    "canonical_sha256",
    "template",
    "validate",
]


if __name__ == "__main__":
    print(json.dumps({"schema_version": SCHEMA_VERSION, "prerequisite_count": len(PREREQUISITES), "template_sha256": canonical_sha256(template())}, indent=2))
