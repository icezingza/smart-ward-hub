"""Focused/adversarial tests for internal pre-handoff evidence selection."""

from copy import deepcopy

from consolidated_internal_handoff_index import LOCKED_BOUNDARY, LOCKED_EXTERNAL_GATE_SNAPSHOT
from pre_handoff_evidence_selection import (
    DEPENDENCY_ORDER,
    SELECTED_SET,
    SelectionCode,
    SelectionDecision,
    evaluate_selection,
)


def _fixtures():
    freeze = {
        "freeze_status": "PASS",
        "authorization_boundary": deepcopy(LOCKED_BOUNDARY),
        "external_gate_snapshot": deepcopy(LOCKED_EXTERNAL_GATE_SNAPSHOT),
        "files": [],
    }
    packages = {}
    package_hashes = {}
    for index, (package_id, relative, _role) in enumerate(SELECTED_SET):
        if package_id in {"cross_package_binding", "consolidated_internal_handoff"}:
            payload = {"decision": "BOUND", "read_only": True}
        elif package_id == "pre_handoff_readiness":
            payload = {"decision": "INTERNAL_HANDOFF_READY", "remediation_codes": []}
        elif package_id == "pre_handoff_manifest_validation":
            payload = {"decision": "MANIFEST_VALID", "remediation_codes": []}
        else:
            payload = {"decision": "PRESENT"}
        packages[package_id] = payload
        digest = f"{index + 1:064x}"
        package_hashes[package_id] = digest
        freeze["files"].append({"path": relative, "sha256": digest})
    return freeze, packages, package_hashes


def _evaluate(*, runtime_artifacts=None, dependency_order=DEPENDENCY_ORDER):
    freeze, packages, package_hashes = _fixtures()
    return evaluate_selection(
        root=None,
        freeze=freeze,
        packages=packages,
        package_hashes=package_hashes,
        tracked_paths=set(),
        runtime_artifacts=set(runtime_artifacts or ()),
        dependency_order=dependency_order,
    )


def test_bound_selected_set_is_valid():
    result = _evaluate()
    assert result.decision == SelectionDecision.SELECTED_SET_VALID
    assert result.remediation_codes == ()
    assert all(result.checks.values())
    assert len(result.selected) == len(SELECTED_SET)
    assert [row["package_id"] for row in result.selected] == list(DEPENDENCY_ORDER)


def test_missing_artifact_blocks_selection():
    freeze, packages, hashes = _fixtures()
    packages.pop("pre_handoff_readiness")
    result = evaluate_selection(root=None, freeze=freeze, packages=packages, package_hashes=hashes, tracked_paths=set(), runtime_artifacts=set())
    assert result.decision == SelectionDecision.SELECTION_BLOCKED
    assert SelectionCode.REQUIRED_ARTIFACT_MISSING in result.remediation_codes


def test_unfrozen_artifact_blocks_selection():
    freeze, packages, hashes = _fixtures()
    freeze["files"] = [entry for entry in freeze["files"] if entry["path"] != "evals/micro_rag/evidence/pre-handoff-readiness-local.json"]
    result = evaluate_selection(root=None, freeze=freeze, packages=packages, package_hashes=hashes, tracked_paths=set(), runtime_artifacts=set())
    assert result.decision == SelectionDecision.SELECTION_BLOCKED
    assert SelectionCode.REQUIRED_ARTIFACT_NOT_FROZEN in result.remediation_codes


def test_hash_mismatch_blocks_selection():
    freeze, packages, hashes = _fixtures()
    hashes["cross_package_binding"] = "f" * 64
    result = evaluate_selection(root=None, freeze=freeze, packages=packages, package_hashes=hashes, tracked_paths=set(), runtime_artifacts=set())
    assert result.decision == SelectionDecision.SELECTION_BLOCKED
    assert SelectionCode.ARTIFACT_HASH_MISMATCH in result.remediation_codes


def test_dependency_order_mismatch_blocks_selection():
    result = _evaluate(dependency_order=tuple(reversed(DEPENDENCY_ORDER)))
    assert result.decision == SelectionDecision.SELECTION_BLOCKED
    assert SelectionCode.DEPENDENCY_ORDER_INVALID in result.remediation_codes


def test_package_decision_mismatch_blocks_selection():
    freeze, packages, hashes = _fixtures()
    packages["pre_handoff_manifest_validation"] = {"decision": "MANIFEST_INVALID", "remediation_codes": ["SNAPSHOT_HASH_MISMATCH"]}
    result = evaluate_selection(root=None, freeze=freeze, packages=packages, package_hashes=hashes, tracked_paths=set(), runtime_artifacts=set())
    assert result.decision == SelectionDecision.SELECTION_BLOCKED
    assert SelectionCode.PACKAGE_DECISION_INVALID in result.remediation_codes


def test_runtime_artifact_presence_blocks_selection():
    result = _evaluate(runtime_artifacts=["ward_hub.db-wal"])
    assert result.decision == SelectionDecision.SELECTION_BLOCKED
    assert SelectionCode.RUNTIME_ARTIFACT_SELECTED in result.remediation_codes
    assert result.excluded[0]["reason"] == "RUNTIME_ARTIFACT_EXCLUDED"


def test_freeze_boundary_and_gate_mutations_block_selection():
    freeze, packages, hashes = _fixtures()
    freeze["authorization_boundary"]["production_authorized"] = True
    freeze["external_gate_snapshot"]["passed"] = 1
    result = evaluate_selection(root=None, freeze=freeze, packages=packages, package_hashes=hashes, tracked_paths=set(), runtime_artifacts=set())
    assert result.decision == SelectionDecision.SELECTION_BLOCKED
    assert SelectionCode.FREEZE_BOUNDARY_MUTATED in result.remediation_codes
    assert SelectionCode.EXTERNAL_GATE_SNAPSHOT_MUTATED in result.remediation_codes


def run() -> None:
    tests = [
        value for name, value in globals().items()
        if name.startswith("test_") and callable(value)
    ]
    for test in tests:
        test()
    print(f"[EvidenceSelection] focused/adversarial tests: {len(tests)} PASSED")
    print("PRE_HANDOFF_EVIDENCE_SELECTION_TESTS_PASSED")


if __name__ == "__main__":
    run()
