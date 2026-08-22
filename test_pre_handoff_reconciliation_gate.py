"""Focused/adversarial tests for the aggregate pre-handoff reconciliation gate."""

from copy import deepcopy

from pre_handoff_reconciliation_gate import (
    ReconciliationCode,
    ReconciliationDecision,
    evaluate_reconciliation,
)


BASE = {
    "read_only": True,
    "external_submission_allowed": False,
    "authorization_promoted": False,
    "runtime_mutation_performed": False,
    "external_transmission_performed": False,
    "authorization_boundary": {
        "external_authority": "NONE",
        "clinical_validation_authorized": False,
        "production_authorized": False,
        "runtime_authority": "NONE",
    },
}


def _payload(decision: str, checks: dict[str, bool] | None = None) -> dict:
    payload = deepcopy(BASE)
    payload["decision"] = decision
    payload["remediation_codes"] = []
    payload["checks"] = checks if checks is not None else {"primary": True}
    return payload


def _fixtures():
    return {
        "drift": _payload("DRIFT_FREE"),
        "manifest": _payload("MANIFEST_VALID"),
        "selection": _payload("SELECTED_SET_VALID"),
        "consistency": _payload("SELECTION_MANIFEST_CONSISTENT"),
    }


def _evaluate(**mutations):
    fixtures = _fixtures()
    for name, mutation in mutations.items():
        mutation(fixtures[name])
    return evaluate_reconciliation(**fixtures)


def test_all_child_gates_pass():
    result = _evaluate()
    assert result.decision == ReconciliationDecision.INTERNAL_HANDOFF_RECONCILIATION_READY
    assert result.remediation_codes == ()
    assert all(result.checks.values())


def test_drift_free_sentinel_is_accepted():
    result = _evaluate(drift=lambda payload: payload.update(remediation_codes=["DRIFT_FREE"]))
    assert result.decision == ReconciliationDecision.INTERNAL_HANDOFF_RECONCILIATION_READY
    assert result.remediation_codes == ()


def test_drift_child_failure_blocks_aggregate():
    result = _evaluate(drift=lambda payload: payload.update(decision="DRIFT_DETECTED", remediation_codes=["HASH_MISMATCH"]))
    assert result.decision == ReconciliationDecision.INTERNAL_HANDOFF_RECONCILIATION_BLOCKED
    assert ReconciliationCode.DRIFT_GATE_FAILED in result.remediation_codes


def test_drift_unknown_nonempty_remediation_fails_closed():
    result = _evaluate(drift=lambda payload: payload.update(remediation_codes=["UNEXPECTED_DRIFT_CODE"]))
    assert result.decision == ReconciliationDecision.INTERNAL_HANDOFF_RECONCILIATION_BLOCKED
    assert ReconciliationCode.DRIFT_GATE_FAILED in result.remediation_codes


def test_manifest_child_failure_blocks_aggregate():
    result = _evaluate(manifest=lambda payload: payload.update(decision="MANIFEST_INVALID", remediation_codes=["SNAPSHOT_HASH_MISMATCH"]))
    assert result.decision == ReconciliationDecision.INTERNAL_HANDOFF_RECONCILIATION_BLOCKED
    assert ReconciliationCode.MANIFEST_GATE_FAILED in result.remediation_codes


def test_selection_child_failure_blocks_aggregate():
    result = _evaluate(selection=lambda payload: payload.update(decision="SELECTION_BLOCKED", remediation_codes=["REQUIRED_ARTIFACT_MISSING"]))
    assert result.decision == ReconciliationDecision.INTERNAL_HANDOFF_RECONCILIATION_BLOCKED
    assert ReconciliationCode.SELECTION_GATE_FAILED in result.remediation_codes


def test_consistency_child_failure_blocks_aggregate():
    result = _evaluate(consistency=lambda payload: payload.update(decision="SELECTION_MANIFEST_INCONSISTENT", remediation_codes=["HASH_DRIFT"]))
    assert result.decision == ReconciliationDecision.INTERNAL_HANDOFF_RECONCILIATION_BLOCKED
    assert ReconciliationCode.CONSISTENCY_GATE_FAILED in result.remediation_codes


def test_authorization_and_external_mutations_block_aggregate():
    def mutate(payload):
        payload["authorization_boundary"]["production_authorized"] = True
        payload["external_submission_allowed"] = True
        payload["runtime_mutation_performed"] = True
        payload["external_transmission_performed"] = True

    result = _evaluate(manifest=mutate)
    assert result.decision == ReconciliationDecision.INTERNAL_HANDOFF_RECONCILIATION_BLOCKED
    assert ReconciliationCode.AUTHORIZATION_BOUNDARY_MUTATED in result.remediation_codes
    assert ReconciliationCode.EXTERNAL_SUBMISSION_ENABLED in result.remediation_codes
    assert ReconciliationCode.RUNTIME_MUTATION_DETECTED in result.remediation_codes
    assert ReconciliationCode.EXTERNAL_TRANSMISSION_DETECTED in result.remediation_codes


def test_read_only_mutation_blocks_aggregate():
    result = _evaluate(consistency=lambda payload: payload.update(read_only=False))
    assert result.decision == ReconciliationDecision.INTERNAL_HANDOFF_RECONCILIATION_BLOCKED
    assert ReconciliationCode.AGGREGATE_READ_ONLY_INVALID in result.remediation_codes


def test_child_nonempty_remediation_codes_fail_closed():
    result = _evaluate(selection=lambda payload: payload.update(remediation_codes=["STALE_ARTIFACT"]))
    assert result.decision == ReconciliationDecision.INTERNAL_HANDOFF_RECONCILIATION_BLOCKED
    assert ReconciliationCode.SELECTION_GATE_FAILED in result.remediation_codes


def run():
    tests = [
        value for name, value in globals().items()
        if name.startswith("test_") and callable(value)
    ]
    for test in tests:
        test()
    print(f"[Reconciliation] focused/adversarial tests: {len(tests)} PASSED")
    print("PRE_HANDOFF_RECONCILIATION_GATE_TESTS_PASSED")


if __name__ == "__main__":
    run()
