"""Focused/adversarial tests for the local hardware-bench packet readiness guard."""
from __future__ import annotations

from copy import deepcopy

from p0_hardware_bench_evidence_readiness import (
    BENCH_STEP_IDS,
    HardwareBenchReadinessError,
    PRECONDITION_IDS,
    STOP_CONDITION_IDS,
    TARGET_MODEL,
    TARGET_ROLE,
    _fixture_packet,
    evaluate_hardware_bench_readiness,
    validate_bench_packet,
)


def _expect_error(callback, label: str) -> None:
    try:
        callback()
    except HardwareBenchReadinessError:
        print(f"[P0 Hardware Bench] {label}: PASSED")
        return
    raise AssertionError(f"{label}: unsafe packet was accepted")


def test_valid_packet_is_prepared_not_executed():
    report = evaluate_hardware_bench_readiness()
    assert report["all_passed"] is True
    assert report["decision"] == "P0_HARDWARE_BENCH_PACKET_PREPARED_PENDING_PHYSICAL_EXECUTION"
    assert report["mode"] == "LOCAL_DETERMINISTIC_TEMPLATE_ONLY"
    assert report["target_model"] == TARGET_MODEL
    assert report["target_role"] == TARGET_ROLE
    assert report["physical_execution_performed"] is False
    assert report["physical_hardware_evidence"] == "UNVERIFIED"
    assert report["clinical_use_authorized"] is False
    assert report["external_submission_allowed"] is False
    assert report["authorization_promoted"] is False
    assert report["external_gate_snapshot"] == {"blocked": 7, "open": 3, "evidence_submitted": 0, "passed": 0}
    print("[P0 Hardware Bench] Prepared packet remains non-authorizing: PASSED")


def test_target_and_status_overclaims_are_rejected():
    wrong_target = _fixture_packet()
    wrong_target["target_model"] = "BMAX i11_s"
    _expect_error(lambda: validate_bench_packet(wrong_target), "Wrong fixed-hub target")

    wrong_role = _fixture_packet()
    wrong_role["target_role"] = "ROAMING_CANDIDATE"
    _expect_error(lambda: validate_bench_packet(wrong_role), "Wrong hardware role")

    executed = _fixture_packet()
    executed["packet_status"] = "EXECUTED"
    _expect_error(lambda: validate_bench_packet(executed), "Executed status overclaim")

    physical = _fixture_packet()
    physical["physical_execution_performed"] = True
    _expect_error(lambda: validate_bench_packet(physical), "Physical execution overclaim")

    clinical = _fixture_packet()
    clinical["clinical_use_authorized"] = True
    _expect_error(lambda: validate_bench_packet(clinical), "Clinical authorization overclaim")


def test_coverage_and_observed_results_are_fail_closed():
    missing_precondition = _fixture_packet()
    missing_precondition["preconditions"].pop(PRECONDITION_IDS[0])
    _expect_error(lambda: validate_bench_packet(missing_precondition), "Missing precondition")

    completed_step = _fixture_packet()
    completed_step["bench_steps"][BENCH_STEP_IDS[0]]["status"] = "PASS"
    _expect_error(lambda: validate_bench_packet(completed_step), "Unverified bench step marked passed")

    missing_stop = _fixture_packet()
    missing_stop["stop_conditions"].pop(STOP_CONDITION_IDS[0])
    _expect_error(lambda: validate_bench_packet(missing_stop), "Missing stop condition")

    observed = _fixture_packet()
    observed["observed_results"] = {"HB-01": {"status": "PASS"}}
    _expect_error(lambda: validate_bench_packet(observed), "Observed result before execution")


def test_opaque_refs_and_redaction_markers_are_rejected():
    raw_asset = _fixture_packet()
    raw_asset["asset_ref"] = "asset:HN-raw-fixture"
    _expect_error(lambda: validate_bench_packet(raw_asset), "Raw identity in asset ref")

    bad_ref = _fixture_packet()
    bad_ref["operator_ref"] = "operator"
    _expect_error(lambda: validate_bench_packet(bad_ref), "Unscoped operator ref")

    secret_ref = _fixture_packet()
    secret_ref["software_ref"] = "software:private_key=fixture"
    _expect_error(lambda: validate_bench_packet(secret_ref), "Secret marker in software ref")


def test_exact_schema_and_time_window_are_enforced():
    unknown = _fixture_packet()
    unknown["extra"] = "not allowed"
    _expect_error(lambda: validate_bench_packet(unknown), "Unknown packet field")

    reversed_time = _fixture_packet()
    reversed_time["started_at_utc"], reversed_time["completed_at_utc"] = (
        reversed_time["completed_at_utc"],
        "2026-08-22T23:00:00Z",
    )
    _expect_error(lambda: validate_bench_packet(reversed_time), "Invalid time window")

    naive_time = _fixture_packet()
    naive_time["started_at_utc"] = "2026-08-23T00:00:00"
    _expect_error(lambda: validate_bench_packet(naive_time), "Naive timestamp")


def test_returned_boundary_mutation_cannot_promote_hardware_or_authority():
    report = evaluate_hardware_bench_readiness()
    mutated = deepcopy(report)
    mutated["physical_execution_performed"] = True
    mutated["clinical_use_authorized"] = True
    mutated["authorization_boundary"]["production_authorized"] = True
    mutated["external_gate_snapshot"]["passed"] = 10
    fresh = evaluate_hardware_bench_readiness()
    assert fresh["physical_execution_performed"] is False
    assert fresh["clinical_use_authorized"] is False
    assert fresh["authorization_boundary"]["production_authorized"] is False
    assert fresh["external_gate_snapshot"]["passed"] == 0
    assert fresh["authorization_promoted"] is False
    print("[P0 Hardware Bench] Returned evidence mutation cannot promote physical or production status: PASSED")


def run() -> None:
    tests = [
        test_valid_packet_is_prepared_not_executed,
        test_target_and_status_overclaims_are_rejected,
        test_coverage_and_observed_results_are_fail_closed,
        test_opaque_refs_and_redaction_markers_are_rejected,
        test_exact_schema_and_time_window_are_enforced,
        test_returned_boundary_mutation_cannot_promote_hardware_or_authority,
    ]
    for test in tests:
        test()
    print(f"[P0 Hardware Bench] focused/adversarial tests: {len(tests)} PASSED")
    print("P0_HARDWARE_BENCH_EVIDENCE_READINESS_TESTS_PASSED")


if __name__ == "__main__":
    run()
