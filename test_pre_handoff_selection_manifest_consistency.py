"""Focused/adversarial tests for selection-to-manifest consistency."""

from copy import deepcopy

from consolidated_internal_handoff_index import LOCKED_BOUNDARY, LOCKED_EXTERNAL_GATE_SNAPSHOT
from pre_handoff_evidence_selection import DEPENDENCY_ORDER, SELECTED_SET
from pre_handoff_selection_manifest_consistency import (
    ConsistencyCode,
    ConsistencyDecision,
    evaluate_consistency,
)


def _fixtures():
    selected = []
    freeze_files = []
    for index, (package_id, path, role) in enumerate(SELECTED_SET):
        digest = f"{index + 1:064x}"
        status = {
            "cross_package_binding": "BOUND",
            "consolidated_internal_handoff": "BOUND",
            "pre_handoff_readiness": "INTERNAL_HANDOFF_READY",
            "pre_handoff_manifest_validation": "MANIFEST_VALID",
        }.get(package_id, "PRESENT")
        selected.append({"package_id": package_id, "path": path, "role": role, "sha256": digest, "status": status})
        freeze_files.append({"path": path, "sha256": digest})
    selected_snapshot = {
        "decision": "SELECTED_SET_VALID",
        "remediation_codes": [],
        "dependency_order": list(DEPENDENCY_ORDER),
        "selected": selected,
        "authorization_boundary": deepcopy(LOCKED_BOUNDARY),
        "claim_boundary": {"status": "CONTROLLED_PRODUCTION_PROTOTYPE", "clinical_validation": "PENDING", "production_ready": False},
        "external_gate_snapshot": deepcopy(LOCKED_EXTERNAL_GATE_SNAPSHOT),
        "external_submission_allowed": False,
        "runtime_mutation_performed": False,
        "external_transmission_performed": False,
        "read_only": True,
        "freeze_source_revision": "a" * 40,
    }
    readiness = {
        "decision": "INTERNAL_HANDOFF_READY",
        "remediation_codes": [],
        "source_revision": "b" * 40,
        "freeze_source_revision": "b" * 40,
        "checks": {"freeze_drift_free": True},
        "authorization_boundary": deepcopy(LOCKED_BOUNDARY),
        "claim_boundary": {"status": "CONTROLLED_PRODUCTION_PROTOTYPE", "clinical_validation": "PENDING", "production_ready": False},
        "external_gate_snapshot": deepcopy(LOCKED_EXTERNAL_GATE_SNAPSHOT),
        "external_submission_allowed": False,
        "runtime_mutation_performed": False,
        "external_transmission_performed": False,
        "read_only": True,
    }
    manifest = {
        "decision": "MANIFEST_VALID",
        "remediation_codes": [],
        "snapshot_relative": "evals/micro_rag/evidence/pre-handoff-readiness-local.json",
        "snapshot_source_revision": "b" * 40,
        "source_revision": "c" * 40,
        "freeze_source_revision": "c" * 40,
        "authorization_boundary": deepcopy(LOCKED_BOUNDARY),
        "claim_boundary": {"status": "CONTROLLED_PRODUCTION_PROTOTYPE", "clinical_validation": "PENDING", "production_ready": False},
        "external_gate_snapshot": deepcopy(LOCKED_EXTERNAL_GATE_SNAPSHOT),
        "external_submission_allowed": False,
        "runtime_mutation_performed": False,
        "external_transmission_performed": False,
        "read_only": True,
    }
    freeze = {
        "freeze_status": "PASS",
        "source_revision": "d" * 40,
        "origin_main_revision": "d" * 40,
        "authorization_boundary": deepcopy(LOCKED_BOUNDARY),
        "external_gate_snapshot": deepcopy(LOCKED_EXTERNAL_GATE_SNAPSHOT),
        "files": freeze_files,
    }
    current_selection = {"selected": deepcopy(selected)}
    return selected_snapshot, readiness, manifest, freeze, current_selection


def _evaluate():
    selection, readiness, manifest, freeze, current = _fixtures()
    return evaluate_consistency(
        selection=selection,
        readiness=readiness,
        manifest=manifest,
        freeze=freeze,
        current_selection=current,
        lineage_valid=True,
    )


def test_consistent_chain_is_valid():
    result = _evaluate()
    assert result.decision == ConsistencyDecision.CONSISTENT
    assert result.remediation_codes == ()
    assert all(result.checks.values())


def test_selection_order_mismatch_is_blocked():
    selection, readiness, manifest, freeze, current = _fixtures()
    selection["dependency_order"] = list(reversed(DEPENDENCY_ORDER))
    result = evaluate_consistency(selection=selection, readiness=readiness, manifest=manifest, freeze=freeze, current_selection=current, lineage_valid=True)
    assert result.decision == ConsistencyDecision.INCONSISTENT
    assert ConsistencyCode.SELECTION_DEPENDENCY_ORDER_MISMATCH in result.remediation_codes


def test_selected_artifact_hash_drift_is_blocked():
    selection, readiness, manifest, freeze, current = _fixtures()
    selection["selected"][0]["sha256"] = "f" * 64
    result = evaluate_consistency(selection=selection, readiness=readiness, manifest=manifest, freeze=freeze, current_selection=current, lineage_valid=True)
    assert result.decision == ConsistencyDecision.INCONSISTENT
    assert ConsistencyCode.SELECTION_ARTIFACT_HASH_MISMATCH in result.remediation_codes


def test_manifest_readiness_binding_mismatch_is_blocked():
    selection, readiness, manifest, freeze, current = _fixtures()
    manifest["snapshot_source_revision"] = "e" * 40
    result = evaluate_consistency(selection=selection, readiness=readiness, manifest=manifest, freeze=freeze, current_selection=current, lineage_valid=True)
    assert result.decision == ConsistencyDecision.INCONSISTENT
    assert ConsistencyCode.MANIFEST_READINESS_BINDING_MISMATCH in result.remediation_codes


def test_readiness_decision_mismatch_is_blocked():
    selection, readiness, manifest, freeze, current = _fixtures()
    readiness["decision"] = "INTERNAL_HANDOFF_BLOCKED"
    readiness["remediation_codes"] = ["FREEZE_DRIFT_DETECTED"]
    result = evaluate_consistency(selection=selection, readiness=readiness, manifest=manifest, freeze=freeze, current_selection=current, lineage_valid=True)
    assert result.decision == ConsistencyDecision.INCONSISTENT
    assert ConsistencyCode.READINESS_DECISION_MISMATCH in result.remediation_codes


def test_lineage_mismatch_is_blocked():
    result = _evaluate()
    assert result.decision == ConsistencyDecision.CONSISTENT
    selection, readiness, manifest, freeze, current = _fixtures()
    result = evaluate_consistency(selection=selection, readiness=readiness, manifest=manifest, freeze=freeze, current_selection=current, lineage_valid=False)
    assert result.decision == ConsistencyDecision.INCONSISTENT
    assert ConsistencyCode.SELECTION_FREEZE_LINEAGE_MISMATCH in result.remediation_codes


def test_boundary_mutation_is_blocked():
    selection, readiness, manifest, freeze, current = _fixtures()
    manifest["authorization_boundary"]["production_authorized"] = True
    manifest["external_gate_snapshot"]["passed"] = 1
    result = evaluate_consistency(selection=selection, readiness=readiness, manifest=manifest, freeze=freeze, current_selection=current, lineage_valid=True)
    assert result.decision == ConsistencyDecision.INCONSISTENT
    assert ConsistencyCode.AUTHORIZATION_BOUNDARY_MISMATCH in result.remediation_codes
    assert ConsistencyCode.EXTERNAL_GATE_BOUNDARY_MISMATCH in result.remediation_codes


def test_submission_runtime_transmission_mutations_are_blocked():
    selection, readiness, manifest, freeze, current = _fixtures()
    readiness["external_submission_allowed"] = True
    manifest["runtime_mutation_performed"] = True
    selection["external_transmission_performed"] = True
    result = evaluate_consistency(selection=selection, readiness=readiness, manifest=manifest, freeze=freeze, current_selection=current, lineage_valid=True)
    assert result.decision == ConsistencyDecision.INCONSISTENT
    assert ConsistencyCode.EXTERNAL_SUBMISSION_ENABLED in result.remediation_codes
    assert ConsistencyCode.RUNTIME_MUTATION_DETECTED in result.remediation_codes
    assert ConsistencyCode.EXTERNAL_TRANSMISSION_DETECTED in result.remediation_codes


def run():
    tests = [
        value for name, value in globals().items()
        if name.startswith("test_") and callable(value)
    ]
    for test in tests:
        test()
    print(f"[SelectionManifest] focused/adversarial tests: {len(tests)} PASSED")
    print("PRE_HANDOFF_SELECTION_MANIFEST_CONSISTENCY_TESTS_PASSED")


if __name__ == "__main__":
    run()
