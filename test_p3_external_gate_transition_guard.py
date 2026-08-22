"""Focused/adversarial tests for the P3 external-gate transition guard."""
from __future__ import annotations

from copy import deepcopy
from unittest.mock import patch

from p3_external_gate_transition_guard import evaluate_transition_guard


def test_transition_guard_verifies_safe_dry_run():
    report = evaluate_transition_guard()
    assert report["decision"] == "P3_EXTERNAL_GATE_TRANSITION_GUARD_VERIFIED"
    assert report["remediation_codes"] == []
    assert all(report["checks"].values())
    assert report["current_external_status_counts"] == {
        "BLOCKED": 7,
        "EVIDENCE_SUBMITTED": 0,
        "OPEN": 3,
        "TOTAL": 10,
    }
    assert report["dry_run_transition"]["blocked_submission_refused"] is True
    assert report["dry_run_transition"]["empty_reopen_refused"] is True
    assert report["dry_run_transition"]["reopened_gate_submitted"] is True
    assert report["dry_run_transition"]["summary"]["ready_for_external_review"] is False
    assert report["dry_run_transition"]["external_owner_appointment"] == "PENDING_EXTERNAL_APPOINTMENT"
    print("[P3 Transition] Safe dry-run lifecycle is verified: PASSED")


def test_current_status_drift_blocks_transition_guard():
    drifted = {
        "decision": "P3_EXTERNAL_GATE_STATUS_RECONCILIATION_BLOCKED",
        "status_counts": {"BLOCKED": 6, "OPEN": 4, "EVIDENCE_SUBMITTED": 0, "TOTAL": 10},
        "ready_for_external_review": False,
        "blocked_gate_ids": [],
        "open_gate_ids": [],
    }
    with patch("p3_external_gate_transition_guard.reconcile_external_gates", return_value=drifted):
        report = evaluate_transition_guard()
    assert report["decision"] == "P3_EXTERNAL_GATE_TRANSITION_GUARD_BLOCKED"
    assert report["checks"]["current_status_reconciled"] is False
    assert "CURRENT_GATE_STATUS_NOT_RECONCILED" in report["remediation_codes"]
    print("[P3 Transition] Current external status drift blocks lifecycle guard: PASSED")


def test_transition_summary_mutation_fails_closed():
    original = evaluate_transition_guard
    del original
    from p3_external_gate_transition_guard import _simulate_transition_lifecycle

    mutated = deepcopy(_simulate_transition_lifecycle())
    mutated["summary"]["status_counts"] = {"OPEN": 8, "EVIDENCE_SUBMITTED": 1, "BLOCKED": 1}
    with patch("p3_external_gate_transition_guard._simulate_transition_lifecycle", return_value=mutated):
        report = evaluate_transition_guard()
    assert report["decision"] == "P3_EXTERNAL_GATE_TRANSITION_GUARD_BLOCKED"
    assert report["checks"]["dry_run_transition_counts_bounded"] is False
    assert "TRANSITION_COUNT_MISMATCH" in report["remediation_codes"]
    print("[P3 Transition] Transition-count mutation fails closed: PASSED")


def test_blocked_bypass_mutation_fails_closed():
    from p3_external_gate_transition_guard import _simulate_transition_lifecycle

    mutated = deepcopy(_simulate_transition_lifecycle())
    mutated["blocked_submission_refused"] = False
    with patch("p3_external_gate_transition_guard._simulate_transition_lifecycle", return_value=mutated):
        report = evaluate_transition_guard()
    assert report["decision"] == "P3_EXTERNAL_GATE_TRANSITION_GUARD_BLOCKED"
    assert report["checks"]["blocked_gate_requires_reopen_before_submit"] is False
    assert "BLOCKED_GATE_SUBMISSION_BYPASS" in report["remediation_codes"]
    print("[P3 Transition] Blocked-gate submission bypass fails closed: PASSED")


def test_pass_promotion_and_boundary_mutation_fail_closed():
    from p3_external_gate_transition_guard import _simulate_transition_lifecycle

    mutated = deepcopy(_simulate_transition_lifecycle())
    mutated["evidence_submitted_is_not_passed"] = False
    mutated["production_authorized"] = True
    with patch("p3_external_gate_transition_guard._simulate_transition_lifecycle", return_value=mutated):
        report = evaluate_transition_guard()
    assert report["decision"] == "P3_EXTERNAL_GATE_TRANSITION_GUARD_BLOCKED"
    assert report["checks"]["evidence_submission_is_not_pass"] is False
    assert report["checks"]["boundary_locked"] is False
    assert "EVIDENCE_STATUS_PROMOTED_TO_PASS" in report["remediation_codes"]
    assert "TRANSITION_AUTHORIZATION_BOUNDARY_MUTATED" in report["remediation_codes"]
    print("[P3 Transition] Pass-promotion and authorization mutation fail closed: PASSED")


def test_redaction_mutation_fails_closed():
    from p3_external_gate_transition_guard import _simulate_transition_lifecycle

    mutated = deepcopy(_simulate_transition_lifecycle())
    mutated["gate_blockers"]["GV-09"] = "HN-RAW-IDENTITY must not be exported"
    with patch("p3_external_gate_transition_guard._simulate_transition_lifecycle", return_value=mutated):
        report = evaluate_transition_guard()
    assert report["decision"] == "P3_EXTERNAL_GATE_TRANSITION_GUARD_BLOCKED"
    assert report["checks"]["lifecycle_text_redacted"] is False
    assert "TRANSITION_EVIDENCE_REDACTION_FAILED" in report["remediation_codes"]
    print("[P3 Transition] Raw identity marker fails redaction gate: PASSED")


def run() -> None:
    tests = [
        test_transition_guard_verifies_safe_dry_run,
        test_current_status_drift_blocks_transition_guard,
        test_transition_summary_mutation_fails_closed,
        test_blocked_bypass_mutation_fails_closed,
        test_pass_promotion_and_boundary_mutation_fail_closed,
        test_redaction_mutation_fails_closed,
    ]
    for test in tests:
        test()
    print(f"[P3 Transition] focused/adversarial tests: {len(tests)} PASSED")
    print("P3_EXTERNAL_GATE_TRANSITION_GUARD_TESTS_PASSED")


if __name__ == "__main__":
    run()
