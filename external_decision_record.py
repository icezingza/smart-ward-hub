from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import re
from typing import Any


SCHEMA_VERSION = "external-decision-record-v1"
PROJECT = "smart-ward-hub"
REPOSITORY = "icezingza/smart-ward-hub"
PENDING = "PENDING_EXTERNAL_APPOINTMENT"
ZERO_SHA256 = "0" * 64

AUTHORIZATION_BOUNDARY = {
    "external_authority": "NONE",
    "clinical_validation_authorized": False,
    "production_authorized": False,
    "runtime_authority": "NONE",
    "pilot_gate_status": "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION",
}

TEMPLATE_STATUS = "DECISION_RECORD_TEMPLATE"
RECEIVED_STATUS = "EXTERNAL_DECISION_RECORD_RECEIVED"
ALLOWED_DECISIONS = {"BLOCKED", "REQUIRES_CLARIFICATION", "ACCEPTED_WITH_RESIDUAL_RISK"}
ALLOWED_RESPONSE_VERIFICATION = {"UNVERIFIED", "EXTERNAL_VERIFIER_PENDING"}
ALLOWED_EVIDENCE_CLASSES = {"LOCAL_TEMPLATE", "EXTERNAL_UNVERIFIED"}
DECISION_ROLES = {"external_authority", "independent_reviewer"}

OPAQUE_REF = re.compile(r"^(?:opaque|org|approval|artifact|evidence|finding|risk|condition|scope|window|incident|rollback|stop|owner|role|custody|fixture|witness|readback|allowlist|tenant|certificate|acl|revision|package|submission|decision|signature|revocation|key|trust|channel):[A-Za-z0-9._-]{1,180}$")
HEX_SHA256 = re.compile(r"^[a-f0-9]{64}$")
RAW_CONTACT = re.compile(r"(?:@|\b(?:mr|mrs|ms|นาย|นาง|นางสาว)\b|\b(?:HN|AN|MRN|NATIONAL_ID)(?:\s*[-_:]\s*[A-Z0-9-]{2,}|\s+\d[A-Z0-9-]{1,})\b)", re.IGNORECASE)
RAW_PHONE = re.compile(r"(?<![A-Za-z0-9])\+?\d[\d\s().-]{7,}\d(?![A-Za-z0-9])")
PHONE_LIKE_REF_SUFFIX = re.compile(r"^[+\d\s().-]+$")
DATE_LIKE_REF_SUFFIX = re.compile(r"^(?:19|20|21)\d{2}(?:-?\d{2}){2}(?:[-_]\d{1,8})?$")
SECRET_MARKER = re.compile(r"(?:BEGIN (?:RSA|EC|OPENSSH|DSA|PRIVATE) KEY|Bearer(?:\s+|[-_])\S+|(?:password|secret|token|private_key|seed|api[_-]?key)(?:\s*[:=]|[-_])\S+)", re.IGNORECASE)
FORBIDDEN_CLAIM = re.compile(r"(?:clinical-ready|production-ready|tamper-proof|HIPAA/PDPA compliant 100%)", re.IGNORECASE)


class DecisionRecordValidationError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise DecisionRecordValidationError(message)


def _exact_keys(value: Any, expected: set[str], field: str) -> None:
    _require(isinstance(value, dict), f"{field} must be an object")
    unknown = sorted(set(value) - expected)
    missing = sorted(expected - set(value))
    _require(not unknown and not missing, f"{field} fields mismatch: unknown={unknown}, missing={missing}")


def _safe_text(value: Any, field: str, *, max_length: int = 512, allow_typed_numeric: bool = False) -> str:
    _require(isinstance(value, str) and value.strip(), f"{field} must be non-empty text")
    _require(len(value) <= max_length, f"{field} too large")
    _require(RAW_CONTACT.search(value) is None, f"{field} must not contain raw identity/contact data")
    if not allow_typed_numeric:
        _require(RAW_PHONE.search(value) is None, f"{field} must not contain raw identity/contact data")
    _require(SECRET_MARKER.search(value) is None, f"{field} must not contain secret material")
    _require(FORBIDDEN_CLAIM.search(value) is None, f"{field} must not contain forbidden claim")
    return value


def _ref(value: Any, field: str, *, allow_pending: bool = False) -> str:
    _require(isinstance(value, str) and value.strip(), f"{field} must be a non-empty string")
    if allow_pending and value == PENDING:
        return value
    _require(OPAQUE_REF.fullmatch(value) is not None, f"{field} must be an opaque typed reference")
    suffix = value.split(":", 1)[1]
    _require(PHONE_LIKE_REF_SUFFIX.fullmatch(suffix) is None or DATE_LIKE_REF_SUFFIX.fullmatch(suffix) is not None, f"{field} must not be a numeric-only contact reference")
    _safe_text(value, field, max_length=192, allow_typed_numeric=True)
    return value


def _sha(value: Any, field: str, *, allow_zero: bool = False) -> str:
    _require(isinstance(value, str), f"{field} must be a string")
    if allow_zero and value == ZERO_SHA256:
        return value
    _require(HEX_SHA256.fullmatch(value) is not None, f"{field} must be lowercase SHA-256")
    return value


def _utc(value: Any, field: str, *, allow_pending: bool = False) -> str | None:
    if allow_pending and value == PENDING:
        return None
    _require(isinstance(value, str), f"{field} must be an ISO-8601 string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise DecisionRecordValidationError(f"{field} must be a valid ISO-8601 timestamp") from exc
    _require(parsed.tzinfo is not None and parsed.utcoffset() is not None, f"{field} must be timezone-aware")
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _ref_list(value: Any, field: str, *, allow_empty: bool = True) -> list[str]:
    _require(isinstance(value, list), f"{field} must be a list")
    if not allow_empty:
        _require(bool(value), f"{field} must not be empty")
    result = []
    seen: set[str] = set()
    for index, item in enumerate(value):
        reference = _ref(item, f"{field}[{index}]")
        _require(reference not in seen, f"{field} contains duplicate reference")
        seen.add(reference)
        result.append(reference)
    return result


def _boundary(payload: dict[str, Any]) -> None:
    _require(payload.get("authorization_boundary") == AUTHORIZATION_BOUNDARY, "authorization boundary must remain locked")
    _require(payload.get("external_execution_authorized") is False, "local record cannot authorize external execution")
    _require(payload.get("production_authorized") is False, "local record cannot authorize production")
    _require(payload.get("clinical_validation_authorized") is False, "local record cannot authorize clinical validation")
    _require(payload.get("authorization_promoted") is False, "local record cannot promote authorization")


def _blank_basis() -> dict[str, list[str]]:
    return {"evidence_ids": [], "finding_ids": [], "residual_risk_ids": [], "condition_ids": []}


def _blank_authenticity() -> dict[str, Any]:
    return {
        "verification_status": "UNVERIFIED",
        "key_id_ref": PENDING,
        "certificate_ref": PENDING,
        "trust_chain_ref": PENDING,
        "verified_at_utc": PENDING,
    }


def template() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "project": PROJECT,
        "repository": REPOSITORY,
        "record_id": PENDING,
        "decision_id": PENDING,
        "submission_id": PENDING,
        "manifest_sha256": ZERO_SHA256,
        "scope_id": PENDING,
        "window_id": PENDING,
        "decision": PENDING,
        "decision_basis": _blank_basis(),
        "decided_by_role": PENDING,
        "decided_by_ref": PENDING,
        "decision_timestamp": PENDING,
        "effective_from": PENDING,
        "expires_at": PENDING,
        "rollback_ref": PENDING,
        "stop_authority_ref": PENDING,
        "signature_ref": PENDING,
        "independent_verification_ref": PENDING,
        "revocation_ref": PENDING,
        "response_authenticity": _blank_authenticity(),
        "status": TEMPLATE_STATUS,
        "evidence_class": "LOCAL_TEMPLATE",
        "external_decision_verified": False,
        "authorization_promoted": False,
        "external_execution_authorized": False,
        "production_authorized": False,
        "clinical_validation_authorized": False,
        "authorization_boundary": deepcopy(AUTHORIZATION_BOUNDARY),
        "independent_verification_required": True,
    }


def _validate_common(payload: dict[str, Any]) -> None:
    expected = {
        "schema_version", "project", "repository", "record_id", "decision_id", "submission_id", "manifest_sha256",
        "scope_id", "window_id", "decision", "decision_basis", "decided_by_role", "decided_by_ref", "decision_timestamp",
        "effective_from", "expires_at", "rollback_ref", "stop_authority_ref", "signature_ref", "independent_verification_ref",
        "revocation_ref", "response_authenticity", "status", "evidence_class", "external_decision_verified", "authorization_promoted",
        "external_execution_authorized", "production_authorized", "clinical_validation_authorized", "authorization_boundary", "independent_verification_required",
    }
    _exact_keys(payload, expected, "payload")
    _require(payload.get("schema_version") == SCHEMA_VERSION, "schema_version mismatch")
    _require(payload.get("project") == PROJECT, "project mismatch")
    _require(payload.get("repository") == REPOSITORY, "repository mismatch")
    _require(payload.get("evidence_class") in ALLOWED_EVIDENCE_CLASSES, "unsupported evidence class")
    _require(payload.get("external_decision_verified") is False, "local record cannot verify external decision")
    _require(payload.get("independent_verification_required") is True, "independent_verification_required must be true")
    _boundary(payload)
    _sha(payload.get("manifest_sha256"), "manifest_sha256", allow_zero=payload.get("status") == TEMPLATE_STATUS)

    basis = payload.get("decision_basis")
    _exact_keys(basis, {"evidence_ids", "finding_ids", "residual_risk_ids", "condition_ids"}, "decision_basis")
    for field in basis:
        _ref_list(basis[field], f"decision_basis.{field}")

    authenticity = payload.get("response_authenticity")
    _exact_keys(authenticity, {"verification_status", "key_id_ref", "certificate_ref", "trust_chain_ref", "verified_at_utc"}, "response_authenticity")
    _require(authenticity.get("verification_status") in ALLOWED_RESPONSE_VERIFICATION, "response authenticity must remain unverified locally")


def _validate_template(payload: dict[str, Any]) -> dict[str, Any]:
    _require(payload.get("status") == TEMPLATE_STATUS, "template status mismatch")
    _require(payload.get("evidence_class") == "LOCAL_TEMPLATE", "template evidence class mismatch")
    _require(payload == template(), "template must remain blank-safe and exact")
    return {
        "valid": True,
        "mode": "TEMPLATE_ONLY",
        "decision_record_ready": False,
        "authorization_promoted": False,
        "external_decision_verified": False,
    }


def _validate_received(payload: dict[str, Any]) -> dict[str, Any]:
    _require(payload.get("status") == RECEIVED_STATUS, "received status mismatch")
    _require(payload.get("evidence_class") == "EXTERNAL_UNVERIFIED", "received record must remain externally unverified")
    for field in ("record_id", "decision_id", "submission_id", "scope_id", "window_id", "decided_by_ref", "rollback_ref", "stop_authority_ref", "signature_ref", "independent_verification_ref", "revocation_ref"):
        _ref(payload.get(field), field)
    _sha(payload.get("manifest_sha256"), "manifest_sha256")
    _require(payload.get("decision") in ALLOWED_DECISIONS, "decision must be a non-authorizing external decision")
    _require(payload.get("decided_by_role") in DECISION_ROLES, "decided_by_role must be an external role")
    decision_timestamp = _utc(payload.get("decision_timestamp"), "decision_timestamp")
    effective_from = _utc(payload.get("effective_from"), "effective_from")
    expires_at = _utc(payload.get("expires_at"), "expires_at")
    _require(effective_from < expires_at, "effective_from must precede expires_at")
    _require(decision_timestamp <= expires_at, "decision_timestamp must not follow expires_at")
    _require(any(payload["decision_basis"].values()), "decision_basis must contain at least one reference")

    authenticity = payload["response_authenticity"]
    _require(authenticity["verification_status"] in ALLOWED_RESPONSE_VERIFICATION, "response authenticity cannot be locally verified")
    for field in ("key_id_ref", "certificate_ref", "trust_chain_ref"):
        _ref(authenticity[field], f"response_authenticity.{field}")
    _utc(authenticity["verified_at_utc"], "response_authenticity.verified_at_utc")
    return {
        "valid": True,
        "mode": "EXTERNAL_RECORD_RECEIVED",
        "decision_record_ready": True,
        "authorization_promoted": False,
        "external_decision_verified": False,
        "decision": payload["decision"],
        "decision_timestamp": decision_timestamp,
        "effective_from": effective_from,
        "expires_at": expires_at,
    }


def validate(payload: dict[str, Any], *, template_only: bool = False) -> dict[str, Any]:
    _require(isinstance(payload, dict), "payload must be an object")
    _validate_common(payload)
    if template_only:
        return _validate_template(payload)
    return _validate_received(payload)


def canonical_sha256(payload: dict[str, Any]) -> str:
    candidate = deepcopy(payload)
    candidate.pop("canonical_sha256", None)
    encoded = json.dumps(candidate, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


__all__ = [
    "ALLOWED_DECISIONS",
    "AUTHORIZATION_BOUNDARY",
    "DecisionRecordValidationError",
    "RECEIVED_STATUS",
    "SCHEMA_VERSION",
    "TEMPLATE_STATUS",
    "canonical_sha256",
    "template",
    "validate",
]


if __name__ == "__main__":
    print(json.dumps({"schema_version": SCHEMA_VERSION, "template_sha256": canonical_sha256(template()), "authorization_promoted": False}, indent=2))
