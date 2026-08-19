from __future__ import annotations

from external_validation_package import ExternalValidationPackageError, GateEvidence, default_pilot_package


def expect_error(action, expected: str) -> None:
    try:
        action()
    except ExternalValidationPackageError as exc:
        assert str(exc) == expected, (str(exc), expected)
    else:
        raise AssertionError(f"expected {expected}")


def run() -> None:
    package = default_pilot_package()
    expected_ids = {f"GV-{index:02d}" for index in range(1, 11)}
    assert set(package.gates) == expected_ids
    for gate_id, gate in package.gates.items():
        assert gate.status == "OPEN"
        assert gate.owner_role.strip()
        assert gate.required_evidence
        assert gate_id == f"GV-{int(gate_id[-2:]):02d}"
        gate.validate()
    print("[GV-MATRIX] All 10 gates have unique IDs, owners and required evidence: PASSED")

    gate = package.gates["GV-01"]
    expect_error(
        lambda: gate.submit_evidence(GateEvidence("protocol.md", "SOFTWARE_VERIFIED", "2026-08-20T10:00:00")),
        "evidence_timestamp_must_be_timezone_aware",
    )
    expect_error(
        lambda: gate.submit_evidence(GateEvidence("protocol.md", "clinical_validated", "2026-08-20T10:00:00+00:00")),
        "unsupported_evidence_claim",
    )
    print("[GV-MATRIX] Timezone-aware timestamps and case-insensitive claim boundary: PASSED")

    gate.submit_evidence(GateEvidence("protocol.md", "SOFTWARE_VERIFIED", "2026-08-20T10:00:00+00:00"))
    gate.block("External clinical approval is not yet assigned")
    expect_error(
        lambda: gate.submit_evidence(GateEvidence("protocol-v2.md", "SOFTWARE_VERIFIED", "2026-08-20T11:00:00+00:00")),
        "blocked_gate_requires_reopen",
    )
    expect_error(lambda: gate.reopen("   "), "reopen_reason_required")
    gate.reopen("Review owner assigned for follow-up")
    assert gate.status == "OPEN"
    gate.submit_evidence(GateEvidence("protocol-v2.md", "SOFTWARE_VERIFIED", "2026-08-20T11:00:00+00:00"))
    assert gate.status == "EVIDENCE_SUBMITTED"
    print("[GV-MATRIX] Blocked gate cannot be overwritten; explicit reopen is required: PASSED")

    package = default_pilot_package()
    package.gates["GV-10"].required_evidence = ()
    expect_error(lambda: package.readiness_summary(), "gate_owner_and_evidence_required")
    print("[GV-MATRIX] GV-10 required evidence cannot be silently removed: PASSED")
    print("EXTERNAL_VALIDATION_GATE_MATRIX_TESTS_PASSED")


if __name__ == "__main__":
    run()
