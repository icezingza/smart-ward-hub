"""Focused/adversarial tests for the internal pre-handoff readiness check."""

from copy import deepcopy
from pathlib import Path

from consolidated_internal_handoff_index import LOCKED_BOUNDARY, LOCKED_EXTERNAL_GATE_SNAPSHOT
from freeze_integrity_monitor import DriftDecision
from pre_handoff_readiness import (
    HandoffCode,
    HandoffDecision,
    check_pre_handoff,
    evaluate_pre_handoff,
)


ROOT = Path(__file__).resolve().parent


def _fixtures():
    drift = {
        "decision": "DRIFT_FREE",
        "remediation_codes": ["DRIFT_FREE"],
        "read_only": True,
        "external_transmission_performed": False,
    }
    handoff = {
        "decision": "BOUND",
        "remediation_codes": ["HANDOFF_INDEX_BOUND"],
        "read_only": True,
        "external_submission_allowed": False,
        "authorization_promoted": False,
        "runtime_mutation_performed": False,
        "authorization_boundary": deepcopy(LOCKED_BOUNDARY),
        "claim_boundary": {
            "status": "CONTROLLED_PRODUCTION_PROTOTYPE",
            "functional_verification": "PASSED",
            "clinical_validation": "PENDING",
            "production_ready": False,
        },
        "freeze": {"external_gate_snapshot": deepcopy(LOCKED_EXTERNAL_GATE_SNAPSHOT)},
    }
    return drift, handoff


def test_current_repository_is_safe_during_workspace_drift():
    report = check_pre_handoff(ROOT)
    assert report["decision"] in {
        HandoffDecision.INTERNAL_HANDOFF_READY,
        HandoffDecision.INTERNAL_HANDOFF_BLOCKED,
    }
    if report["decision"] == HandoffDecision.INTERNAL_HANDOFF_READY:
        assert report["remediation_codes"] == []
        assert all(report["checks"].values())
    else:
        assert "FREEZE_DRIFT_DETECTED" in report["remediation_codes"]
    assert report["external_submission_allowed"] is False
    assert report["authorization_promoted"] is False
    assert report["runtime_mutation_performed"] is False
    assert report["claim_boundary"]["production_ready"] is False
    assert report["claim_boundary"]["clinical_validation"] == "PENDING"


def test_ready_fixture_allows_internal_handoff():
    drift, handoff = _fixtures()
    result = evaluate_pre_handoff(drift=drift, handoff=handoff)
    assert result.decision == HandoffDecision.INTERNAL_HANDOFF_READY
    assert result.remediation_codes == ()
    assert all(result.checks.values())


def test_drift_blocks_internal_handoff():
    drift, handoff = _fixtures()
    drift["decision"] = "DRIFT_DETECTED"
    drift["remediation_codes"] = ["FREEZE_TRACKED_FILE_HASH_MISMATCH"]
    result = evaluate_pre_handoff(drift=drift, handoff=handoff)
    assert result.decision == HandoffDecision.INTERNAL_HANDOFF_BLOCKED
    assert HandoffCode.FREEZE_DRIFT_DETECTED in result.remediation_codes
    assert result.checks["freeze_drift_free"] is False


def test_unbound_index_blocks_internal_handoff():
    drift, handoff = _fixtures()
    handoff["decision"] = "RECONCILIATION_REQUIRED"
    handoff["remediation_codes"] = ["HANDOFF_INDEX_RECONCILIATION_REQUIRED"]
    result = evaluate_pre_handoff(drift=drift, handoff=handoff)
    assert result.decision == HandoffDecision.INTERNAL_HANDOFF_BLOCKED
    assert HandoffCode.HANDOFF_INDEX_NOT_BOUND in result.remediation_codes


def test_authorization_mutation_blocks_internal_handoff():
    drift, handoff = _fixtures()
    handoff["authorization_boundary"]["production_authorized"] = True
    result = evaluate_pre_handoff(drift=drift, handoff=handoff)
    assert result.decision == HandoffDecision.INTERNAL_HANDOFF_BLOCKED
    assert HandoffCode.AUTHORIZATION_BOUNDARY_MUTATED in result.remediation_codes


def test_claim_mutation_blocks_internal_handoff():
    drift, handoff = _fixtures()
    handoff["claim_boundary"]["production_ready"] = True
    result = evaluate_pre_handoff(drift=drift, handoff=handoff)
    assert result.decision == HandoffDecision.INTERNAL_HANDOFF_BLOCKED
    assert HandoffCode.CLAIM_BOUNDARY_MUTATED in result.remediation_codes


def test_external_gate_mutation_blocks_internal_handoff():
    drift, handoff = _fixtures()
    handoff["freeze"]["external_gate_snapshot"]["passed"] = 1
    result = evaluate_pre_handoff(drift=drift, handoff=handoff)
    assert result.decision == HandoffDecision.INTERNAL_HANDOFF_BLOCKED
    assert HandoffCode.EXTERNAL_GATE_SNAPSHOT_MUTATED in result.remediation_codes


def test_external_submission_enablement_blocks_internal_handoff():
    drift, handoff = _fixtures()
    handoff["external_submission_allowed"] = True
    result = evaluate_pre_handoff(drift=drift, handoff=handoff)
    assert result.decision == HandoffDecision.INTERNAL_HANDOFF_BLOCKED
    assert HandoffCode.EXTERNAL_SUBMISSION_FORBIDDEN in result.remediation_codes


def test_runtime_mutation_or_transmission_blocks_internal_handoff():
    drift, handoff = _fixtures()
    handoff["runtime_mutation_performed"] = True
    drift["external_transmission_performed"] = True
    result = evaluate_pre_handoff(drift=drift, handoff=handoff)
    assert result.decision == HandoffDecision.INTERNAL_HANDOFF_BLOCKED
    assert HandoffCode.RUNTIME_MUTATION_DETECTED in result.remediation_codes
    assert HandoffCode.READ_ONLY_CONTRACT_INVALID in result.remediation_codes


def run() -> None:
    tests = [
        value for name, value in globals().items()
        if name.startswith("test_") and callable(value)
    ]
    for test in tests:
        test()
    print(f"[PreHandoff] focused/adversarial tests: {len(tests)} PASSED")
    print("PRE_HANDOFF_READINESS_TESTS_PASSED")


if __name__ == "__main__":
    run()
