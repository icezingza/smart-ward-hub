from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "wave0-owner-appointment-intake-v1"
PROJECT = "smart-ward-hub"
OPAQUE_REF = re.compile(r"^(?:opaque|org|approval|evidence|artifact|scope|window|incident|rollback):[A-Za-z0-9._-]+$")
RAW_IDENTITY = re.compile(r"(?:@|\+?\d[\d\s().-]{6,}|\b(?:mr|mrs|ms|นาย|นาง|นางสาว)\b)", re.IGNORECASE)
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


def _ref(value: Any, field: str, *, allow_pending: bool = False) -> str:
    _require(isinstance(value, str) and value, f"{field} must be a non-empty string")
    if allow_pending and value == "PENDING_EXTERNAL_APPOINTMENT":
        return value
    _require(OPAQUE_REF.fullmatch(value) is not None, f"{field} must be an opaque typed reference")
    _require(RAW_IDENTITY.search(value) is None, f"{field} must not contain raw identity/contact data")
    return value


def _utc(value: Any, field: str) -> datetime:
    _require(isinstance(value, str), f"{field} must be an ISO-8601 string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise IntakeValidationError(f"{field} must be a valid ISO-8601 timestamp") from exc
    _require(parsed.tzinfo is not None, f"{field} must be timezone-aware")
    return parsed.astimezone(timezone.utc)


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
    if template_only:
        _require(payload.get("package_id") == "PENDING_EXTERNAL_APPOINTMENT", "template package_id must remain pending")
        _require(payload.get("source_revision") == "PENDING_EXTERNAL_APPOINTMENT", "template source_revision must remain pending")
        _require(payload.get("freeze_manifest_sha256") == "0" * 64, "template freeze hash must remain blank-safe")
    else:
        _ref(payload.get("package_id"), "package_id")
        _ref(payload.get("source_revision"), "source_revision")
        _require(isinstance(payload.get("freeze_manifest_sha256"), str) and re.fullmatch(r"[a-f0-9]{64}", payload["freeze_manifest_sha256"]) is not None, "freeze_manifest_sha256 must be lowercase SHA-256")
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
        _require(payload.get("roles", {}).get("external_coordinator") == "PENDING_EXTERNAL_APPOINTMENT", "template must remain blank-safe")
        return {"valid": True, "mode": "TEMPLATE_ONLY", "execution_ready": False}

    _require(payload.get("status") == "OWNER_APPOINTMENT_SUBMITTED", "submitted intake status mismatch")
    scope = payload.get("scope")
    _require(isinstance(scope, dict), "scope must be an object")
    _ref(scope.get("scope_id"), "scope.scope_id")
    _ref(scope.get("signed_scope_ref"), "scope.signed_scope_ref")
    _ref(scope.get("approved_by_ref"), "scope.approved_by_ref")
    _require(isinstance(scope.get("in_scope"), list) and scope["in_scope"], "scope.in_scope must be non-empty")
    _require(isinstance(scope.get("out_of_scope"), list) and scope["out_of_scope"], "scope.out_of_scope must be non-empty")

    window = payload.get("test_window")
    _require(isinstance(window, dict), "test_window must be an object")
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
        _require(isinstance(entry, dict), f"roles.{role} must be an object")
        role_refs[role] = _ref(entry.get("actor_ref"), f"roles.{role}.actor_ref")
        _ref(entry.get("organization_ref"), f"roles.{role}.organization_ref")
        _ref(entry.get("appointment_ref"), f"roles.{role}.appointment_ref")
    _require(len(set(role_refs.values())) == len(role_refs), "roles must satisfy separation of duties")
    _require(role_refs["stop_authority"] != role_refs["rollback_owner"], "stop_authority and rollback_owner must be distinct")
    _require(role_refs["independent_verifier"] != role_refs["external_coordinator"], "independent verifier must be independent")

    stop = payload.get("stop_authority")
    _require(isinstance(stop, dict), "stop_authority must be an object")
    _ref(stop.get("stop_rule_ref"), "stop_authority.stop_rule_ref")
    _ref(stop.get("notification_ref"), "stop_authority.notification_ref")
    rollback = payload.get("rollback_plan")
    _require(isinstance(rollback, dict), "rollback_plan must be an object")
    _ref(rollback.get("target_revision"), "rollback_plan.target_revision")
    _ref(rollback.get("owner_approval_ref"), "rollback_plan.owner_approval_ref")
    _ref(rollback.get("restore_drill_ref"), "rollback_plan.restore_drill_ref")

    evidence = payload.get("evidence_intake")
    _require(isinstance(evidence, dict), "evidence_intake must be an object")
    _ref(evidence.get("submission_manifest_ref"), "evidence_intake.submission_manifest_ref")
    _ref(evidence.get("custody_ref"), "evidence_intake.custody_ref")
    _require(evidence.get("redaction") == "PASS", "evidence_intake.redaction must be PASS")
    return {"valid": True, "mode": "SUBMITTED", "execution_ready": True, "role_count": len(role_refs)}


def template() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "package_id": "PENDING_EXTERNAL_APPOINTMENT",
        "project": PROJECT,
        "repository": "icezingza/smart-ward-hub",
        "source_revision": "PENDING_EXTERNAL_APPOINTMENT",
        "freeze_manifest_sha256": "0" * 64,
        "scope": {"scope_id": "PENDING_EXTERNAL_APPOINTMENT", "signed_scope_ref": "PENDING_EXTERNAL_APPOINTMENT", "approved_by_ref": "PENDING_EXTERNAL_APPOINTMENT", "in_scope": [], "out_of_scope": []},
        "test_window": {"start_utc": None, "end_utc": None, "approval_ref": "PENDING_EXTERNAL_APPOINTMENT", "allowlist_ref": "PENDING_EXTERNAL_APPOINTMENT"},
        "roles": {role: "PENDING_EXTERNAL_APPOINTMENT" for role in REQUIRED_ROLES},
        "stop_authority": {"stop_rule_ref": "PENDING_EXTERNAL_APPOINTMENT", "notification_ref": "PENDING_EXTERNAL_APPOINTMENT"},
        "rollback_plan": {"target_revision": "PENDING_EXTERNAL_APPOINTMENT", "owner_approval_ref": "PENDING_EXTERNAL_APPOINTMENT", "restore_drill_ref": "PENDING_EXTERNAL_APPOINTMENT"},
        "evidence_intake": {"submission_manifest_ref": "PENDING_EXTERNAL_APPOINTMENT", "custody_ref": "PENDING_EXTERNAL_APPOINTMENT", "redaction": "PENDING"},
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
