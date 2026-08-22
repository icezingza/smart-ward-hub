"""Focused/adversarial tests for the consolidated internal handoff index."""

from copy import deepcopy
from pathlib import Path

from consolidated_internal_handoff_index import (
    LOCKED_BOUNDARY,
    LOCKED_EXTERNAL_GATE_SNAPSHOT,
    build_index,
    evaluate_index,
)
from cross_package_evidence_binding import (
    APPROVAL_PATH,
    DURABLE_PATH,
    TRANSCRIPT_PATH,
)
from export_cross_package_evidence_binding import export_evidence as export_binding


ROOT = Path(__file__).resolve().parent


def _bound_fixture():
    binding = export_binding(project_root=ROOT)
    freeze = {
        "manifest_path": "evals/micro_rag/evidence/release-candidate-freeze-20260820.json",
        "freeze_status": "PASS",
        "source_revision": "a" * 40,
        "origin_main_revision": "a" * 40,
        "external_gate_snapshot": deepcopy(LOCKED_EXTERNAL_GATE_SNAPSHOT),
        "files": [
            {"path": TRANSCRIPT_PATH.as_posix(), "sha256": binding["artifact_hashes"]["transcript"]},
            {"path": APPROVAL_PATH.as_posix(), "sha256": binding["artifact_hashes"]["approval"]},
            {"path": DURABLE_PATH.as_posix(), "sha256": binding["artifact_hashes"]["durable"]},
            {"path": "evals/micro_rag/evidence/cross-package-binding-local.json", "sha256": "b" * 64},
        ],
    }
    return binding, freeze


def test_current_repository_builds_bound_index():
    result = build_index(ROOT)
    assert result.decision == "BOUND"
    assert result.remediation_codes == ("HANDOFF_INDEX_BOUND",)
    assert result.index["read_only"] is True
    assert result.index["external_submission_allowed"] is False
    assert result.index["authorization_promoted"] is False
    assert result.index["runtime_mutation_performed"] is False
    assert result.index["authorization_boundary"] == LOCKED_BOUNDARY
    assert result.index["freeze"]["external_gate_snapshot"] == LOCKED_EXTERNAL_GATE_SNAPSHOT
    assert len(result.index["evidence_navigation"]) == 4
    assert all(row["status"] == "BOUND" for row in result.index["evidence_navigation"])


def test_binding_not_bound_requires_reconciliation():
    binding, freeze = _bound_fixture()
    binding["decision"] = "RECONCILIATION_REQUIRED"
    result = evaluate_index(binding=binding, freeze=freeze, package_hashes=None)
    assert result.decision == "RECONCILIATION_REQUIRED"
    assert "CROSS_PACKAGE_BINDING_NOT_BOUND" in result.remediation_codes


def test_external_gate_snapshot_mutation_requires_reconciliation():
    binding, freeze = _bound_fixture()
    freeze["external_gate_snapshot"]["passed"] = 1
    result = evaluate_index(binding=binding, freeze=freeze)
    assert result.decision == "RECONCILIATION_REQUIRED"
    assert "EXTERNAL_GATE_SNAPSHOT_MUTATED" in result.remediation_codes


def test_claim_boundary_mutation_requires_reconciliation():
    binding, freeze = _bound_fixture()
    binding["claim_boundary"]["production_ready"] = True
    result = evaluate_index(binding=binding, freeze=freeze)
    assert result.decision == "RECONCILIATION_REQUIRED"
    assert "CLAIM_BOUNDARY_MUTATED" in result.remediation_codes


def test_freeze_hash_mismatch_requires_reconciliation():
    binding, freeze = _bound_fixture()
    hashes = {
        "transcript": binding["artifact_hashes"]["transcript"],
        "approval": binding["artifact_hashes"]["approval"],
        "durable": binding["artifact_hashes"]["durable"],
        "binding": "c" * 64,
    }
    result = evaluate_index(binding=binding, freeze=freeze, package_hashes=hashes)
    assert result.decision == "RECONCILIATION_REQUIRED"
    assert "FREEZE_HASH_MISMATCH_CROSS_PACKAGE_BINDING" in result.remediation_codes


def test_authorization_boundary_mutation_requires_reconciliation():
    binding, freeze = _bound_fixture()
    binding["authorization_boundary"]["production_authorized"] = True
    result = evaluate_index(binding=binding, freeze=freeze)
    assert result.decision == "RECONCILIATION_REQUIRED"
    assert "AUTHORIZATION_BOUNDARY_MUTATED" in result.remediation_codes


def test_index_does_not_permit_external_submission():
    result = build_index(ROOT)
    index = result.index
    assert index["external_submission_allowed"] is False
    assert index["authorization_promoted"] is False
    assert index["runtime_mutation_performed"] is False
    assert index["claim_boundary"]["production_ready"] is False
    assert index["claim_boundary"]["clinical_validation"] == "PENDING"


def run() -> None:
    tests = [
        value for name, value in globals().items()
        if name.startswith("test_") and callable(value)
    ]
    for test in tests:
        test()
    print(f"[HandoffIndex] focused/adversarial tests: {len(tests)} PASSED")
    print("CONSOLIDATED_INTERNAL_HANDOFF_INDEX_TESTS_PASSED")


if __name__ == "__main__":
    run()
