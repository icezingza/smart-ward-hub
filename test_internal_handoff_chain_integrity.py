"""Focused and adversarial tests for the internal handoff chain integrity gate."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from internal_handoff_chain_integrity import (
    ChainCode,
    ChainDecision,
    FREEZE_PATH,
    HANDOFF_PATH,
    RECONCILIATION_PATH,
    check_repository,
    evaluate_chain,
)


ROOT = Path(__file__).resolve().parent


def _load(relative: Path) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def _fixtures() -> dict:
    return {
        "freeze": _load(FREEZE_PATH),
        "handoff": _load(HANDOFF_PATH),
        "reconciliation": _load(RECONCILIATION_PATH),
    }


def _evaluate(**mutations):
    fixtures = _fixtures()
    for name, mutation in mutations.items():
        mutation(fixtures[name])
    return evaluate_chain(**fixtures, root=ROOT)


def test_repository_is_bound():
    result = check_repository(ROOT)
    assert result["decision"] == ChainDecision.INTERNAL_HANDOFF_CHAIN_BOUND
    assert result["remediation_codes"] == []
    assert all(result["checks"].values())
    assert result["read_only"] is True
    assert result["external_submission_allowed"] is False
    assert result["authorization_promoted"] is False
    assert result["runtime_mutation_performed"] is False


def test_handoff_binding_failure_blocks():
    result = _evaluate(handoff=lambda payload: payload.update(decision="RECONCILIATION_REQUIRED"))
    assert result.decision == ChainDecision.INTERNAL_HANDOFF_CHAIN_BLOCKED
    assert ChainCode.HANDOFF_INDEX_NOT_BOUND in result.remediation_codes


def test_reconciliation_failure_blocks():
    result = _evaluate(reconciliation=lambda payload: payload.update(decision="INTERNAL_HANDOFF_RECONCILIATION_BLOCKED"))
    assert result.decision == ChainDecision.INTERNAL_HANDOFF_CHAIN_BLOCKED
    assert ChainCode.RECONCILIATION_NOT_READY in result.remediation_codes


def test_reconciliation_child_drift_blocks():
    def mutate(payload):
        payload["child_decisions"]["selection"] = "SELECTION_BLOCKED"

    result = _evaluate(reconciliation=mutate)
    assert result.decision == ChainDecision.INTERNAL_HANDOFF_CHAIN_BLOCKED
    assert ChainCode.RECONCILIATION_CHILD_DRIFT in result.remediation_codes


def test_frozen_artifact_hash_mismatch_blocks():
    def mutate(payload):
        for entry in payload["files"]:
            if entry["path"] == HANDOFF_PATH.as_posix():
                entry["sha256"] = "0" * 64

    result = _evaluate(freeze=mutate)
    assert result.decision == ChainDecision.INTERNAL_HANDOFF_CHAIN_BLOCKED
    assert ChainCode.ARTIFACT_HASH_MISMATCH in result.remediation_codes


def test_authorization_boundary_mutation_blocks():
    result = _evaluate(handoff=lambda payload: payload["authorization_boundary"].update(production_authorized=True))
    assert result.decision == ChainDecision.INTERNAL_HANDOFF_CHAIN_BLOCKED
    assert ChainCode.CHAIN_EXTERNAL_LOCK_INVALID in result.remediation_codes


def test_external_gate_snapshot_mutation_blocks():
    result = _evaluate(reconciliation=lambda payload: payload["external_gate_snapshot"].update(blocked=6))
    assert result.decision == ChainDecision.INTERNAL_HANDOFF_CHAIN_BLOCKED
    assert ChainCode.EXTERNAL_GATE_SNAPSHOT_MUTATED in result.remediation_codes


def test_non_ancestor_source_revision_blocks():
    result = _evaluate(handoff=lambda payload: payload.update(source_revision="f" * 40))
    assert result.decision == ChainDecision.INTERNAL_HANDOFF_CHAIN_BLOCKED
    assert ChainCode.SOURCE_REVISION_NOT_ANCESTOR in result.remediation_codes


def test_invalid_source_revision_blocks():
    result = _evaluate(reconciliation=lambda payload: payload.update(freeze_source_revision="not-a-revision"))
    assert result.decision == ChainDecision.INTERNAL_HANDOFF_CHAIN_BLOCKED
    assert ChainCode.SOURCE_REVISION_INVALID in result.remediation_codes


def test_input_mutation_isolated():
    fixtures = _fixtures()
    before = deepcopy(fixtures)
    result = evaluate_chain(**fixtures, root=ROOT)
    assert result.decision == ChainDecision.INTERNAL_HANDOFF_CHAIN_BOUND
    assert fixtures == before


def test_no_execution_flags_can_be_enabled():
    def mutate(payload):
        payload["external_submission_allowed"] = True
        payload["authorization_promoted"] = True
        payload["runtime_mutation_performed"] = True

    result = _evaluate(reconciliation=mutate)
    assert result.decision == ChainDecision.INTERNAL_HANDOFF_CHAIN_BLOCKED
    assert ChainCode.CHAIN_EXTERNAL_LOCK_INVALID in result.remediation_codes


def run() -> None:
    tests = [
        value for name, value in globals().items()
        if name.startswith("test_") and callable(value)
    ]
    for test in tests:
        test()
    print(f"[Chain] focused/adversarial tests: {len(tests)} PASSED")
    print("INTERNAL_HANDOFF_CHAIN_INTEGRITY_TESTS_PASSED")


if __name__ == "__main__":
    run()
