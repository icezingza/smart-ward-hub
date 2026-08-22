from __future__ import annotations

from copy import deepcopy

from p2_002_adapter_conformance import (
    ConformanceCode,
    ConformanceDecision,
    LOCKED_BOUNDARY,
    build_envelope,
    check_conformance,
    evaluate_conformance,
)


def test_current_fixture_conformance_passes():
    result = check_conformance()
    assert result["decision"] == ConformanceDecision.P2_002_ADAPTER_CONFORMANCE_VERIFIED
    assert result["remediation_codes"] == []
    assert all(result["checks"].values())
    assert result["transports"] == ["mqtt", "websocket", "serial", "ble"]
    assert result["selected_software_transport"] == "serial"
    assert result["hardware_evidence"] == "UNVERIFIED"
    assert result["fixture_only"] is True
    assert result["read_only"] is True
    assert result["external_submission_allowed"] is False
    assert result["authorization_promoted"] is False
    assert result["runtime_mutation_performed"] is False
    assert result["external_transmission_performed"] is False


def test_normalized_contract_is_identical_across_transports():
    result = check_conformance()
    values = list(result["normalized_by_transport"].values())
    assert values and all(value == values[0] for value in values)
    assert set(values[0]) == {
        "schema_version",
        "device_id",
        "sequence",
        "ppg",
        "accel_x",
        "accel_y",
        "accel_z",
        "battery_pct",
    }


def test_failure_matrix_covers_every_transport():
    result = check_conformance()
    for transport, failures in result["failure_matrix"].items():
        assert failures == {
            "missing_signature": "signature_missing",
            "pii_field": "pii_or_secret_field_detected",
            "command_field": "command_field_detected",
            "source_identity_mismatch": "source_device_mismatch",
            "unknown_outer_field": "unknown_outer_field",
            "oversized_frame": "frame_too_large",
            "wrong_transport_context": "transport_context_mismatch",
        }, transport


def test_public_boundary_mutation_blocks():
    result = evaluate_conformance(external_submission_allowed=True)
    assert result.decision == ConformanceDecision.P2_002_ADAPTER_CONFORMANCE_BLOCKED
    assert ConformanceCode.EXECUTION_BOUNDARY_MUTATED in result.remediation_codes


def test_authorization_boundary_mutation_blocks():
    mutated = deepcopy(LOCKED_BOUNDARY)
    mutated["production_authorized"] = True
    result = evaluate_conformance(authorization_boundary=mutated)
    assert result.decision == ConformanceDecision.P2_002_ADAPTER_CONFORMANCE_BLOCKED
    assert ConformanceCode.AUTHORIZATION_BOUNDARY_MUTATED in result.remediation_codes


def test_fixture_builder_does_not_mutate_input():
    fixture = build_envelope()
    before = deepcopy(fixture)
    check_conformance()
    assert fixture == before


def run() -> None:
    tests = [
        value for name, value in globals().items()
        if name.startswith("test_") and callable(value)
    ]
    for test in tests:
        test()
    print(f"[P2-002 CONFORMANCE] focused/adversarial tests: {len(tests)} PASSED")
    print("P2_002_ADAPTER_CONFORMANCE_TESTS_PASSED")


if __name__ == "__main__":
    run()
