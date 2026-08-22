"""Focused/adversarial tests for the P4 reviewer appointment plan."""
from __future__ import annotations

from copy import deepcopy
from unittest.mock import patch

from p4_independent_reviewer_appointment_plan import (
    appointment_plan_template,
    evaluate_appointment_plan,
    validate_appointment_plan,
)


def test_appointment_plan_is_ready_only_for_external_appointment():
    report = evaluate_appointment_plan()
    assert report["decision"] == "P4_INDEPENDENT_REVIEWER_APPOINTMENT_PLAN_READY"
    assert report["remediation_codes"] == []
    assert all(report["checks"].values())
    assert report["ready_for_external_appointment"] is True
    assert report["ready_for_external_review"] is False
    assert report["appointment_confirmed"] is False
    assert report["submission_allowed"] is False
    assert report["plan"]["appointment_decision"] == "NOT_ISSUED"
    assert report["plan"]["review_scope_gate_ids"] == [f"GV-{index:02d}" for index in range(1, 11)]
    assert report["plan"]["review_scope_test_ids"] == [f"T-{index:02d}" for index in range(1, 13)]
    print("[P4 Appointment] Plan is ready only for external appointment: PASSED")


def test_appointment_self_issue_fails_closed():
    plan = appointment_plan_template()
    plan["appointment_decision"] = "ISSUED"
    try:
        validate_appointment_plan(plan)
    except ValueError as exc:
        assert "appointment decision must remain not issued" in str(exc)
    else:
        raise AssertionError("self-issued appointment was accepted")
    print("[P4 Appointment] Self-issued appointment fails closed: PASSED")


def test_scope_mutation_fails_closed():
    plan = appointment_plan_template()
    plan["review_scope_gate_ids"] = plan["review_scope_gate_ids"][:-1]
    try:
        validate_appointment_plan(plan)
    except ValueError as exc:
        assert "Gate scope mismatch" in str(exc)
    else:
        raise AssertionError("incomplete Gate scope was accepted")
    print("[P4 Appointment] Incomplete scope fails closed: PASSED")


def test_role_separation_mutation_fails_closed():
    plan = appointment_plan_template()
    plan["role_separation"]["stop_and_rollback_must_differ"] = False
    try:
        validate_appointment_plan(plan)
    except ValueError as exc:
        assert "stop/rollback separation" in str(exc)
    else:
        raise AssertionError("role separation mutation was accepted")
    print("[P4 Appointment] Role separation mutation fails closed: PASSED")


def test_reviewer_dependency_mutation_fails_closed():
    dependency = {
        "decision": "P4_INDEPENDENT_REVIEWER_HANDOFF_BLOCKED",
        "ready_for_external_appointment": False,
        "ready_for_external_review": False,
        "submission_allowed": False,
    }
    with patch("p4_independent_reviewer_appointment_plan.evaluate_reviewer_handoff_readiness", return_value=dependency):
        report = evaluate_appointment_plan()
    assert report["decision"] == "P4_INDEPENDENT_REVIEWER_APPOINTMENT_PLAN_BLOCKED"
    assert report["checks"]["reviewer_handoff_dependency_ready"] is False
    assert "REVIEWER_HANDOFF_DEPENDENCY_NOT_READY" in report["remediation_codes"]
    print("[P4 Appointment] Reviewer dependency mutation fails closed: PASSED")


def test_authorization_mutation_fails_closed():
    plan = appointment_plan_template()
    plan["production_authorized"] = True
    try:
        validate_appointment_plan(plan)
    except ValueError as exc:
        assert "production_authorized must remain false" in str(exc)
    else:
        raise AssertionError("production authorization mutation was accepted")
    print("[P4 Appointment] Authorization mutation fails closed: PASSED")


def test_redaction_mutation_fails_closed():
    plan = appointment_plan_template()
    plan["acceptance_conditions"][0] = "HN-RAW-IDENTITY must not be included"
    try:
        validate_appointment_plan(plan)
    except ValueError as exc:
        assert "unsafe identity" in str(exc)
    else:
        raise AssertionError("raw identity marker was accepted")
    print("[P4 Appointment] Redaction mutation fails closed: PASSED")


def run() -> None:
    tests = [
        test_appointment_plan_is_ready_only_for_external_appointment,
        test_appointment_self_issue_fails_closed,
        test_scope_mutation_fails_closed,
        test_role_separation_mutation_fails_closed,
        test_reviewer_dependency_mutation_fails_closed,
        test_authorization_mutation_fails_closed,
        test_redaction_mutation_fails_closed,
    ]
    for test in tests:
        test()
    print(f"[P4 Appointment] focused/adversarial tests: {len(tests)} PASSED")
    print("P4_INDEPENDENT_REVIEWER_APPOINTMENT_PLAN_TESTS_PASSED")


if __name__ == "__main__":
    run()
