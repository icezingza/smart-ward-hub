"""Focused/adversarial tests for the P4 blocked-gate unblock readiness control."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from p4_blocked_gate_unblock_readiness import (
    BLOCKER_PATH,
    ROOT,
    _load_json,
    evaluate_p4_blocked_gate_readiness,
)


def test_seven_blocked_gates_are_complete_and_locked():
    report = evaluate_p4_blocked_gate_readiness()
    assert report["decision"] == "P4_BLOCKED_GATE_UNBLOCK_READINESS_RECONCILED"
    assert report["remediation_codes"] == []
    assert all(report["checks"].values())
    assert report["blocked_gate_ids"] == ["GV-01", "GV-03", "GV-04", "GV-06", "GV-07", "GV-08", "GV-09"]
    assert report["status_counts"] == {"BLOCKED": 7, "EVIDENCE_SUBMITTED": 0, "OPEN": 3, "TOTAL": 10}
    assert len(report["records"]) == 7
    assert all(record["status"] == "BLOCKED" for record in report["records"])
    assert all(record["external_evidence_status"] == "NOT_VERIFIED" for record in report["records"])
    assert all(record["local_software_evidence_does_not_unlock"] is True for record in report["records"])
    assert report["unblock_authorized"] is False
    assert report["ready_for_external_review"] is False
    print("[P4 Blockers] Seven blocked gates and unlock records are reconciled: PASSED")


def test_missing_blocker_record_fails_closed():
    blocker_report = deepcopy(_load_json(ROOT / BLOCKER_PATH))
    blocker_report["blockers"] = blocker_report["blockers"][:-1]

    def load_mutated(path: Path):
        if path.name == BLOCKER_PATH.name:
            return blocker_report
        return _load_json(path)

    with patch("p4_blocked_gate_unblock_readiness._load_json", side_effect=load_mutated):
        report = evaluate_p4_blocked_gate_readiness()
    assert report["decision"] == "P4_BLOCKED_GATE_UNBLOCK_READINESS_BLOCKED"
    assert report["checks"]["exactly_seven_blocker_records"] is False
    assert "BLOCKED_GATE_RECORD_SET_MISMATCH" in report["remediation_codes"]
    print("[P4 Blockers] Missing blocker record fails closed: PASSED")


def test_required_external_evidence_mutation_fails_closed():
    blocker_report = deepcopy(_load_json(ROOT / BLOCKER_PATH))
    blocker_report["blockers"][0]["required_external_evidence"] = []

    def load_mutated(path: Path):
        if path.name == BLOCKER_PATH.name:
            return blocker_report
        return _load_json(path)

    with patch("p4_blocked_gate_unblock_readiness._load_json", side_effect=load_mutated):
        report = evaluate_p4_blocked_gate_readiness()
    assert report["decision"] == "P4_BLOCKED_GATE_UNBLOCK_READINESS_BLOCKED"
    assert report["checks"]["all_blocked_records_complete"] is False
    assert "BLOCKED_GATE_UNBLOCK_CONDITION_INCOMPLETE" in report["remediation_codes"]
    print("[P4 Blockers] Evidence requirement mutation fails closed: PASSED")


def test_external_verification_status_mutation_fails_closed():
    blocker_report = deepcopy(_load_json(ROOT / BLOCKER_PATH))
    blocker_report["blockers"][0]["external_evidence_status"] = "VERIFIED"

    def load_mutated(path: Path):
        if path.name == BLOCKER_PATH.name:
            return blocker_report
        return _load_json(path)

    with patch("p4_blocked_gate_unblock_readiness._load_json", side_effect=load_mutated):
        report = evaluate_p4_blocked_gate_readiness()
    assert report["decision"] == "P4_BLOCKED_GATE_UNBLOCK_READINESS_BLOCKED"
    assert report["checks"]["all_blocked_records_complete"] is False
    assert "BLOCKED_GATE_UNBLOCK_CONDITION_INCOMPLETE" in report["remediation_codes"]
    print("[P4 Blockers] External evidence status mutation fails closed: PASSED")


def test_authorization_mutation_fails_closed_without_unblock():
    blocker_report = deepcopy(_load_json(ROOT / BLOCKER_PATH))
    blocker_report["production_authorized"] = True

    def load_mutated(path: Path):
        if path.name == BLOCKER_PATH.name:
            return blocker_report
        return _load_json(path)

    with patch("p4_blocked_gate_unblock_readiness._load_json", side_effect=load_mutated):
        report = evaluate_p4_blocked_gate_readiness()
    assert report["decision"] == "P4_BLOCKED_GATE_UNBLOCK_READINESS_BLOCKED"
    assert report["checks"]["authorization_boundary_locked"] is False
    assert "P4_AUTHORIZATION_BOUNDARY_MUTATED" in report["remediation_codes"]
    assert report["unblock_authorized"] is False
    assert report["production_ready"] is False
    print("[P4 Blockers] Authorization mutation cannot unlock a gate: PASSED")


def test_redaction_and_freeze_mutations_fail_closed():
    blocker_report = deepcopy(_load_json(ROOT / BLOCKER_PATH))
    blocker_report["blockers"][0]["blocker_reason"] = "HN-RAW-IDENTITY must not be exported"

    def load_mutated(path: Path):
        if path.name == BLOCKER_PATH.name:
            return blocker_report
        return _load_json(path)

    with patch("p4_blocked_gate_unblock_readiness._load_json", side_effect=load_mutated), patch(
        "p4_blocked_gate_unblock_readiness._freeze_hash", return_value="0" * 64
    ):
        report = evaluate_p4_blocked_gate_readiness()
    assert report["decision"] == "P4_BLOCKED_GATE_UNBLOCK_READINESS_BLOCKED"
    assert report["checks"]["all_records_redacted"] is False
    assert report["checks"]["blocker_report_freeze_bound"] is False
    assert "BLOCKED_GATE_REDACTION_FAILED" in report["remediation_codes"]
    assert "P4_BLOCKER_FREEZE_BINDING_MISSING" in report["remediation_codes"]
    print("[P4 Blockers] Redaction and freeze mutations fail closed: PASSED")


def run() -> None:
    tests = [
        test_seven_blocked_gates_are_complete_and_locked,
        test_missing_blocker_record_fails_closed,
        test_required_external_evidence_mutation_fails_closed,
        test_external_verification_status_mutation_fails_closed,
        test_authorization_mutation_fails_closed_without_unblock,
        test_redaction_and_freeze_mutations_fail_closed,
    ]
    for test in tests:
        test()
    print(f"[P4 Blockers] focused/adversarial tests: {len(tests)} PASSED")
    print("P4_BLOCKED_GATE_UNBLOCK_READINESS_TESTS_PASSED")


if __name__ == "__main__":
    run()
