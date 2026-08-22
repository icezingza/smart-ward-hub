"""Internal-only appointment plan for an independent reviewer.

This module prepares a controlled appointment packet blueprint. It never records a
real reviewer identity, confirms an appointment, submits evidence, or grants
external, clinical, runtime, or production authority.
"""
from __future__ import annotations

import json
import re
from typing import Any

from p4_independent_reviewer_handoff_readiness import evaluate_reviewer_handoff_readiness
from wave0_owner_appointment_intake import PENDING, REQUIRED_ROLES, template as owner_appointment_template, validate_owner_appointment_intake


SCHEMA_VERSION = "p4-independent-reviewer-appointment-plan-v1"
PROJECT = "smart-ward-hub"
TARGET_GATES = tuple(f"GV-{index:02d}" for index in range(1, 11))
TARGET_TESTS = tuple(f"T-{index:02d}" for index in range(1, 13))
REQUIRED_APPOINTMENT_RECORDS = (
    "reviewer_appointment_ref",
    "reviewer_organization_ref",
    "conflict_declaration_ref",
    "appointing_authority_ref",
    "signed_scope_ref",
    "decision_scope_ref",
    "expiry_ref",
    "readback_channel_ref",
    "custody_path_ref",
)
PENDING_EXTERNAL_INPUTS = (
    "named independent reviewer and conflict declaration",
    "reviewer organization and independence statement",
    "appointing external authority and decision scope",
    "signed intended-use/scope/expiry/rollback/stop record",
    "independent read-back channel and evidence custody path",
    "named stop authority and recovery approver",
    "external reviewer acceptance and findings protocol",
    "signed external appointment or explicit closed-no-authorization record",
)
RAW_ID_RE = re.compile(r"\b(?:HN|AN|MRN|NATIONAL[_ -]?ID)(?:\s*[-_:]\s*[A-Z0-9-]{2,}|\s+\d[A-Z0-9-]{1,})\b", re.IGNORECASE)
SECRET_RE = re.compile(r"(?:BEGIN (?:RSA|EC|OPENSSH|DSA|PRIVATE) KEY|Bearer\s+\S+|(?:password|secret|token|private_key|api_key)\s*[:=]\s*\S+)", re.IGNORECASE)


class AppointmentPlanError(ValueError):
    """Raised when the appointment plan violates the internal contract."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AppointmentPlanError(message)


def _redacted(value: Any) -> bool:
    encoded = json.dumps(value, ensure_ascii=True, sort_keys=True)
    return not RAW_ID_RE.search(encoded) and not SECRET_RE.search(encoded) and "@" not in encoded


def _locked_boundary() -> dict[str, Any]:
    return {
        "external_authority": "NONE",
        "clinical_validation_authorized": False,
        "production_authorized": False,
        "runtime_authority": "NONE",
        "pilot_gate_status": "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION",
    }


def appointment_plan_template() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "project": PROJECT,
        "plan_status": "APPOINTMENT_PLAN_TEMPLATE",
        "appointment_packet_id": PENDING,
        "reviewer_appointment": PENDING,
        "reviewer_organization": PENDING,
        "appointment_decision": "NOT_ISSUED",
        "conflict_declaration": PENDING,
        "decision_scope": {
            "scope_ref": PENDING,
            "signed_scope_ref": PENDING,
            "intended_use": "Controlled non-interventional external validation coordination for Smart Ward Hub",
            "in_scope": ["GV-01..GV-10", "T-01..T-12", "local software evidence and reproducibility read-back"],
            "out_of_scope": ["clinical treatment decisions", "production authorization", "real patient data", "real hardware validation without separate approval"],
            "expiry_required": True,
        },
        "required_appointment_records": list(REQUIRED_APPOINTMENT_RECORDS),
        "required_external_inputs": list(PENDING_EXTERNAL_INPUTS),
        "review_scope_gate_ids": list(TARGET_GATES),
        "review_scope_test_ids": list(TARGET_TESTS),
        "role_separation": {
            "independent_reviewer_role": "independent_reviewer",
            "appointing_authority_role": "external_authority",
            "system_operator_role": "internal_operator",
            "evidence_custodian_role": "evidence_custodian",
            "stop_authority_role": "stop_authority",
            "rollback_owner_role": "rollback_owner",
            "reviewer_must_differ_from": ["internal_operator", "external_coordinator", "evidence_custodian"],
            "stop_and_rollback_must_differ": True,
        },
        "acceptance_conditions": [
            "appointment and conflict declaration are signed/read-back",
            "external authority and decision scope are named",
            "intended use, expiry, rollback and stop rules are signed",
            "independent read-back and evidence custody are available",
            "reviewer has no production, clinical or runtime authority",
            "local software evidence remains evidence-only until external acceptance",
        ],
        "authorization_boundary": _locked_boundary(),
        "external_execution_authorized": False,
        "production_authorized": False,
        "clinical_validation_authorized": False,
        "independent_review_started": False,
        "submission_allowed": False,
        "software_evidence_only": True,
        "independent_verification_required": True,
        "redaction": "PASS",
        "raw_identity_present": False,
    }


def validate_appointment_plan(plan: dict[str, Any]) -> dict[str, Any]:
    _require(isinstance(plan, dict), "appointment plan must be an object")
    _require(plan.get("schema_version") == SCHEMA_VERSION, "schema_version mismatch")
    _require(plan.get("project") == PROJECT, "project mismatch")
    _require(plan.get("plan_status") == "APPOINTMENT_PLAN_TEMPLATE", "plan must remain a template")
    for field in ("appointment_packet_id", "reviewer_appointment", "reviewer_organization", "conflict_declaration"):
        _require(plan.get(field) == PENDING, f"{field} must remain pending")
    _require(plan.get("appointment_decision") == "NOT_ISSUED", "appointment decision must remain not issued")
    _require(plan.get("required_appointment_records") == list(REQUIRED_APPOINTMENT_RECORDS), "appointment records mismatch")
    _require(plan.get("required_external_inputs") == list(PENDING_EXTERNAL_INPUTS), "external input register mismatch")
    _require(plan.get("review_scope_gate_ids") == list(TARGET_GATES), "Gate scope mismatch")
    _require(plan.get("review_scope_test_ids") == list(TARGET_TESTS), "test scope mismatch")
    scope = plan.get("decision_scope")
    _require(isinstance(scope, dict), "decision_scope must be an object")
    _require(scope.get("scope_ref") == PENDING and scope.get("signed_scope_ref") == PENDING, "scope refs must remain pending")
    _require(scope.get("expiry_required") is True, "scope expiry is required")
    roles = plan.get("role_separation")
    _require(isinstance(roles, dict), "role separation must be an object")
    _require(roles.get("independent_reviewer_role") == "independent_reviewer", "reviewer role mismatch")
    _require(roles.get("appointing_authority_role") == "external_authority", "appointing authority mismatch")
    _require(roles.get("stop_and_rollback_must_differ") is True, "stop/rollback separation must be required")
    reviewer_must_differ = roles.get("reviewer_must_differ_from")
    _require(reviewer_must_differ == ["internal_operator", "external_coordinator", "evidence_custodian"], "reviewer independence rule mismatch")
    conditions = plan.get("acceptance_conditions")
    _require(isinstance(conditions, list) and len(conditions) == 6 and all(isinstance(item, str) and item.strip() for item in conditions), "acceptance conditions incomplete")
    _require(plan.get("authorization_boundary") == _locked_boundary(), "authorization boundary must remain locked")
    for field in ("external_execution_authorized", "production_authorized", "clinical_validation_authorized", "independent_review_started", "submission_allowed"):
        _require(plan.get(field) is False, f"{field} must remain false")
    _require(plan.get("software_evidence_only") is True, "software_evidence_only must be true")
    _require(plan.get("independent_verification_required") is True, "independent verification must remain required")
    _require(plan.get("redaction") == "PASS" and plan.get("raw_identity_present") is False, "redaction boundary mismatch")
    _require(_redacted(plan), "appointment plan contains unsafe identity or secret marker")
    return {
        "valid": True,
        "plan_status": plan["plan_status"],
        "required_appointment_records": len(plan["required_appointment_records"]),
        "required_external_inputs": len(plan["required_external_inputs"]),
        "review_scope_gate_ids": len(plan["review_scope_gate_ids"]),
        "review_scope_test_ids": len(plan["review_scope_test_ids"]),
        "appointment_decision": plan["appointment_decision"],
        "submission_allowed": plan["submission_allowed"],
        "authorization_boundary": dict(plan["authorization_boundary"]),
    }


def evaluate_appointment_plan() -> dict[str, Any]:
    plan = appointment_plan_template()
    owner_template = owner_appointment_template()
    owner_validation = validate_owner_appointment_intake(owner_template, template_only=True)
    reviewer_handoff = evaluate_reviewer_handoff_readiness()
    checks: dict[str, bool] = {}
    remediation_codes: list[str] = []
    try:
        plan_validation = validate_appointment_plan(plan)
    except AppointmentPlanError as exc:
        plan_validation = {"valid": False, "error": str(exc)}
    checks["appointment_plan_template_valid"] = plan_validation.get("valid") is True
    if not checks["appointment_plan_template_valid"]:
        remediation_codes.append("APPOINTMENT_PLAN_TEMPLATE_INVALID")
    checks["owner_appointment_template_valid"] = owner_validation.get("valid") is True and owner_validation.get("owner_appointment_ready") is False
    if not checks["owner_appointment_template_valid"]:
        remediation_codes.append("OWNER_APPOINTMENT_TEMPLATE_NOT_LOCKED")
    checks["reviewer_handoff_dependency_ready"] = reviewer_handoff.get("decision") == "P4_INDEPENDENT_REVIEWER_HANDOFF_READY" and reviewer_handoff.get("ready_for_external_appointment") is True and reviewer_handoff.get("ready_for_external_review") is False
    if not checks["reviewer_handoff_dependency_ready"]:
        remediation_codes.append("REVIEWER_HANDOFF_DEPENDENCY_NOT_READY")
    checks["scope_covers_all_gates_and_tests"] = plan.get("review_scope_gate_ids") == list(TARGET_GATES) and plan.get("review_scope_test_ids") == list(TARGET_TESTS)
    if not checks["scope_covers_all_gates_and_tests"]:
        remediation_codes.append("APPOINTMENT_SCOPE_INCOMPLETE")
    checks["role_separation_defined"] = (
        plan["role_separation"]["independent_reviewer_role"] != plan["role_separation"]["appointing_authority_role"]
        and plan["role_separation"]["stop_and_rollback_must_differ"] is True
        and len(plan["role_separation"]["reviewer_must_differ_from"]) == 3
    )
    if not checks["role_separation_defined"]:
        remediation_codes.append("REVIEWER_ROLE_SEPARATION_INCOMPLETE")
    checks["appointment_not_issued"] = plan.get("reviewer_appointment") == PENDING and plan.get("appointment_decision") == "NOT_ISSUED"
    if not checks["appointment_not_issued"]:
        remediation_codes.append("APPOINTMENT_SELF_ISSUED")
    checks["boundary_locked"] = plan.get("authorization_boundary") == _locked_boundary() and plan.get("submission_allowed") is False and plan.get("independent_review_started") is False
    if not checks["boundary_locked"]:
        remediation_codes.append("APPOINTMENT_AUTHORIZATION_BOUNDARY_MUTATED")
    checks["plan_redacted"] = _redacted(plan)
    if not checks["plan_redacted"]:
        remediation_codes.append("APPOINTMENT_PLAN_REDACTION_FAILED")
    remediation_codes = sorted(set(remediation_codes))
    decision = "P4_INDEPENDENT_REVIEWER_APPOINTMENT_PLAN_READY" if all(checks.values()) else "P4_INDEPENDENT_REVIEWER_APPOINTMENT_PLAN_BLOCKED"
    return {
        "schema_version": SCHEMA_VERSION,
        "evidence_type": "P4_INDEPENDENT_REVIEWER_APPOINTMENT_PLAN",
        "decision": decision,
        "checks": checks,
        "remediation_codes": remediation_codes,
        "plan": plan,
        "owner_appointment_template_validation": owner_validation,
        "reviewer_handoff_dependency": {
            "decision": reviewer_handoff.get("decision"),
            "ready_for_external_appointment": reviewer_handoff.get("ready_for_external_appointment"),
            "ready_for_external_review": reviewer_handoff.get("ready_for_external_review"),
            "submission_allowed": reviewer_handoff.get("submission_allowed"),
        },
        "external_authority": "NONE",
        "clinical_validation_authorized": False,
        "production_authorized": False,
        "runtime_authority": "NONE",
        "pilot_gate_status": "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION",
        "ready_for_external_appointment": True if all(checks.values()) else False,
        "ready_for_external_review": False,
        "appointment_confirmed": False,
        "submission_allowed": False,
        "read_only": True,
        "fixture_only": True,
        "external_transmission_performed": False,
        "runtime_mutation_performed": False,
        "authorization_promoted": False,
        "production_ready": False,
        "clinical_validation": "PENDING",
        "hardware_evidence": "UNVERIFIED",
        "claim_boundary": "CONTROLLED_PRODUCTION_PROTOTYPE",
    }


if __name__ == "__main__":
    print(json.dumps(evaluate_appointment_plan(), ensure_ascii=True, indent=2, sort_keys=True))
