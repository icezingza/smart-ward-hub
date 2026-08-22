"""Focused/adversarial tests for P1 host-hardware preparation reconciliation."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone

from deployment_readiness import validate_environment
from p0_hardware_bench_evidence_readiness import evaluate_hardware_bench_readiness
from p1_002_host_hardening_readiness import (
    template as host_template,
    validate_host_hardening_manifest,
)
from p1_host_hardware_preparation_reconciliation import (
    HostHardwareReconciliationError,
    _assert_bench_shape,
    _assert_deployment_shape,
    _assert_host_shape,
    _bench_packet_result,
    _deployment_result,
    _host_manifest_result,
    evaluate_host_hardware_preparation,
)


def _expect_error(callback, label: str) -> None:
    try:
        callback()
    except (HostHardwareReconciliationError, ValueError):
        print(f"[P1 Host-Hardware Reconciliation] {label}: PASSED")
        return
    raise AssertionError(f"{label}: unsafe mutation was accepted")


def test_reconciliation_passes_without_target_host_execution():
    report = evaluate_host_hardware_preparation()
    assert report["all_passed"] is True
    assert report["decision"] == "P1_HOST_HARDWARE_PREPARATION_RECONCILED_PENDING_TARGET_HOST_EVIDENCE"
    assert report["target_model"] == "Acer Spin N17H2"
    assert report["target_role"] == "FIXED_EDGE_HUB_CANDIDATE"
    assert report["host_execution_status"] == "NOT_STARTED"
    assert report["physical_execution_performed"] is False
    assert report["real_target_host_evidence"] == "UNVERIFIED"
    assert report["external_submission_allowed"] is False
    assert report["authorization_promoted"] is False
    print("[P1 Host-Hardware Reconciliation] local-only reconciliation decision: PASSED")


def test_deployment_defaults_are_pilot_safe_and_outside_source_tree():
    result = _deployment_result()
    _assert_deployment_shape(result)
    assert result["status"] == "PASS"
    assert result["physical_validation"] == "UNVERIFIED"
    assert result["clinical_validation"] == "PENDING"
    assert all(item["status"] != "FAIL" for item in result["checks"])
    print("[P1 Host-Hardware Reconciliation] deployment defaults and path separation: PASSED")


def test_deployment_wildcard_and_source_tree_paths_fail_closed():
    env = {
        "SW_ENVIRONMENT": "pilot",
        "SW_AUTO_CREATE_DB": "false",
        "SW_SEED_DATA": "false",
        "SW_ENABLE_DOCS": "false",
        "SW_ALLOWED_HOSTS": "*",
        "SW_AUTH_MODE": "oidc",
        "SW_OIDC_ISSUER": "https://issuer.fixture.invalid",
        "SW_OIDC_AUDIENCE": "fixture",
        "SW_OIDC_JWKS_URL": "https://issuer.fixture.invalid/jwks",
        "SW_DATABASE_PATH": "/tmp/ward_hub.db",
        "SW_TELEMETRY_STATE_PATH": "/tmp/state.json",
        "SW_AUDIT_LOG_PATH": "/tmp/audit.jsonl",
        "SW_DEVICE_TRUST_MODE": "enforce",
    }
    result = validate_environment(env, project_root=__import__("pathlib").Path(__file__).resolve().parent, bind_host="0.0.0.0", port=8080)
    assert result.status == "FAIL"
    failures = {item["check"] for item in result.checks if item["status"] == "FAIL"}
    assert {"loopback_binding", "allowed_hosts"}.issubset(failures)
    assert {"path:SW_DATABASE_PATH", "path:SW_TELEMETRY_STATE_PATH", "path:SW_AUDIT_LOG_PATH"}.isdisjoint(failures)
    print("[P1 Host-Hardware Reconciliation] wildcard binding/path fail-closed behavior: PASSED")


def test_host_template_execution_promotion_is_rejected():
    manifest = host_template()
    manifest["status"] = "HOST_HARDENING_EXECUTED"
    _expect_error(lambda: validate_host_hardening_manifest(manifest, template_only=True), "Host execution status promotion")

    manifest = host_template()
    manifest["host_execution_status"] = "EXECUTED"
    _expect_error(lambda: validate_host_hardening_manifest(manifest, template_only=True), "Host execution flag promotion")

    manifest = host_template()
    manifest["external_owner_appointment"] = "owner:real-operator"
    _expect_error(lambda: validate_host_hardening_manifest(manifest, template_only=True), "External owner injection")


def test_hardware_packet_target_and_observed_result_promotion_are_rejected():
    packet = evaluate_hardware_bench_readiness()
    assert packet["all_passed"] is True
    assert packet["target_model"] == "Acer Spin N17H2"
    assert packet["physical_execution_performed"] is False
    assert packet["observed_result_count"] == 0

    mutated = deepcopy(packet)
    mutated["target_model"] = "BMAX i11_s"
    _expect_error(lambda: _assert_bench_shape(mutated), "Bench target mutation")

    mutated = deepcopy(packet)
    mutated["observed_result_count"] = 1
    _expect_error(lambda: _assert_bench_shape(mutated), "Observed result preclaim")

    mutated = deepcopy(packet)
    mutated["physical_execution_performed"] = True
    _expect_error(lambda: _assert_bench_shape(mutated), "Physical execution promotion")


def test_raw_identity_and_secret_markers_are_not_accepted_by_host_contract():
    manifest = host_template()
    manifest["operator_ref"] = "operator:HN-2026-9988"
    _expect_error(lambda: validate_host_hardening_manifest(manifest, template_only=True), "Host raw identity marker")

    manifest = host_template()
    manifest["evidence_store_ref"] = "secret=fixture-value"
    _expect_error(lambda: validate_host_hardening_manifest(manifest, template_only=True), "Host secret marker")


def test_cross_artifact_mutation_does_not_change_fresh_evaluation():
    report = evaluate_host_hardware_preparation()
    mutated = deepcopy(report)
    mutated["target_model"] = "BMAX i11_s"
    mutated["host_execution_status"] = "EXECUTED"
    mutated["physical_execution_performed"] = True
    mutated["authorization_boundary"]["production_authorized"] = True
    mutated["external_gate_snapshot"]["passed"] = 10

    fresh = evaluate_host_hardware_preparation()
    assert fresh["all_passed"] is True
    assert fresh["target_model"] == "Acer Spin N17H2"
    assert fresh["host_execution_status"] == "NOT_STARTED"
    assert fresh["physical_execution_performed"] is False
    assert fresh["authorization_boundary"]["production_authorized"] is False
    assert fresh["external_gate_snapshot"]["passed"] == 0
    assert fresh["external_submission_allowed"] is False
    print("[P1 Host-Hardware Reconciliation] returned evidence mutation isolation: PASSED")


def test_boundary_values_are_explicitly_locked():
    report = evaluate_host_hardware_preparation()
    assert report["clinical_validation_authorized"] is False
    assert report["production_authorized"] is False
    assert report["runtime_authority"] == "NONE"
    assert report["external_authority"] == "NONE"
    assert report["pilot_gate_status"] == "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION"
    assert report["external_gate_snapshot"] == {"blocked": 7, "open": 3, "evidence_submitted": 0, "passed": 0}
    assert report["software_evidence_only"] is True
    assert report["fixture_only"] is True
    assert report["patient_data_used"] is False
    print("[P1 Host-Hardware Reconciliation] explicit authority/gate boundary: PASSED")


def run() -> None:
    tests = [
        test_reconciliation_passes_without_target_host_execution,
        test_deployment_defaults_are_pilot_safe_and_outside_source_tree,
        test_deployment_wildcard_and_source_tree_paths_fail_closed,
        test_host_template_execution_promotion_is_rejected,
        test_hardware_packet_target_and_observed_result_promotion_are_rejected,
        test_raw_identity_and_secret_markers_are_not_accepted_by_host_contract,
        test_cross_artifact_mutation_does_not_change_fresh_evaluation,
        test_boundary_values_are_explicitly_locked,
    ]
    for test in tests:
        test()
    print(f"[P1 Host-Hardware Reconciliation] focused/adversarial tests: {len(tests)} PASSED")
    print("P1_HOST_HARDWARE_PREPARATION_RECONCILIATION_TESTS_PASSED")


if __name__ == "__main__":
    run()
