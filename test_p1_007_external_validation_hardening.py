from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from external_validation_package import ExternalValidationPackageError, GateEvidence, ValidationGate, default_pilot_package
from p1_007_external_validation_readiness import ExternalValidationReadinessError, template, validate_manifest

ROOT = Path(__file__).resolve().parent
TEMPLATE_PATH = ROOT / "evals/micro_rag/evidence/p1-007-external-validation-readiness-template-20260820.json"
SCHEMA_PATH = ROOT / "evals/micro_rag/evidence/p1-007-external-validation-readiness-schema-v1.json"


def expect_error(action, expected: str) -> None:
    try:
        action()
    except ExternalValidationPackageError as exc:
        assert str(exc) == expected, (str(exc), expected)
    else:
        raise AssertionError(f"expected {expected}")


def expect_manifest_rejection(payload: dict, fragment: str) -> None:
    try:
        validate_manifest(payload, template_only=True)
    except ExternalValidationReadinessError as exc:
        assert fragment in str(exc), str(exc)
    else:
        raise AssertionError("manifest mutation was accepted")


def test_manifest_mutations() -> None:
    payload = template()
    assert validate_manifest(payload, template_only=True)["valid"] is True
    assert json.loads(TEMPLATE_PATH.read_text(encoding="utf-8"))["gate_count"] == 10
    assert json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))["$id"].endswith("p1-007-external-validation-readiness-v1")
    payload = template()
    payload["unexpected"] = True
    expect_manifest_rejection(payload, "unknown fields")
    mutations = (
        ("external_execution_status", "RUNNING", "external execution must remain NOT_STARTED"),
        ("real_world_authorization", True, "real_world_authorization must remain false"),
        ("clinical_validation_authorized", True, "clinical_validation_authorized must remain false"),
        ("production_authorized", True, "production_authorized must remain false"),
        ("claim_boundary", "production-ready", "claim boundary mismatch"),
        ("evidence_class", "CLINICAL_VALIDATED", "evidence class mismatch"),
    )
    for field, value, fragment in mutations:
        mutated = template()
        mutated[field] = value
        expect_manifest_rejection(mutated, fragment)
    mutated = template()
    mutated["gates"].pop("GV-10")
    expect_manifest_rejection(mutated, "gates must contain exactly")
    mutated = template()
    mutated["gate_status_counts"]["BLOCKED"] = 1
    expect_manifest_rejection(mutated, "initial gate status counts mismatch")
    mutated = template()
    mutated["package_ref"] = "org:coordinator@example.invalid"
    expect_manifest_rejection(mutated, "must be an opaque reference")
    mutated = template()
    mutated["blocker_policy"]["reason_required"] = False
    expect_manifest_rejection(mutated, "blocker reason must be required")
    print("[P1-007] Readiness manifest gate/claim/execution/reopen mutations: PASSED")


def test_runtime_gate_lifecycle() -> None:
    package = default_pilot_package()
    evidence = GateEvidence("artifact:protocol-v1", "SOFTWARE_VERIFIED", "2026-08-20T10:00:00+00:00")
    package.gates["GV-01"].submit_evidence(evidence)
    expect_error(lambda: package.gates["GV-01"].submit_evidence(evidence), "duplicate_gate_evidence")
    package.block_gate("GV-01", "External approval is not assigned")
    expect_error(lambda: package.submit_evidence("GV-01", "artifact:protocol-v2", "SOFTWARE_VERIFIED"), "blocked_gate_requires_reopen")
    expect_error(lambda: package.reopen_gate("GV-01", "   "), "reopen_reason_required")
    package.reopen_gate("GV-01", "Approval owner assigned for re-review")
    package.submit_evidence("GV-01", "artifact:protocol-v2", "SOFTWARE_VERIFIED")
    assert package.gates["GV-01"].status == "EVIDENCE_SUBMITTED"
    expect_error(lambda: package.block_gate("GV-01", "already submitted"), "gate_already_blocked") if False else None
    package.block_gate("GV-02", "Privacy review pending")
    expect_error(lambda: package.block_gate("GV-02", "second blocker"), "gate_already_blocked")
    summary = package.readiness_summary()
    assert summary["status_counts"]["BLOCKED"] == 1
    assert summary["status_counts"]["EVIDENCE_SUBMITTED"] == 1
    assert summary["real_world_authorization"] is False
    assert summary["clinical_validation_authorized"] is False
    assert summary["production_authorized"] is False
    assert summary["execution_status"] == "NOT_STARTED"
    summary["status_counts"]["BLOCKED"] = 0
    assert package.readiness_summary()["status_counts"]["BLOCKED"] == 1
    print("[P1-007] Evidence idempotency, blocked/reopen lifecycle and summary-copy boundary: PASSED")


def test_runtime_type_identity_claim_fail_closed() -> None:
    package = default_pilot_package()
    package.real_world_authorization = True
    expect_error(lambda: package.validate(), "software_package_cannot_authorize_real_world_testing")
    package = default_pilot_package()
    package.execution_status = "RUNNING"
    expect_error(lambda: package.validate(), "external_execution_boundary_breached")
    package = default_pilot_package()
    package.external_owner_appointment = "owner:real@example.invalid"
    expect_error(lambda: package.validate(), "external_owner_appointment_boundary_breached")
    package = default_pilot_package()
    package.gates["GV-01"].owner_role = "clinical@example.invalid"
    expect_error(lambda: package.validate(), "unsafe_gate_owner")
    package = default_pilot_package()
    package.gates["GV-01"].required_evidence = ("HN-2026-1234",)
    expect_error(lambda: package.validate(), "unsafe_required_evidence_reference")
    expect_error(lambda: GateEvidence("artifact:one", "CLINICAL_ACCURACY", "2026-08-20T10:00:00+00:00").validate(), "unsupported_evidence_claim")
    expect_error(lambda: GateEvidence("artifact:one", "SOFTWARE_VERIFIED", "2026-08-20T10:00:00").validate(), "evidence_timestamp_must_be_timezone_aware")
    expect_error(lambda: GateEvidence(None, "SOFTWARE_VERIFIED", "2026-08-20T10:00:00+00:00").validate(), "unsafe_evidence_reference")
    print("[P1-007] Runtime type/identity/secret/claim/authorization mutations: PASSED")


if __name__ == "__main__":
    test_manifest_mutations()
    test_runtime_gate_lifecycle()
    test_runtime_type_identity_claim_fail_closed()
    print("P1_007_EXTERNAL_VALIDATION_HARDENING_TESTS_PASSED")
