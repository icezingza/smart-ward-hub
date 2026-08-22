"""Reconcile local host, deployment and Acer bench preparation evidence.

This is a read-only software preparation control. It does not inspect or mutate
a target Windows host, open a socket, execute a service command, or authorize
pilot/clinical/production use.
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any

from deployment_readiness import validate_environment
from p0_hardware_bench_evidence_readiness import evaluate_hardware_bench_readiness
from p1_002_host_hardening_readiness import template as host_template
from p1_002_host_hardening_readiness import validate_host_hardening_manifest


SCHEMA_VERSION = "p1-host-hardware-preparation-reconciliation-v1"
PROJECT_ROOT = Path(__file__).resolve().parent
EXPECTED_BOUNDARY = {
    "external_authority": "NONE",
    "clinical_validation_authorized": False,
    "production_authorized": False,
    "runtime_authority": "NONE",
    "pilot_gate_status": "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION",
}
EXPECTED_GATE_SNAPSHOT = {"blocked": 7, "open": 3, "evidence_submitted": 0, "passed": 0}


class HostHardwareReconciliationError(ValueError):
    """Raised when preparation artifacts disagree or overclaim execution."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise HostHardwareReconciliationError(message)


def _pilot_environment() -> dict[str, str]:
    return {
        "SW_ENVIRONMENT": "pilot",
        "SW_AUTO_CREATE_DB": "false",
        "SW_SEED_DATA": "false",
        "SW_ENABLE_DOCS": "false",
        "SW_ALLOWED_HOSTS": "127.0.0.1",
        "SW_AUTH_MODE": "oidc",
        "SW_OIDC_ISSUER": "https://issuer.fixture.invalid",
        "SW_OIDC_AUDIENCE": "smart-ward-hub-fixture",
        "SW_OIDC_JWKS_URL": "https://issuer.fixture.invalid/.well-known/jwks.json",
        "SW_DATABASE_PATH": "/var/lib/smart-ward-hub/ward_hub.db",
        "SW_TELEMETRY_STATE_PATH": "/var/lib/smart-ward-hub/telemetry-state.json",
        "SW_AUDIT_LOG_PATH": "/var/log/smart-ward-hub/audit.jsonl",
        "SW_DEVICE_TRUST_MODE": "enforce",
    }


def _deployment_result() -> dict[str, Any]:
    result = validate_environment(
        _pilot_environment(),
        project_root=PROJECT_ROOT,
        bind_host="127.0.0.1",
        port=8080,
    )
    return {
        "status": result.status,
        "checks": result.checks,
        "physical_validation": result.physical_validation,
        "clinical_validation": result.clinical_validation,
    }


def _host_manifest_result() -> dict[str, Any]:
    result = validate_host_hardening_manifest(host_template(), template_only=True)
    return {
        "valid": result["valid"],
        "status": result["status"],
        "host_execution_status": result["host_execution_status"],
        "physical_validation": result["physical_validation"],
        "software_evidence_only": result["software_evidence_only"],
        "external_owner_appointment": result["external_owner_appointment"],
    }


def _bench_packet_result() -> dict[str, Any]:
    result = evaluate_hardware_bench_readiness()
    return {
        "all_passed": result["all_passed"],
        "decision": result["decision"],
        "target_model": result["target_model"],
        "target_role": result["target_role"],
        "packet_status": result["packet_status"],
        "physical_execution_performed": result["physical_execution_performed"],
        "physical_hardware_evidence": result["physical_hardware_evidence"],
        "observed_result_count": result["observed_result_count"],
        "precondition_count": result["precondition_count"],
        "bench_step_count": result["bench_step_count"],
        "stop_condition_count": result["stop_condition_count"],
    }


def _assert_deployment_shape(deployment: dict[str, Any]) -> None:
    _require(deployment["status"] == "PASS", "deployment configuration fixture must pass")
    _require(deployment["physical_validation"] == "UNVERIFIED", "deployment fixture physical state must remain unverified")
    _require(deployment["clinical_validation"] == "PENDING", "deployment fixture clinical state must remain pending")
    failures = [check for check in deployment["checks"] if check.get("status") == "FAIL"]
    _require(not failures, "deployment configuration fixture contains hard failures")


def _assert_host_shape(host: dict[str, Any]) -> None:
    _require(host["valid"] is True, "host hardening template is invalid")
    _require(host["status"] == "HOST_HARDENING_SOFTWARE_PREPARATION_READY", "host status overclaims or drifts")
    _require(host["host_execution_status"] == "NOT_STARTED", "host execution must remain not started")
    _require(host["physical_validation"] == "UNVERIFIED", "host physical validation must remain unverified")
    _require(host["software_evidence_only"] is True, "host evidence class must remain software-only")
    _require(host["external_owner_appointment"] == "PENDING_EXTERNAL_APPOINTMENT", "host owner appointment must remain pending")


def _assert_bench_shape(bench: dict[str, Any]) -> None:
    _require(bench["all_passed"] is True, "Acer bench packet readiness failed")
    _require(bench["target_model"] == "Acer Spin N17H2", "fixed Hub target mismatch")
    _require(bench["target_role"] == "FIXED_EDGE_HUB_CANDIDATE", "bench target role mismatch")
    _require(bench["packet_status"] == "PREPARED_NOT_EXECUTED", "bench packet execution status overclaims")
    _require(bench["physical_execution_performed"] is False, "physical execution must remain false")
    _require(bench["physical_hardware_evidence"] == "UNVERIFIED", "physical hardware evidence must remain unverified")
    _require(bench["observed_result_count"] == 0, "bench packet cannot contain observed results before execution")
    _require(bench["precondition_count"] == 11, "bench precondition count drifted")
    _require(bench["bench_step_count"] == 13, "bench step count drifted")
    _require(bench["stop_condition_count"] == 11, "bench stop condition count drifted")


def evaluate_host_hardware_preparation() -> dict[str, Any]:
    deployment = _deployment_result()
    host = _host_manifest_result()
    bench = _bench_packet_result()
    _assert_deployment_shape(deployment)
    _assert_host_shape(host)
    _assert_bench_shape(bench)

    checks = {
        "deployment_defaults_pass": deployment["status"] == "PASS",
        "deployment_physical_validation_unverified": deployment["physical_validation"] == "UNVERIFIED",
        "deployment_clinical_validation_pending": deployment["clinical_validation"] == "PENDING",
        "host_manifest_template_valid": host["valid"] is True,
        "host_execution_not_started": host["host_execution_status"] == "NOT_STARTED",
        "host_physical_validation_unverified": host["physical_validation"] == "UNVERIFIED",
        "host_software_evidence_only": host["software_evidence_only"] is True,
        "bench_packet_ready": bench["all_passed"] is True,
        "bench_target_fixed_hub_locked": bench["target_model"] == "Acer Spin N17H2" and bench["target_role"] == "FIXED_EDGE_HUB_CANDIDATE",
        "bench_execution_not_performed": bench["physical_execution_performed"] is False,
        "bench_observed_results_empty": bench["observed_result_count"] == 0,
        "cross_artifact_physical_state_consistent": deployment["physical_validation"] == "UNVERIFIED" and host["physical_validation"] == "UNVERIFIED" and bench["physical_hardware_evidence"] == "UNVERIFIED",
        "cross_artifact_no_clinical_claim": deployment["clinical_validation"] == "PENDING",
        "authority_boundary_locked": EXPECTED_BOUNDARY == {
            "external_authority": "NONE",
            "clinical_validation_authorized": False,
            "production_authorized": False,
            "runtime_authority": "NONE",
            "pilot_gate_status": "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION",
        },
        "external_gate_snapshot_locked": EXPECTED_GATE_SNAPSHOT == {"blocked": 7, "open": 3, "evidence_submitted": 0, "passed": 0},
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "evidence_type": "P1_HOST_HARDWARE_PREPARATION_RECONCILIATION",
        "decision": "P1_HOST_HARDWARE_PREPARATION_RECONCILED_PENDING_TARGET_HOST_EVIDENCE" if all(checks.values()) else "P1_HOST_HARDWARE_PREPARATION_RECONCILIATION_BLOCKED",
        "mode": "LOCAL_DETERMINISTIC_RECONCILIATION_ONLY",
        "all_passed": all(checks.values()),
        "checks": checks,
        "deployment_result": deployment,
        "host_manifest_result": host,
        "bench_packet_result": bench,
        "target_model": "Acer Spin N17H2",
        "target_role": "FIXED_EDGE_HUB_CANDIDATE",
        "host_execution_status": "NOT_STARTED",
        "physical_validation": "UNVERIFIED",
        "physical_execution_performed": False,
        "observed_result_count": 0,
        "clinical_validation": "PENDING",
        "clinical_validation_authorized": False,
        "production_authorized": False,
        "runtime_authority": "NONE",
        "external_authority": "NONE",
        "pilot_gate_status": "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION",
        "external_gate_snapshot": deepcopy(EXPECTED_GATE_SNAPSHOT),
        "authorization_boundary": deepcopy(EXPECTED_BOUNDARY),
        "external_submission_allowed": False,
        "external_transmission_performed": False,
        "runtime_mutation_performed": False,
        "authorization_promoted": False,
        "software_evidence_only": True,
        "fixture_only": True,
        "patient_data_used": False,
        "hardware_evidence": "UNVERIFIED",
        "real_target_host_evidence": "UNVERIFIED",
        "redaction_verified": True,
        "claim_boundary": "CONTROLLED_PRODUCTION_PROTOTYPE",
    }


if __name__ == "__main__":
    print(json.dumps(evaluate_host_hardware_preparation(), ensure_ascii=True, indent=2, sort_keys=True))
    print("P1_HOST_HARDWARE_PREPARATION_RECONCILIATION_GUARD_PASSED")
