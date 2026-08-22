"""Focused/adversarial tests for the P2-005 worker consistency gate."""
from __future__ import annotations

from copy import deepcopy
from unittest.mock import patch

from cross_package_evidence_binding import check_repository
from durable_worker_replay_contract import run_rehearsal
from p2_005_worker_control_consistency import evaluate_worker_consistency
from worker_recovery_approval import build_approval_readback
from worker_recovery_transcript import build_worker_recovery_transcript


def test_full_worker_stack_is_consistent():
    report = evaluate_worker_consistency()
    assert report["decision"] == "P2_005_WORKER_CONTROL_CONSISTENCY_VERIFIED"
    assert report["remediation_codes"] == []
    assert all(report["checks"].values())
    assert report["cross_package_binding_decision"] == "BOUND"
    assert report["durable_summary"]["restore_status"] == "SOFTWARE_RESTORE_VERIFIED"
    assert report["durable_summary"]["replay_executed"] is False
    assert report["transcript_event_count"] == 5
    assert report["approval_validation_valid"] is True
    assert report["production_ready"] is False
    print("[P2-005 Consistency] Full worker evidence chain is consistent: PASSED")


def test_durable_runtime_execution_mutation_blocks():
    durable = deepcopy(run_rehearsal())
    durable["runtime_replay_executed"] = True
    with patch("p2_005_worker_control_consistency.run_rehearsal", return_value=durable):
        report = evaluate_worker_consistency()
    assert report["decision"] == "P2_005_WORKER_CONTROL_CONSISTENCY_BLOCKED"
    assert report["checks"]["durable_fixture_replay_boundary"] is False
    assert "DURABLE_FIXTURE_BOUNDARY_INVALID" in report["remediation_codes"]
    print("[P2-005 Consistency] Durable runtime replay mutation fails closed: PASSED")


def test_transcript_integrity_mutation_blocks():
    transcript = deepcopy(build_worker_recovery_transcript())
    transcript["transcript_integrity_valid"] = False
    with patch("p2_005_worker_control_consistency.build_worker_recovery_transcript", return_value=transcript):
        report = evaluate_worker_consistency()
    assert report["decision"] == "P2_005_WORKER_CONTROL_CONSISTENCY_BLOCKED"
    assert report["checks"]["transcript_redacted_and_integrity_valid"] is False
    assert "WORKER_TRANSCRIPT_INVALID" in report["remediation_codes"]
    print("[P2-005 Consistency] Transcript integrity mutation fails closed: PASSED")


def test_approval_and_binding_mutations_block():
    approval = deepcopy(build_approval_readback())
    approval["validation"]["valid"] = False
    binding = deepcopy(check_repository())
    binding["decision"] = "RECONCILIATION_REQUIRED"
    with patch("p2_005_worker_control_consistency.build_approval_readback", return_value=approval), patch(
        "p2_005_worker_control_consistency.check_repository", return_value=binding
    ):
        report = evaluate_worker_consistency()
    assert report["decision"] == "P2_005_WORKER_CONTROL_CONSISTENCY_BLOCKED"
    assert report["checks"]["approval_readback_bound_and_separated"] is False
    assert report["checks"]["cross_package_binding_bound"] is False
    assert "WORKER_APPROVAL_READBACK_INVALID" in report["remediation_codes"]
    assert "CROSS_PACKAGE_BINDING_NOT_BOUND" in report["remediation_codes"]
    print("[P2-005 Consistency] Approval/binding mutations fail closed: PASSED")


def test_authorization_mutation_blocks_without_promotion():
    binding = deepcopy(check_repository())
    binding["authorization_boundary"]["production_authorized"] = True
    with patch("p2_005_worker_control_consistency.check_repository", return_value=binding):
        report = evaluate_worker_consistency()
    assert report["decision"] == "P2_005_WORKER_CONTROL_CONSISTENCY_BLOCKED"
    assert report["checks"]["authorization_and_claim_boundary_locked"] is False
    assert report["authorization_promoted"] is False
    assert report["production_ready"] is False
    assert "WORKER_AUTHORIZATION_BOUNDARY_MUTATED" in report["remediation_codes"]
    print("[P2-005 Consistency] Authorization mutation cannot self-promote: PASSED")


def test_redaction_mutation_blocks():
    in_process = {
        "submitted_status": "QUEUED",
        "idempotent_replay_fingerprint_equal": True,
        "success_status": "SUCCEEDED",
        "success_attempts": 1,
        "stale_job_blocked": True,
        "stale_reconciled_status": "QUEUED",
        "stale_recovered_status": "SUCCEEDED",
        "audit_chain_valid": True,
        "patient_token": "forbidden-fixture-value",
    }
    with patch("p2_005_worker_control_consistency._in_process_rehearsal", return_value=in_process):
        report = evaluate_worker_consistency()
    assert report["decision"] == "P2_005_WORKER_CONTROL_CONSISTENCY_BLOCKED"
    assert report["checks"]["redaction_boundary_clean"] is False
    assert "WORKER_EVIDENCE_REDACTION_FAILED" in report["remediation_codes"]
    print("[P2-005 Consistency] Raw identity marker fails redaction gate: PASSED")


def run() -> None:
    tests = [
        test_full_worker_stack_is_consistent,
        test_durable_runtime_execution_mutation_blocks,
        test_transcript_integrity_mutation_blocks,
        test_approval_and_binding_mutations_block,
        test_authorization_mutation_blocks_without_promotion,
        test_redaction_mutation_blocks,
    ]
    for test in tests:
        test()
    print(f"[P2-005 Consistency] focused/adversarial tests: {len(tests)} PASSED")
    print("P2_005_WORKER_CONTROL_CONSISTENCY_TESTS_PASSED")


if __name__ == "__main__":
    run()
