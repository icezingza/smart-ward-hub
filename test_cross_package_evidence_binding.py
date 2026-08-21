"""Focused/adversarial tests for cross-package evidence binding."""

from copy import deepcopy
from pathlib import Path

from cross_package_evidence_binding import (
    APPROVAL_PATH,
    DURABLE_PATH,
    FREEZE_PATH,
    TRANSCRIPT_PATH,
    BindingCode,
    BindingDecision,
    check_repository,
    evaluate_bindings,
)
from durable_worker_replay_contract import run_rehearsal
from worker_recovery_approval import build_approval_readback
from worker_recovery_transcript import build_worker_recovery_transcript


BOUNDARY = {
    "external_authority": "NONE",
    "clinical_validation_authorized": False,
    "production_authorized": False,
    "runtime_authority": "NONE",
    "pilot_gate_status": "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION",
}


def _synthetic_bound_inputs():
    transcript = build_worker_recovery_transcript()
    approval_report = build_approval_readback()
    approval = {
        "source_revision": "a" * 40,
        **approval_report,
    }
    durable = {
        "source_revision": "a" * 40,
        **run_rehearsal(),
    }
    transcript["source_revision"] = "a" * 40
    hashes = {"transcript": "1" * 64, "approval": "2" * 64, "durable": "3" * 64}
    freeze = {
        "source_revision": "a" * 40,
        "authorization_boundary": BOUNDARY,
        "files": [
            {"path": TRANSCRIPT_PATH.as_posix(), "sha256": hashes["transcript"]},
            {"path": APPROVAL_PATH.as_posix(), "sha256": hashes["approval"]},
            {"path": DURABLE_PATH.as_posix(), "sha256": hashes["durable"]},
        ],
    }
    return transcript, approval, durable, freeze, hashes


def test_synthetic_bound_packages_return_bound():
    transcript, approval, durable, freeze, hashes = _synthetic_bound_inputs()
    result = evaluate_bindings(
        transcript=transcript,
        approval=approval,
        durable=durable,
        freeze=freeze,
        artifact_hashes=hashes,
        verify_revision_ancestry=False,
    )
    assert result.decision == BindingDecision.BOUND
    assert result.remediation_codes == (BindingCode.EVIDENCE_PACKAGES_BOUND,)
    assert all(result.checks.values())
    assert result.read_only is True
    assert result.external_transmission_performed is False


def test_transcript_hash_mismatch_is_reconciliation_required():
    transcript, approval, durable, freeze, hashes = _synthetic_bound_inputs()
    approval["approval"]["transcript_sha256"] = "f" * 64
    result = evaluate_bindings(
        transcript=transcript,
        approval=approval,
        durable=durable,
        freeze=freeze,
        artifact_hashes=hashes,
        verify_revision_ancestry=False,
    )
    assert result.decision == BindingDecision.RECONCILIATION_REQUIRED
    assert BindingCode.APPROVAL_TRANSCRIPT_HASH_MISMATCH in result.remediation_codes


def test_queue_binding_reference_mismatch_is_reconciliation_required():
    transcript, approval, durable, freeze, hashes = _synthetic_bound_inputs()
    approval["approval"]["queue_backup_ref"] = "backup:tampered-001"
    result = evaluate_bindings(
        transcript=transcript,
        approval=approval,
        durable=durable,
        freeze=freeze,
        artifact_hashes=hashes,
        verify_revision_ancestry=False,
    )
    assert result.decision == BindingDecision.RECONCILIATION_REQUIRED
    assert BindingCode.APPROVAL_QUEUE_REF_MISMATCH in result.remediation_codes


def test_durable_boundary_mutation_is_reconciliation_required():
    transcript, approval, durable, freeze, hashes = _synthetic_bound_inputs()
    durable["runtime_replay_executed"] = True
    result = evaluate_bindings(
        transcript=transcript,
        approval=approval,
        durable=durable,
        freeze=freeze,
        artifact_hashes=hashes,
        verify_revision_ancestry=False,
    )
    assert result.decision == BindingDecision.RECONCILIATION_REQUIRED
    assert BindingCode.DURABLE_REPLAY_BOUNDARY_MISMATCH in result.remediation_codes


def test_freeze_artifact_hash_mismatch_is_reconciliation_required():
    transcript, approval, durable, freeze, hashes = _synthetic_bound_inputs()
    freeze["files"][0]["sha256"] = "e" * 64
    result = evaluate_bindings(
        transcript=transcript,
        approval=approval,
        durable=durable,
        freeze=freeze,
        artifact_hashes=hashes,
        verify_revision_ancestry=False,
    )
    assert result.decision == BindingDecision.RECONCILIATION_REQUIRED
    assert BindingCode.FREEZE_ARTIFACT_HASH_MISMATCH in result.remediation_codes


def test_current_repository_binding_is_bound_after_evidence_regeneration():
    report = check_repository(Path(__file__).resolve().parent)
    assert report["decision"] == BindingDecision.BOUND
    assert report["remediation_codes"] == [BindingCode.EVIDENCE_PACKAGES_BOUND]
    assert report["read_only"] is True
    assert report["external_transmission_performed"] is False
    assert report["authorization_boundary"] == BOUNDARY


def run() -> None:
    tests = [
        value for name, value in globals().items()
        if name.startswith("test_") and callable(value)
    ]
    for test in tests:
        test()
    print(f"[CrossPackage] focused/adversarial tests: {len(tests)} PASSED")
    print("CROSS_PACKAGE_EVIDENCE_BINDING_TESTS_PASSED")


if __name__ == "__main__":
    run()
