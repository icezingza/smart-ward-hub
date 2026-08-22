"""Focused/adversarial tests for Wave 0 governance reconciliation."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace

from p3_external_gate_status_reconciliation import reconcile_external_gates
from p4_independent_reviewer_appointment_plan import appointment_plan_template
from wave0_governance import GovernanceState, build_synthetic_wave0_package
from wave0_governance_reconciliation_guard import (
    GovernanceReconciliationError,
    _appointment_template_check,
    _package_pre_freeze_check,
    evaluate_wave0_governance_reconciliation,
)
from wave0_owner_appointment_intake import template as owner_template
from wave0_owner_appointment_intake import validate_owner_appointment_intake
from p4_independent_reviewer_appointment_plan import validate_appointment_plan


def _expect_error(callback, label: str) -> None:
    try:
        callback()
    except (GovernanceReconciliationError, ValueError):
        print(f"[Wave 0 Reconciliation] {label}: PASSED")
        return
    raise AssertionError(f"{label}: unsafe mutation was accepted")


def test_reconciliation_is_ready_only_for_external_appointment():
    report = evaluate_wave0_governance_reconciliation()
    assert report["all_passed"] is True
    assert report["decision"] == "WAVE0_GOVERNANCE_RECONCILED_READY_FOR_EXTERNAL_APPOINTMENT_ONLY"
    assert report["ready_for_external_appointment"] is True
    assert report["ready_for_external_review"] is False
    assert report["appointment_confirmed"] is False
    assert report["submission_allowed"] is False
    assert report["external_transmission_performed"] is False
    assert report["authorization_promoted"] is False
    print("[Wave 0 Reconciliation] Appointment-only readiness state: PASSED")


def test_package_is_ready_to_freeze_without_self_freeze():
    result = _package_pre_freeze_check()
    assert result["state"] == GovernanceState.READY_TO_FREEZE.value
    assert result["freeze_created"] is False
    assert result["appointment_count"] >= 4
    assert result["checks"]["external_verification_pending"] is True
    print("[Wave 0 Reconciliation] Pre-freeze package remains unfrozen and pending external verification: PASSED")


def test_owner_and_reviewer_templates_remain_pending():
    owner = owner_template()
    owner_result = validate_owner_appointment_intake(owner, template_only=True)
    assert owner_result == {"valid": True, "mode": "TEMPLATE_ONLY", "execution_ready": False, "owner_appointment_ready": False}

    reviewer = appointment_plan_template()
    reviewer_result = validate_appointment_plan(reviewer)
    assert reviewer_result["valid"] is True
    assert reviewer_result["appointment_decision"] == "NOT_ISSUED"
    assert reviewer_result["submission_allowed"] is False

    summary = _appointment_template_check()
    assert summary["owner_appointment_ready"] is False
    assert summary["reviewer_appointment"] == "PENDING_EXTERNAL_APPOINTMENT"
    assert summary["appointment_decision"] == "NOT_ISSUED"
    print("[Wave 0 Reconciliation] Owner/reviewer appointment templates pending: PASSED")


def test_gate_counts_and_sets_are_preserved():
    report = evaluate_wave0_governance_reconciliation()
    gate_result = report["external_gate_reconciliation"]
    assert gate_result["decision"] == "P3_EXTERNAL_GATE_STATUS_RECONCILED"
    assert gate_result["status_counts"] == {"BLOCKED": 7, "OPEN": 3, "EVIDENCE_SUBMITTED": 0, "TOTAL": 10}
    assert len(gate_result["blocked_gate_ids"]) == 7
    assert len(gate_result["open_gate_ids"]) == 3
    assert gate_result["evidence_submitted_gate_ids"] == []
    assert report["external_gate_snapshot"] == {"blocked": 7, "open": 3, "evidence_submitted": 0, "passed": 0}
    print("[Wave 0 Reconciliation] External Gate counts and sets preserved: PASSED")


def test_unsafe_template_mutations_are_rejected():
    owner = owner_template()
    owner["roles"]["independent_verifier"] = "actor:local"
    _expect_error(lambda: validate_owner_appointment_intake(owner, template_only=True), "Owner role self-assignment")

    reviewer = appointment_plan_template()
    reviewer["appointment_decision"] = "ACCEPTED"
    _expect_error(lambda: validate_appointment_plan(reviewer), "Reviewer decision promotion")

    reviewer = appointment_plan_template()
    reviewer["submission_allowed"] = True
    _expect_error(lambda: validate_appointment_plan(reviewer), "Submission promotion")


def test_malformed_wave0_package_is_rejected_or_blocked():
    package = build_synthetic_wave0_package()
    package.appointments[0] = replace(
        package.appointments[0],
        appointment_id=package.appointments[1].appointment_id,
    )
    result = package.validate(now=package.created_at)
    assert result["state"] == GovernanceState.BLOCKED.value
    assert result["errors"]
    print("[Wave 0 Reconciliation] Duplicate appointment is blocked: PASSED")

    package = build_synthetic_wave0_package()
    package.production_authorized = True
    result = package.validate(now=package.created_at)
    assert result["state"] == GovernanceState.BLOCKED.value
    assert result["checks"]["authorization_locked"] is False
    assert "authorization boundary is not locked" in result["errors"]
    print("[Wave 0 Reconciliation] Production-authority mutation is blocked: PASSED")


def test_returned_reconciliation_mutation_cannot_change_authority_or_counts():
    report = evaluate_wave0_governance_reconciliation()
    mutated = deepcopy(report)
    mutated["ready_for_external_review"] = True
    mutated["appointment_confirmed"] = True
    mutated["authorization_boundary"]["production_authorized"] = True
    mutated["external_gate_snapshot"]["passed"] = 10
    fresh = evaluate_wave0_governance_reconciliation()
    assert fresh["ready_for_external_review"] is False
    assert fresh["appointment_confirmed"] is False
    assert fresh["authorization_boundary"]["production_authorized"] is False
    assert fresh["external_gate_snapshot"]["passed"] == 0
    assert fresh["authorization_promoted"] is False
    print("[Wave 0 Reconciliation] Returned evidence mutation cannot authorize or promote gates: PASSED")


def test_gate_source_remains_read_only():
    first = reconcile_external_gates()
    second = reconcile_external_gates()
    assert first == second
    assert second["status_counts"] == {"BLOCKED": 7, "OPEN": 3, "EVIDENCE_SUBMITTED": 0, "TOTAL": 10}
    assert second["external_transmission_performed"] is False
    assert second["runtime_mutation_performed"] is False
    print("[Wave 0 Reconciliation] External Gate source reconciliation is deterministic/read-only: PASSED")


def run() -> None:
    tests = [
        test_reconciliation_is_ready_only_for_external_appointment,
        test_package_is_ready_to_freeze_without_self_freeze,
        test_owner_and_reviewer_templates_remain_pending,
        test_gate_counts_and_sets_are_preserved,
        test_unsafe_template_mutations_are_rejected,
        test_malformed_wave0_package_is_rejected_or_blocked,
        test_returned_reconciliation_mutation_cannot_change_authority_or_counts,
        test_gate_source_remains_read_only,
    ]
    for test in tests:
        test()
    print(f"[Wave 0 Reconciliation] focused/adversarial tests: {len(tests)} PASSED")
    print("WAVE0_GOVERNANCE_RECONCILIATION_GUARD_TESTS_PASSED")


if __name__ == "__main__":
    run()
