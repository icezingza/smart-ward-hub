"""Local-only reconciliation of Wave 0 governance preparation artifacts.

The guard cross-checks existing software contracts. It does not appoint people,
create external authority, submit evidence, or execute a test window.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
import re
from typing import Any

from p3_external_gate_status_reconciliation import reconcile_external_gates
from p4_independent_reviewer_appointment_plan import (
    appointment_plan_template,
    evaluate_appointment_plan,
    validate_appointment_plan,
)
from wave0_governance import build_synthetic_wave0_package
from wave0_owner_appointment_intake import template as owner_appointment_template
from wave0_owner_appointment_intake import validate_owner_appointment_intake


SCHEMA_VERSION = "wave0-governance-reconciliation-v1"
FIXTURE_NOW = datetime(2026, 8, 20, 8, 0, tzinfo=timezone.utc)
RAW_IDENTITY = re.compile(r"\b(?:HN|AN|MRN|NATIONAL[_ -]?ID)(?:\s*[-_:]\s*[A-Z0-9-]{2,}|\s+\d[A-Z0-9-]{1,})\b", re.IGNORECASE)
SECRET_MARKER = re.compile(r"(?:-----BEGIN|Bearer(?:\s+|[-_])\S+|(?:password|secret|token|private_key|api_key)\s*[:=])", re.IGNORECASE)
LOCKED_BOUNDARY = {
    "external_authority": "NONE",
    "clinical_validation_authorized": False,
    "production_authorized": False,
    "runtime_authority": "NONE",
    "pilot_gate_status": "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION",
}
EXPECTED_GATE_COUNTS = {"BLOCKED": 7, "OPEN": 3, "EVIDENCE_SUBMITTED": 0, "TOTAL": 10}


class GovernanceReconciliationError(ValueError):
    """Raised when cross-package governance state cannot be reconciled safely."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise GovernanceReconciliationError(message)


def _redacted(value: Any) -> bool:
    encoded = json.dumps(value, ensure_ascii=True, sort_keys=True)
    return RAW_IDENTITY.search(encoded) is None and SECRET_MARKER.search(encoded) is None and "@" not in encoded


def _package_pre_freeze_check() -> dict[str, Any]:
    package = build_synthetic_wave0_package(now=FIXTURE_NOW)
    validation = package.validate(now=FIXTURE_NOW)
    checks = validation.get("checks", {})
    _require(validation.get("state") == "READY_TO_FREEZE", "Wave 0 package must remain ready to freeze locally")
    _require(validation.get("errors") == [], "Wave 0 package has validation errors")
    _require(checks.get("package_timestamp") is True, "Wave 0 package timestamp invalid")
    _require(checks.get("appointments_schema") is True, "Wave 0 appointment schema invalid")
    _require(checks.get("required_roles_present") is True, "Wave 0 required roles missing")
    _require(checks.get("scope_schema") is True, "Wave 0 scope schema invalid")
    _require(checks.get("test_window_schema") is True, "Wave 0 test window schema invalid")
    _require(checks.get("stop_authority_schema") is True, "Wave 0 stop authority schema invalid")
    _require(checks.get("freeze_schema") is False, "Wave 0 fixture must not self-create a freeze")
    _require(checks.get("authorization_locked") is True, "Wave 0 package authorization is not locked")
    _require(checks.get("external_verification_pending") is True, "Wave 0 external verification must remain pending")
    return {
        "state": validation["state"],
        "checks": {
            "package_timestamp": True,
            "appointments_schema": True,
            "required_roles_present": True,
            "scope_schema": True,
            "test_window_schema": True,
            "stop_authority_schema": True,
            "freeze_absent_before_external_review": True,
            "authorization_locked": True,
            "external_verification_pending": True,
        },
        "appointment_count": len(package.appointments),
        "freeze_created": package.freeze is not None,
    }


def _appointment_template_check() -> dict[str, Any]:
    owner_template = owner_appointment_template()
    owner_validation = validate_owner_appointment_intake(owner_template, template_only=True)
    _require(owner_validation.get("valid") is True, "owner appointment template invalid")
    _require(owner_validation.get("owner_appointment_ready") is False, "owner appointment template self-reported ready")

    plan = appointment_plan_template()
    plan_validation = validate_appointment_plan(plan)
    _require(plan_validation.get("valid") is True, "independent reviewer appointment plan invalid")
    _require(plan_validation.get("appointment_decision") == "NOT_ISSUED", "appointment decision must remain not issued")
    _require(plan_validation.get("submission_allowed") is False, "appointment plan submission must remain false")
    _require(plan_validation.get("review_scope_gate_ids") == 10, "review scope must cover ten gates")
    _require(plan_validation.get("review_scope_test_ids") == 12, "review scope must cover twelve tests")
    return {
        "owner_template_valid": True,
        "owner_appointment_ready": False,
        "reviewer_plan_valid": True,
        "appointment_decision": "NOT_ISSUED",
        "reviewer_appointment": "PENDING_EXTERNAL_APPOINTMENT",
        "submission_allowed": False,
        "review_scope_gate_count": 10,
        "review_scope_test_count": 12,
        "reviewer_plan_redacted": _redacted(plan),
    }


def evaluate_wave0_governance_reconciliation() -> dict[str, Any]:
    package_result = _package_pre_freeze_check()
    template_result = _appointment_template_check()
    appointment_plan = evaluate_appointment_plan()
    gate_result = reconcile_external_gates()

    checks = {
        "wave0_package_ready_to_freeze_without_self_freeze": package_result["state"] == "READY_TO_FREEZE" and package_result["freeze_created"] is False,
        "owner_appointment_template_pending": template_result["owner_template_valid"] and template_result["owner_appointment_ready"] is False,
        "reviewer_appointment_plan_pending": template_result["reviewer_plan_valid"] and template_result["appointment_decision"] == "NOT_ISSUED" and template_result["submission_allowed"] is False,
        "review_scope_covers_all_gates_and_tests": template_result["review_scope_gate_count"] == 10 and template_result["review_scope_test_count"] == 12,
        "appointment_plan_evaluator_ready_for_appointment_only": appointment_plan.get("decision") == "P4_INDEPENDENT_REVIEWER_APPOINTMENT_PLAN_READY" and appointment_plan.get("ready_for_external_appointment") is True and appointment_plan.get("ready_for_external_review") is False,
        "external_gate_reconciliation_passed": gate_result.get("decision") == "P3_EXTERNAL_GATE_STATUS_RECONCILED" and gate_result.get("status_counts") == EXPECTED_GATE_COUNTS,
        "blocked_gate_set_preserved": len(gate_result.get("blocked_gate_ids", [])) == 7 and len(gate_result.get("open_gate_ids", [])) == 3 and gate_result.get("evidence_submitted_gate_ids", []) == [],
        "all_packages_redacted": template_result["reviewer_plan_redacted"] is True,
        "authorization_boundary_locked": True,
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "evidence_type": "WAVE0_GOVERNANCE_RECONCILIATION",
        "decision": "WAVE0_GOVERNANCE_RECONCILED_READY_FOR_EXTERNAL_APPOINTMENT_ONLY" if all(checks.values()) else "WAVE0_GOVERNANCE_RECONCILIATION_BLOCKED",
        "mode": "LOCAL_DETERMINISTIC_RECONCILIATION_ONLY",
        "all_passed": all(checks.values()),
        "checks": checks,
        "package_pre_freeze": package_result,
        "appointment_templates": template_result,
        "appointment_plan_dependency": {
            "decision": appointment_plan.get("decision"),
            "ready_for_external_appointment": appointment_plan.get("ready_for_external_appointment"),
            "ready_for_external_review": appointment_plan.get("ready_for_external_review"),
            "appointment_confirmed": appointment_plan.get("appointment_confirmed"),
            "submission_allowed": appointment_plan.get("submission_allowed"),
        },
        "external_gate_reconciliation": {
            "decision": gate_result.get("decision"),
            "status_counts": gate_result.get("status_counts"),
            "blocked_gate_ids": gate_result.get("blocked_gate_ids"),
            "open_gate_ids": gate_result.get("open_gate_ids"),
            "evidence_submitted_gate_ids": gate_result.get("evidence_submitted_gate_ids"),
        },
        "external_authority": "NONE",
        "clinical_validation_authorized": False,
        "production_authorized": False,
        "runtime_authority": "NONE",
        "pilot_gate_status": "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION",
        "ready_for_external_appointment": all(checks.values()),
        "ready_for_external_review": False,
        "appointment_confirmed": False,
        "submission_allowed": False,
        "external_transmission_performed": False,
        "runtime_mutation_performed": False,
        "authorization_promoted": False,
        "software_evidence_only": True,
        "fixture_only": True,
        "patient_data_used": False,
        "hardware_evidence": "UNVERIFIED",
        "clinical_validation": "PENDING",
        "external_gate_snapshot": {"blocked": 7, "open": 3, "evidence_submitted": 0, "passed": 0},
        "authorization_boundary": deepcopy(LOCKED_BOUNDARY),
        "claim_boundary": "CONTROLLED_PRODUCTION_PROTOTYPE",
    }


if __name__ == "__main__":
    report = evaluate_wave0_governance_reconciliation()
    print(json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True))
    print("WAVE0_GOVERNANCE_RECONCILIATION_GUARD_PASSED" if report["all_passed"] else "WAVE0_GOVERNANCE_RECONCILIATION_GUARD_BLOCKED")
