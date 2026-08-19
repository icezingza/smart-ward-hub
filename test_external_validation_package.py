from __future__ import annotations

from external_validation_package import (
    ExternalValidationPackageError,
    GateEvidence,
    default_pilot_package,
)


def expect_error(action, expected: str) -> None:
    try:
        action()
    except ExternalValidationPackageError as exc:
        assert str(exc) == expected, (str(exc), expected)
    else:
        raise AssertionError(f"expected {expected}")


def run() -> None:
    package = default_pilot_package()
    summary = package.readiness_summary()
    assert summary["gate_count"] == 10
    assert summary["status_counts"]["OPEN"] == 10
    assert summary["ready_for_external_review"] is False
    assert summary["real_world_authorization"] is False
    assert summary["clinical_governance_required"] is True
    print("[P1-007] Default external-validation package has 10 open gates and no authorization: PASSED")

    package.submit_evidence("GV-02", "P1_005_ZERO_PII_AND_NON_ACCURACY_METRICS.md", "SOFTWARE_VERIFIED")
    assert package.gates["GV-02"].status == "EVIDENCE_SUBMITTED"
    expect_error(
        lambda: package.submit_evidence("GV-02", "P1_005_ZERO_PII_AND_NON_ACCURACY_METRICS.md", "SOFTWARE_VERIFIED"),
        "duplicate_gate_evidence",
    )
    print("[P1-007] Gate evidence submission is traceable and idempotency-protected: PASSED")

    package.block_gate("GV-06", "Acer has no enumerated COM port and physical loopback fixture is absent")
    assert package.gates["GV-06"].status == "BLOCKED"
    assert package.gates["GV-06"].blocker.startswith("Acer")
    print("[P1-007] Physical gate can be explicitly blocked without hiding the reason: PASSED")

    package = default_pilot_package()
    package.real_world_authorization = True
    expect_error(lambda: package.readiness_summary(), "software_package_cannot_authorize_real_world_testing")
    print("[P1-007] Software package cannot self-authorize real-world testing: PASSED")

    package = default_pilot_package()
    expect_error(
        lambda: package.submit_evidence("GV-01", "HN-2026-9999-evidence", "SOFTWARE_VERIFIED"),
        "unsafe_evidence_reference",
    )
    expect_error(
        lambda: package.submit_evidence("GV-01", "clinical-ready-proof", "CLINICAL_VALIDATED"),
        "unsupported_evidence_claim",
    )
    print("[P1-007] Raw identity and unsupported evidence claims are rejected: PASSED")

    package = default_pilot_package()
    package.block_gate("GV-09", "Clinical owner and signed ward SOP not assigned")
    summary = package.readiness_summary()
    assert summary["status_counts"]["BLOCKED"] == 1
    assert summary["ready_for_external_review"] is False
    print("[P1-007] Clinical governance blocker remains visible in readiness summary: PASSED")
    print("EXTERNAL_VALIDATION_PACKAGE_TESTS_PASSED")


if __name__ == "__main__":
    run()
