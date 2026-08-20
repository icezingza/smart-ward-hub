from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any


SCHEMA_VERSION = "wave0-owner-appointment-intake-v1"
PROJECT = "smart-ward-hub"
REPOSITORY = "icezingza/smart-ward-hub"
PENDING = "PENDING_EXTERNAL_APPOINTMENT"
OPAQUE_REF = re.compile(r"^(?:opaque|org|approval|evidence|artifact|scope|window|incident|rollback):[A-Za-z0-9._-]+$")
RAW_IDENTITY = re.compile(r"(?:@|(?<![A-Za-z0-9])\+?\d[\d\s().-]{7,}\d(?![A-Za-z0-9])|\b(?:mr|mrs|ms|นาย|นาง|นางสาว)\b|\b(?:HN|AN|MRN|NATIONAL_ID)(?:\s*[-_:]\s*[A-Z0-9-]{2,}|\s+\d[A-Z0-9-]{1,})\b)", re.IGNORECASE)
SECRET_MARKER = re.compile(r"(?:BEGIN (?:RSA|EC|OPENSSH|DSA|PRIVATE) KEY|Bearer\s+\S+|(?:password|secret|token|private_key|seed)\s*[:=]\s*\S+)", re.IGNORECASE)
REQUIRED_ROLES = (
    "external_coordinator",
    "clinical_owner",
    "security_owner",
    "integration_owner",
    "custody_owner",
    "reliability_owner",
    "independent_verifier",
    "stop_authority",
    "rollback_owner",
)


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


def _ref(value: Any, field: str, *, allow_pending: bool = False) -> str:
    _require(isinstance(value, str) and value.strip(), f"{field} must be a non-empty string")
    if allow_pending and value == PENDING:
        return value
    _require(OPAQUE_REF.fullmatch(value) is not None, f"{field} must be an opaque typed reference")
    _require(RAW_IDENTITY.search(value) is None, f"{field} must not contain raw identity/contact data")
    _require(SECRET_MARKER.search(value) is None, f"{field} must not contain secret material")
    return value


def _safe_scope_items(value: Any, field: str) -> None:
    _require(isinstance(value, list) and value, f"{field} must be a non-empty list")
    seen: set[str] = set()
    for index, item in enumerate(value):
        _require(isinstance(item, str) and item.strip(), f"{field}[{index}] must be non-empty text")
        _require(len(item) <= 512, f"{field}[{index}] too large")
        _require(RAW_IDENTITY.search(item) is None, f"{field}[{index}] must not contain raw identity/contact data")
        _require(SECRET_MARKER.search(item) is None, f"{field}[{index}] must not contain secret material")
        _require(item not in seen, f"{field} must not contain duplicate items")
        seen.add(item)


def _utc(value: Any, field: str) -> datetime:
    _require(isinstance(value, str), f"{field} must be an ISO-8601 string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, TypeError, ValueError) as exc:
        raise IntakeValidationError(f"{field} must be a valid ISO-8601 timestamp") from exc
    _require(parsed.tzinfo is not None and parsed.utcoffset() is not None, f"{field} must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _validate_template_shape(payload: dict[str, Any]) -> None:
    _require(payload.get("repository") == REPOSITORY, "template repository mismatch")
    _require(payload.get("package_id") == PENDING, "template package_id must remain pending")
    _require(payload.get("source_revision") == PENDING, "template source_revision must remain pending")
    _require(payload.get("freeze_manifest_sha256") == "0" * 64, "template freeze hash must remain blank-safe")
    _exact_keys(payload.get("scope"), {"scope_id", "signed_scope_ref", "approved_by_ref", "in_scope", "out_of_scope"}, "template.scope")
    for field in ("scope_id", "signed_scope_ref", "approved_by_ref"):
        _require(payload["scope"][field] == PENDING, f"template.scope.{field} must remain pending")
    _require(payload["scope"]["in_scope"] == [] and payload["scope"]["out_of_scope"] == [], "template scope lists must remain empty")
    _exact_keys(payload.get("test_window"), {"start_utc", "end_utc", "approval_ref", "allowlist_ref"}, "template.test_window")
    _require(payload["test_window"]["start_utc"] is None and payload["test_window"]["end_utc"] is None, "template test window timestamps must remain blank")
    _require(payload["test_window"]["approval_ref"] == PENDING and payload["test_window"]["allowlist_ref"] == PENDING, "template test window refs must remain pending")
    _exact_keys(payload.get("roles"), set(REQUIRED_ROLES), "template.roles")
    _require(all(payload["roles"][role] == PENDING for role in REQUIRED_ROLES), "template roles must remain blank-safe")
    _exact_keys(payload.get("stop_authority"), {"stop_rule_ref", "notification_ref"}, "template.stop_authority")
    _require(all(payload["stop_authority"][field] == PENDING for field in ("stop_rule_ref", "notification_ref")), "template stop authority must remain pending")
    _exact_keys(payload.get("rollback_plan"), {"target_revision", "owner_approval_ref", "restore_drill_ref"}, "template.rollback_plan")
    _require(all(payload["rollback_plan"][field] == PENDING for field in ("target_revision", "owner_approval_ref", "restore_drill_ref")), "template rollback plan must remain pending")
    _exact_keys(payload.get("evidence_intake"), {"submission_manifest_ref", "custody_ref", "redaction"}, "template.evidence_intake")
    _require(payload["evidence_intake"]["submission_manifest_ref"] == PENDING and payload["evidence_intake"]["custody_ref"] == PENDING, "template evidence refs must remain pending")
    _require(payload["evidence_intake"]["redaction"] == "PENDING", "template evidence redaction must remain pending")


def validate_owner_appointment_intake(payload: dict[str, Any], *, template_only: bool = False) -> dict[str, Any]:
    _require(isinstance(payload, dict), "payload must be an object")
    allowed = {
        "schema_version", "package_id", "project", "repository", "source_revision", "freeze_manifest_sha256",
        "scope", "test_window", "roles", "stop_authority", "rollback_plan", "evidence_intake",
        "authorization_boundary", "status", "external_execution_authorized", "production_authorized",
        "clinical_validation_authorized", "independent_verification_required",
    }
    unknown = sorted(set(payload) - allowed)
    _require(not unknown, f"unknown fields: {unknown}")
    _require(payload.get("schema_version") == SCHEMA_VERSION, "schema_version mismatch")
    _require(payload.get("project") == PROJECT, "project mismatch")
    _require(payload.get("repository") == REPOSITORY, "repository mismatch")
    _require(payload.get("authorization_boundary") == {
        "external_authority": "NONE",
        "clinical_validation_authorized": False,
        "production_authorized": False,
        "runtime_authority": "NONE",
        "pilot_gate_status": "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION",
    }, "authorization boundary must remain locked")
    _require(payload.get("external_execution_authorized") is False, "local intake cannot authorize external execution")
    _require(payload.get("production_authorized") is False, "local intake cannot authorize production")
    _require(payload.get("clinical_validation_authorized") is False, "local intake cannot authorize clinical validation")
    _require(payload.get("independent_verification_required") is True, "independent_verification_required must be true")

    if template_only:
        _require(payload.get("status") == "OWNER_APPOINTMENT_TEMPLATE", "template status mismatch")
        _validate_template_shape(payload)
        return {"valid": True, "mode": "TEMPLATE_ONLY", "execution_ready": False, "owner_appointment_ready": False}

    if payload.get("status") == "OWNER_APPOINTMENT_TEMPLATE":
        raise IntakeValidationError("submitted validation cannot use template status")
    _require(payload.get("status") == "OWNER_APPOINTMENT_SUBMITTED", "submitted intake status mismatch")
    _ref(payload.get("package_id"), "package_id")
    _ref(payload.get("source_revision"), "source_revision")
    _require(isinstance(payload.get("freeze_manifest_sha256"), str) and re.fullmatch(r"[a-f0-9]{64}", payload["freeze_manifest_sha256"]) is not None, "freeze_manifest_sha256 must be lowercase SHA-256")

    scope = payload.get("scope")
    _exact_keys(scope, {"scope_id", "signed_scope_ref", "approved_by_ref", "in_scope", "out_of_scope"}, "scope")
    _ref(scope.get("scope_id"), "scope.scope_id")
    _ref(scope.get("signed_scope_ref"), "scope.signed_scope_ref")
    _ref(scope.get("approved_by_ref"), "scope.approved_by_ref")
    _safe_scope_items(scope.get("in_scope"), "scope.in_scope")
    _safe_scope_items(scope.get("out_of_scope"), "scope.out_of_scope")

    window = payload.get("test_window")
    _exact_keys(window, {"start_utc", "end_utc", "approval_ref", "allowlist_ref"}, "test_window")
    start = _utc(window.get("start_utc"), "test_window.start_utc")
    end = _utc(window.get("end_utc"), "test_window.end_utc")
    _require(start < end, "test_window.start_utc must precede end_utc")
    _ref(window.get("approval_ref"), "test_window.approval_ref")
    _ref(window.get("allowlist_ref"), "test_window.allowlist_ref")

    roles = payload.get("roles")
    _require(isinstance(roles, dict), "roles must be an object")
    _require(set(roles) == set(REQUIRED_ROLES), "roles must contain exactly the required roles")
    role_refs: dict[str, str] = {}
    for role in REQUIRED_ROLES:
        entry = roles[role]
        _exact_keys(entry, {"actor_ref", "organization_ref", "appointment_ref"}, f"roles.{role}")
        role_refs[role] = _ref(entry.get("actor_ref"), f"roles.{role}.actor_ref")
        _ref(entry.get("organization_ref"), f"roles.{role}.organization_ref")
        _ref(entry.get("appointment_ref"), f"roles.{role}.appointment_ref")
    _require(len(set(role_refs.values())) == len(role_refs), "roles must satisfy separation of duties")
    _require(role_refs["stop_authority"] != role_refs["rollback_owner"], "stop_authority and rollback_owner must be distinct")
    _require(role_refs["independent_verifier"] != role_refs["external_coordinator"], "independent verifier must be independent")

    stop = payload.get("stop_authority")
    _exact_keys(stop, {"stop_rule_ref", "notification_ref"}, "stop_authority")
    _ref(stop.get("stop_rule_ref"), "stop_authority.stop_rule_ref")
    _ref(stop.get("notification_ref"), "stop_authority.notification_ref")
    rollback = payload.get("rollback_plan")
    _exact_keys(rollback, {"target_revision", "owner_approval_ref", "restore_drill_ref"}, "rollback_plan")
    _ref(rollback.get("target_revision"), "rollback_plan.target_revision")
    _ref(rollback.get("owner_approval_ref"), "rollback_plan.owner_approval_ref")
    _ref(rollback.get("restore_drill_ref"), "rollback_plan.restore_drill_ref")

    evidence = payload.get("evidence_intake")
    _exact_keys(evidence, {"submission_manifest_ref", "custody_ref", "redaction"}, "evidence_intake")
    _ref(evidence.get("submission_manifest_ref"), "evidence_intake.submission_manifest_ref")
    _ref(evidence.get("custody_ref"), "evidence_intake.custody_ref")
    _require(evidence.get("redaction") == "PASS", "evidence_intake.redaction must be PASS")

    return {
        "valid": True,
        "mode": "SUBMITTED",
        "execution_ready": False,
        "owner_appointment_ready": True,
        "external_execution_authorized": False,
        "role_count": len(role_refs),
    }


def template() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "package_id": PENDING,
        "project": PROJECT,
        "repository": REPOSITORY,
        "source_revision": PENDING,
        "freeze_manifest_sha256": "0" * 64,
        "scope": {"scope_id": PENDING, "signed_scope_ref": PENDING, "approved_by_ref": PENDING, "in_scope": [], "out_of_scope": []},
        "test_window": {"start_utc": None, "end_utc": None, "approval_ref": PENDING, "allowlist_ref": PENDING},
        "roles": {role: PENDING for role in REQUIRED_ROLES},
        "stop_authority": {"stop_rule_ref": PENDING, "notification_ref": PENDING},
        "rollback_plan": {"target_revision": PENDING, "owner_approval_ref": PENDING, "restore_drill_ref": PENDING},
        "evidence_intake": {"submission_manifest_ref": PENDING, "custody_ref": PENDING, "redaction": "PENDING"},
        "authorization_boundary": {"external_authority": "NONE", "clinical_validation_authorized": False, "production_authorized": False, "runtime_authority": "NONE", "pilot_gate_status": "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION"},
        "status": "OWNER_APPOINTMENT_TEMPLATE",
        "external_execution_authorized": False,
        "production_authorized": False,
        "clinical_validation_authorized": False,
        "independent_verification_required": True,
    }


def template_sha256() -> str:
    data = json.dumps(template(), sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(data).hexdigest()


if __name__ == "__main__":
    sample = template()
    print(json.dumps({"schema_version": SCHEMA_VERSION, "template_sha256": template_sha256(), "status": sample["status"]}, indent=2))
