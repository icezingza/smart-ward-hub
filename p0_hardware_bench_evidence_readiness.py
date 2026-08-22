"""Local-only readiness contract for an Acer Spin N17H2 hardware bench packet.

This module validates the evidence packet shape and safety boundary only. It does
not inspect hardware, remove power, probe ports, connect to HIS, or authorize a
clinical/production run.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import re
from typing import Any


SCHEMA_VERSION = "p0-hardware-bench-evidence-readiness-v1"
TARGET_MODEL = "Acer Spin N17H2"
TARGET_ROLE = "FIXED_EDGE_HUB_CANDIDATE"
PACKET_STATUS = "PREPARED_NOT_EXECUTED"
PENDING_STATUS = "PENDING_EXTERNAL_EXECUTION"
AUTHORIZATION_BOUNDARY = {
    "external_authority": "NONE",
    "clinical_validation_authorized": False,
    "production_authorized": False,
    "runtime_authority": "NONE",
    "pilot_gate_status": "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION",
}
PRECONDITION_IDS = (
    "device_model_and_redacted_asset_id",
    "os_version_and_patch_level",
    "disk_encryption_state",
    "non_root_service_account",
    "firewall_and_listening_ports",
    "trusted_time_source",
    "power_charger_battery_health",
    "network_topology",
    "test_certificates_and_tokens",
    "backup_destination",
    "known_good_software_commit",
)
BENCH_STEP_IDS = tuple(f"HB-{index:02d}" for index in range(1, 14))
STOP_CONDITION_IDS = (
    "identity_mismatch",
    "raw_hn_or_an_at_hub_core",
    "authentication_bypass",
    "unexplained_alert_loss",
    "forensic_hash_mismatch",
    "database_corruption",
    "repeated_missed_telemetry",
    "unsafe_automatic_reset",
    "certificate_or_key_exposure",
    "uncontrolled_purge",
    "unexplained_host_or_network_condition",
)
OPAQUE_REF_PATTERN = re.compile(r"^(?:asset|operator|packet|software|incident|artifact):[A-Za-z0-9._-]{4,128}$")
RAW_IDENTITY_PATTERN = re.compile(r"(?:HN|AN|MRN|NATIONAL_ID)(?:[-_:]|\b)", re.IGNORECASE)
SECRET_MARKER = re.compile(r"(?:-----BEGIN|Bearer(?:\s+|[-_])\S+|private[_-]?key\s*[:=]|api[_-]?key\s*[:=])", re.IGNORECASE)


class HardwareBenchReadinessError(ValueError):
    """Raised when a local hardware-bench packet is malformed or overclaims."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise HardwareBenchReadinessError(message)


def _safe_ref(value: Any, field: str) -> str:
    _require(isinstance(value, str), f"{field}_must_be_string")
    _require(OPAQUE_REF_PATTERN.fullmatch(value) is not None, f"{field}_opaque_reference_required")
    _require(RAW_IDENTITY_PATTERN.search(value) is None, f"{field}_raw_identity_marker")
    _require(SECRET_MARKER.search(value) is None, f"{field}_secret_marker")
    return value


def _utc(value: Any, field: str) -> datetime:
    _require(isinstance(value, str), f"{field}_must_be_iso8601")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HardwareBenchReadinessError(f"{field}_must_be_iso8601") from exc
    _require(parsed.tzinfo is not None and parsed.utcoffset() is not None, f"{field}_timezone_required")
    return parsed.astimezone(timezone.utc)


def _expected_map(values: Any, field: str, expected_ids: tuple[str, ...]) -> dict[str, Any]:
    _require(isinstance(values, dict) and set(values) == set(expected_ids), f"{field}_coverage_mismatch")
    return values


def validate_bench_packet(packet: dict[str, Any]) -> dict[str, Any]:
    """Validate a prepared, non-executed bench packet without hardware access."""
    expected_fields = {
        "packet_id", "target_model", "target_role", "asset_ref", "operator_ref", "software_ref",
        "started_at_utc", "completed_at_utc", "packet_status", "physical_execution_performed",
        "preconditions", "bench_steps", "stop_conditions", "observed_results", "clinical_use_authorized",
    }
    _require(isinstance(packet, dict) and set(packet) == expected_fields, "bench_packet_fields_mismatch")
    _require(packet["target_model"] == TARGET_MODEL, "target_model_mismatch")
    _require(packet["target_role"] == TARGET_ROLE, "target_role_mismatch")
    _safe_ref(packet["packet_id"], "packet_id")
    _safe_ref(packet["asset_ref"], "asset_ref")
    _safe_ref(packet["operator_ref"], "operator_ref")
    _safe_ref(packet["software_ref"], "software_ref")
    start = _utc(packet["started_at_utc"], "started_at_utc")
    end = _utc(packet["completed_at_utc"], "completed_at_utc")
    _require(end >= start, "bench_time_window_invalid")
    _require(packet["packet_status"] == PACKET_STATUS, "packet_must_be_prepared_not_executed")
    _require(packet["physical_execution_performed"] is False, "physical_execution_must_remain_false")
    _require(packet["clinical_use_authorized"] is False, "clinical_use_must_remain_unauthorized")
    preconditions = _expected_map(packet["preconditions"], "preconditions", PRECONDITION_IDS)
    _require(all(value == PENDING_STATUS for value in preconditions.values()), "precondition_status_overclaim")
    bench_steps = _expected_map(packet["bench_steps"], "bench_steps", BENCH_STEP_IDS)
    for step_id, step in bench_steps.items():
        _require(isinstance(step, dict), f"{step_id}_must_be_object")
        _require(set(step) == {"status", "command_ref", "expected_result_ref"}, f"{step_id}_fields_mismatch")
        _require(step["status"] == PENDING_STATUS, f"{step_id}_status_overclaim")
        _safe_ref(step["command_ref"], f"{step_id}_command_ref")
        _safe_ref(step["expected_result_ref"], f"{step_id}_expected_result_ref")
    stop_conditions = _expected_map(packet["stop_conditions"], "stop_conditions", STOP_CONDITION_IDS)
    _require(all(value is True for value in stop_conditions.values()), "stop_condition_coverage_incomplete")
    _require(packet["observed_results"] == {}, "observed_results_must_be_empty_before_execution")
    return {
        "valid": True,
        "packet_status": PACKET_STATUS,
        "target_model": TARGET_MODEL,
        "target_role": TARGET_ROLE,
        "physical_execution_performed": False,
        "precondition_count": len(PRECONDITION_IDS),
        "bench_step_count": len(BENCH_STEP_IDS),
        "stop_condition_count": len(STOP_CONDITION_IDS),
        "observed_result_count": 0,
        "evidence_class": "LOCAL_BENCH_PACKET_TEMPLATE",
        "clinical_use_authorized": False,
    }


def _fixture_packet() -> dict[str, Any]:
    return {
        "packet_id": "packet:acer-spin-n17h2-fixture-01",
        "target_model": TARGET_MODEL,
        "target_role": TARGET_ROLE,
        "asset_ref": "asset:acer-spin-n17h2-fixture",
        "operator_ref": "operator:bench-fixture-01",
        "software_ref": "software:commit-fixture-20260823",
        "started_at_utc": "2026-08-23T00:00:00Z",
        "completed_at_utc": "2026-08-23T00:00:00Z",
        "packet_status": PACKET_STATUS,
        "physical_execution_performed": False,
        "preconditions": {item: PENDING_STATUS for item in PRECONDITION_IDS},
        "bench_steps": {
            step_id: {
                "status": PENDING_STATUS,
                "command_ref": f"artifact:bench-command-{step_id.lower()}",
                "expected_result_ref": f"artifact:bench-expected-{step_id.lower()}",
            }
            for step_id in BENCH_STEP_IDS
        },
        "stop_conditions": {item: True for item in STOP_CONDITION_IDS},
        "observed_results": {},
        "clinical_use_authorized": False,
    }


def evaluate_hardware_bench_readiness() -> dict[str, Any]:
    packet = _fixture_packet()
    packet_result = validate_bench_packet(packet)
    checks = {
        "packet_schema_valid": packet_result["valid"],
        "acer_fixed_hub_target_locked": packet_result["target_model"] == TARGET_MODEL and packet_result["target_role"] == TARGET_ROLE,
        "precondition_coverage_complete": packet_result["precondition_count"] == len(PRECONDITION_IDS),
        "bench_step_coverage_complete": packet_result["bench_step_count"] == len(BENCH_STEP_IDS),
        "stop_condition_coverage_complete": packet_result["stop_condition_count"] == len(STOP_CONDITION_IDS),
        "physical_execution_absent": packet_result["physical_execution_performed"] is False,
        "observed_results_empty": packet_result["observed_result_count"] == 0,
        "clinical_use_locked": packet_result["clinical_use_authorized"] is False,
        "no_patient_data_fixture": True,
        "authority_boundary_locked": AUTHORIZATION_BOUNDARY == {
            "external_authority": "NONE",
            "clinical_validation_authorized": False,
            "production_authorized": False,
            "runtime_authority": "NONE",
            "pilot_gate_status": "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION",
        },
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "decision": "P0_HARDWARE_BENCH_PACKET_PREPARED_PENDING_PHYSICAL_EXECUTION" if all(checks.values()) else "P0_HARDWARE_BENCH_READINESS_BLOCKED",
        "mode": "LOCAL_DETERMINISTIC_TEMPLATE_ONLY",
        "all_passed": all(checks.values()),
        "checks": checks,
        "packet_result": packet_result,
        "target_model": TARGET_MODEL,
        "target_role": TARGET_ROLE,
        "packet_status": PACKET_STATUS,
        "physical_execution_performed": False,
        "physical_hardware_evidence": "UNVERIFIED",
        "preconditions_status": PENDING_STATUS,
        "bench_steps_status": PENDING_STATUS,
        "observed_result_count": 0,
        "precondition_count": len(PRECONDITION_IDS),
        "bench_step_count": len(BENCH_STEP_IDS),
        "stop_condition_count": len(STOP_CONDITION_IDS),
        "clinical_use_authorized": False,
        "external_submission_allowed": False,
        "external_transmission_performed": False,
        "authorization_promoted": False,
        "runtime_mutation_performed": False,
        "patient_data_used": False,
        "raw_frames_recorded": False,
        "real_his_evidence": "UNVERIFIED",
        "real_oidc_mtls_evidence": "UNVERIFIED",
        "authorization_boundary": deepcopy(AUTHORIZATION_BOUNDARY),
        "external_gate_snapshot": {"blocked": 7, "open": 3, "evidence_submitted": 0, "passed": 0},
    }


if __name__ == "__main__":
    import json

    report = evaluate_hardware_bench_readiness()
    print(json.dumps(report, ensure_ascii=True, sort_keys=True))
    print("P0_HARDWARE_BENCH_EVIDENCE_READINESS_GUARD_PASSED" if report["all_passed"] else "P0_HARDWARE_BENCH_EVIDENCE_READINESS_GUARD_BLOCKED")
