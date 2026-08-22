"""Focused/adversarial tests for the pre-handoff evidence manifest validator."""

from copy import deepcopy

from consolidated_internal_handoff_index import LOCKED_BOUNDARY, LOCKED_EXTERNAL_GATE_SNAPSHOT
from pre_handoff_manifest_validator import (
    SNAPSHOT_RELATIVE,
    ManifestCode,
    ManifestDecision,
    evaluate_manifest,
)


def _fixtures():
    checks = {
        "freeze_drift_free": True,
        "handoff_index_bound": True,
        "authorization_boundary_locked": True,
        "claim_boundary_locked": True,
        "external_gate_snapshot_preserved": True,
        "external_submission_disabled": True,
        "runtime_mutation_absent": True,
        "read_only": True,
        "external_transmission_absent": True,
    }
    fresh = {
        "decision": "INTERNAL_HANDOFF_READY",
        "remediation_codes": [],
        "checks": checks,
    }
    snapshot = {
        "evidence_type": "PRE_HANDOFF_READINESS_CHECK",
        "schema_version": "smart-ward-pre-handoff-v1",
        "source_revision": "a" * 40,
        "decision": "INTERNAL_HANDOFF_READY",
        "remediation_codes": [],
        "checks": deepcopy(checks),
        "freeze_source_revision": "a" * 40,
        "origin_main_revision": "a" * 40,
        "external_gate_snapshot": deepcopy(LOCKED_EXTERNAL_GATE_SNAPSHOT),
        "claim_boundary": {
            "status": "CONTROLLED_PRODUCTION_PROTOTYPE",
            "functional_verification": "PASSED",
            "clinical_validation": "PENDING",
            "production_ready": False,
        },
        "authorization_boundary": deepcopy(LOCKED_BOUNDARY),
        "read_only": True,
        "external_submission_allowed": False,
        "authorization_promoted": False,
        "runtime_mutation_performed": False,
        "external_transmission_performed": False,
    }
    freeze = {
        "freeze_status": "PASS",
        "source_revision": "a" * 40,
        "origin_main_revision": "a" * 40,
        "files": [{"path": SNAPSHOT_RELATIVE.as_posix(), "sha256": "b" * 64}],
    }
    return snapshot, freeze, fresh


def test_bound_manifest_is_valid():
    snapshot, freeze, fresh = _fixtures()
    result = evaluate_manifest(
        snapshot=snapshot,
        freeze=freeze,
        fresh_readiness=fresh,
        snapshot_sha256="b" * 64,
    )
    assert result.decision == ManifestDecision.VALID
    assert result.remediation_codes == ()
    assert all(result.checks.values())


def test_snapshot_hash_mismatch_is_blocked():
    snapshot, freeze, fresh = _fixtures()
    result = evaluate_manifest(snapshot=snapshot, freeze=freeze, fresh_readiness=fresh, snapshot_sha256="c" * 64)
    assert result.decision == ManifestDecision.INVALID
    assert ManifestCode.SNAPSHOT_HASH_MISMATCH in result.remediation_codes


def test_snapshot_not_in_freeze_is_blocked():
    snapshot, freeze, fresh = _fixtures()
    freeze["files"] = []
    result = evaluate_manifest(snapshot=snapshot, freeze=freeze, fresh_readiness=fresh, snapshot_sha256="b" * 64)
    assert result.decision == ManifestDecision.INVALID
    assert ManifestCode.SNAPSHOT_NOT_IN_FREEZE in result.remediation_codes


def test_snapshot_source_ancestor_is_allowed():
    snapshot, freeze, fresh = _fixtures()
    snapshot["source_revision"] = "c" * 40
    snapshot["origin_main_revision"] = "d" * 40
    result = evaluate_manifest(
        snapshot=snapshot,
        freeze=freeze,
        fresh_readiness=fresh,
        snapshot_sha256="b" * 64,
        snapshot_source_ancestor=True,
        snapshot_origin_ancestor=True,
    )
    assert result.decision == ManifestDecision.VALID
    assert result.remediation_codes == ()


def test_snapshot_source_mismatch_is_blocked():
    snapshot, freeze, fresh = _fixtures()
    snapshot["source_revision"] = "d" * 40
    result = evaluate_manifest(snapshot=snapshot, freeze=freeze, fresh_readiness=fresh, snapshot_sha256="b" * 64)
    assert result.decision == ManifestDecision.INVALID
    assert ManifestCode.SNAPSHOT_SOURCE_REVISION_MISMATCH in result.remediation_codes


def test_snapshot_decision_or_checks_mismatch_is_blocked():
    snapshot, freeze, fresh = _fixtures()
    snapshot["decision"] = "INTERNAL_HANDOFF_BLOCKED"
    snapshot["checks"]["freeze_drift_free"] = False
    result = evaluate_manifest(snapshot=snapshot, freeze=freeze, fresh_readiness=fresh, snapshot_sha256="b" * 64)
    assert result.decision == ManifestDecision.INVALID
    assert ManifestCode.SNAPSHOT_DECISION_MISMATCH in result.remediation_codes
    assert ManifestCode.SNAPSHOT_CHECKS_MISMATCH in result.remediation_codes


def test_claim_and_authorization_mutations_are_blocked():
    snapshot, freeze, fresh = _fixtures()
    snapshot["claim_boundary"]["production_ready"] = True
    snapshot["authorization_boundary"]["production_authorized"] = True
    result = evaluate_manifest(snapshot=snapshot, freeze=freeze, fresh_readiness=fresh, snapshot_sha256="b" * 64)
    assert result.decision == ManifestDecision.INVALID
    assert ManifestCode.SNAPSHOT_CLAIM_BOUNDARY_MUTATED in result.remediation_codes
    assert ManifestCode.SNAPSHOT_AUTHORIZATION_MUTATED in result.remediation_codes


def test_submission_runtime_and_transmission_mutations_are_blocked():
    snapshot, freeze, fresh = _fixtures()
    snapshot["external_submission_allowed"] = True
    snapshot["runtime_mutation_performed"] = True
    snapshot["external_transmission_performed"] = True
    result = evaluate_manifest(snapshot=snapshot, freeze=freeze, fresh_readiness=fresh, snapshot_sha256="b" * 64)
    assert result.decision == ManifestDecision.INVALID
    assert ManifestCode.SNAPSHOT_EXTERNAL_SUBMISSION_ENABLED in result.remediation_codes
    assert ManifestCode.SNAPSHOT_RUNTIME_MUTATION in result.remediation_codes
    assert ManifestCode.SNAPSHOT_EXTERNAL_TRANSMISSION in result.remediation_codes


def test_fresh_readiness_blocked_is_blocked():
    snapshot, freeze, fresh = _fixtures()
    fresh["decision"] = "INTERNAL_HANDOFF_BLOCKED"
    fresh["remediation_codes"] = ["FREEZE_DRIFT_DETECTED"]
    result = evaluate_manifest(snapshot=snapshot, freeze=freeze, fresh_readiness=fresh, snapshot_sha256="b" * 64)
    assert result.decision == ManifestDecision.INVALID
    assert ManifestCode.FRESH_READINESS_BLOCKED in result.remediation_codes
    assert ManifestCode.FRESH_READINESS_MISMATCH in result.remediation_codes


def run() -> None:
    tests = [
        value for name, value in globals().items()
        if name.startswith("test_") and callable(value)
    ]
    for test in tests:
        test()
    print(f"[PreHandoffManifest] focused/adversarial tests: {len(tests)} PASSED")
    print("PRE_HANDOFF_MANIFEST_VALIDATOR_TESTS_PASSED")


if __name__ == "__main__":
    run()
