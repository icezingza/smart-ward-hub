"""Focused/adversarial tests for the P3 external-gate reconciliation control."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from p3_external_gate_status_reconciliation import (
    BLOCKER_PATH,
    FREEZE_PATH,
    MATRIX_PATH,
    ROOT,
    _load_json,
    _parse_matrix,
    reconcile_external_gates,
)


def test_current_ten_gate_status_is_reconciled():
    report = reconcile_external_gates()
    assert report["decision"] == "P3_EXTERNAL_GATE_STATUS_RECONCILED"
    assert report["remediation_codes"] == []
    assert report["status_counts"] == {"BLOCKED": 7, "OPEN": 3, "EVIDENCE_SUBMITTED": 0, "TOTAL": 10}
    assert report["blocked_gate_ids"] == ["GV-01", "GV-03", "GV-04", "GV-06", "GV-07", "GV-08", "GV-09"]
    assert report["open_gate_ids"] == ["GV-02", "GV-05", "GV-10"]
    assert all(report["checks"].values())
    assert report["ready_for_external_review"] is False
    assert report["production_ready"] is False
    print("[P3 Gates] Current 10-gate matrix reconciles to 7 BLOCKED / 3 OPEN: PASSED")


def test_matrix_status_mutation_fails_closed():
    matrix = deepcopy(_parse_matrix(ROOT / MATRIX_PATH))
    matrix["GV-02"]["status"] = "BLOCKED"
    with patch("p3_external_gate_status_reconciliation._parse_matrix", return_value=matrix):
        report = reconcile_external_gates()
    assert report["decision"] == "P3_EXTERNAL_GATE_STATUS_RECONCILIATION_BLOCKED"
    assert report["checks"]["status_counts_match_locked_summary"] is False
    assert "GATE_STATUS_COUNT_MISMATCH" in report["remediation_codes"]
    print("[P3 Gates] Matrix status mutation fails closed: PASSED")


def test_blocker_set_mutation_fails_closed():
    blocker_report = deepcopy(_load_json(ROOT / BLOCKER_PATH))
    blocker_report["blockers"] = blocker_report["blockers"][:-1]

    def load_mutated(path: Path):
        if path.name == BLOCKER_PATH.name:
            return blocker_report
        return _load_json(path)

    with patch("p3_external_gate_status_reconciliation._load_json", side_effect=load_mutated):
        report = reconcile_external_gates()
    assert report["decision"] == "P3_EXTERNAL_GATE_STATUS_RECONCILIATION_BLOCKED"
    assert report["checks"]["blocked_ids_match_blocker_report"] is False
    assert "BLOCKER_SET_MISMATCH" in report["remediation_codes"]
    print("[P3 Gates] Blocker set mutation fails closed: PASSED")


def test_freeze_hash_mutation_fails_closed():
    with patch("p3_external_gate_status_reconciliation._freeze_hash", return_value="0" * 64):
        report = reconcile_external_gates()
    assert report["decision"] == "P3_EXTERNAL_GATE_STATUS_RECONCILIATION_BLOCKED"
    assert report["checks"]["matrix_bound_to_freeze"] is False
    assert report["checks"]["blocker_report_bound_to_freeze"] is False
    assert "GATE_MATRIX_FREEZE_HASH_MISMATCH" in report["remediation_codes"]
    assert "BLOCKER_REPORT_FREEZE_HASH_MISMATCH" in report["remediation_codes"]
    print("[P3 Gates] Freeze/hash mutation fails closed: PASSED")


def test_redaction_mutation_fails_closed():
    matrix = deepcopy(_parse_matrix(ROOT / MATRIX_PATH))
    matrix["GV-05"]["evidence_and_blocker"] = "HN-RAW-IDENTITY must never be accepted"
    with patch("p3_external_gate_status_reconciliation._parse_matrix", return_value=matrix):
        report = reconcile_external_gates()
    assert report["decision"] == "P3_EXTERNAL_GATE_STATUS_RECONCILIATION_BLOCKED"
    assert report["checks"]["all_gate_text_is_redacted"] is False
    assert "GATE_STATUS_REDACTION_FAILED" in report["remediation_codes"]
    print("[P3 Gates] Raw identity marker fails redaction gate: PASSED")


def test_authorization_mutation_fails_closed_without_promotion():
    blocker_report = deepcopy(_load_json(ROOT / BLOCKER_PATH))
    blocker_report["clinical_validation_authorized"] = True

    def load_mutated(path: Path):
        if path.name == BLOCKER_PATH.name:
            return blocker_report
        return _load_json(path)

    with patch("p3_external_gate_status_reconciliation._load_json", side_effect=load_mutated):
        report = reconcile_external_gates()
    assert report["decision"] == "P3_EXTERNAL_GATE_STATUS_RECONCILIATION_BLOCKED"
    assert report["checks"]["authorization_boundary_locked"] is False
    assert "EXTERNAL_GATE_AUTHORIZATION_BOUNDARY_MUTATED" in report["remediation_codes"]
    assert report["production_authorized"] is False
    assert report["authorization_promoted"] is False
    print("[P3 Gates] Authorization mutation cannot self-promote: PASSED")


def run() -> None:
    tests = [
        test_current_ten_gate_status_is_reconciled,
        test_matrix_status_mutation_fails_closed,
        test_blocker_set_mutation_fails_closed,
        test_freeze_hash_mutation_fails_closed,
        test_redaction_mutation_fails_closed,
        test_authorization_mutation_fails_closed_without_promotion,
    ]
    for test in tests:
        test()
    print(f"[P3 Gates] focused/adversarial tests: {len(tests)} PASSED")
    print("P3_EXTERNAL_GATE_STATUS_RECONCILIATION_TESTS_PASSED")


if __name__ == "__main__":
    run()
