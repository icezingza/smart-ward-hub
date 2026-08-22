"""Fixture-only cross-transport conformance checks for P2-002.

This module exercises the existing transport-neutral adapter contract without
opening sockets, serial ports, BLE sessions, brokers, schedulers, or providers.
Hardware evidence remains explicitly unverified.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import json
from typing import Any, Mapping

from edge_iot_adapters import TransportContext, build_adapter


TRANSPORTS = ("mqtt", "websocket", "serial", "ble")
DEVICE_ID = "device-conformance-001"
KEY_ID = "key-conformance-001"
SIGNATURE = "synthetic-signature-placeholder"
TIMESTAMP = "2026-08-22T00:00:00+00:00"
NORMALIZED_FIELDS = (
    "schema_version",
    "device_id",
    "sequence",
    "ppg",
    "accel_x",
    "accel_y",
    "accel_z",
    "battery_pct",
)
FAILURE_CASES = {
    "missing_signature": "signature_missing",
    "pii_field": "pii_or_secret_field_detected",
    "command_field": "command_field_detected",
    "source_identity_mismatch": "source_device_mismatch",
    "unknown_outer_field": "unknown_outer_field",
    "oversized_frame": "frame_too_large",
    "wrong_transport_context": "transport_context_mismatch",
}
LOCKED_BOUNDARY = {
    "external_authority": "NONE",
    "clinical_validation_authorized": False,
    "production_authorized": False,
    "runtime_authority": "NONE",
    "pilot_gate_status": "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION",
}


class ConformanceDecision(StrEnum):
    P2_002_ADAPTER_CONFORMANCE_VERIFIED = "P2_002_ADAPTER_CONFORMANCE_VERIFIED"
    P2_002_ADAPTER_CONFORMANCE_BLOCKED = "P2_002_ADAPTER_CONFORMANCE_BLOCKED"


class ConformanceCode(StrEnum):
    NORMALIZATION_MISMATCH = "NORMALIZATION_MISMATCH"
    FAILURE_MATRIX_MISMATCH = "FAILURE_MATRIX_MISMATCH"
    REDACTION_FAILURE = "REDACTION_FAILURE"
    INPUT_MUTATION = "INPUT_MUTATION"
    AUTHORIZATION_BOUNDARY_MUTATED = "AUTHORIZATION_BOUNDARY_MUTATED"
    EXECUTION_BOUNDARY_MUTATED = "EXECUTION_BOUNDARY_MUTATED"


@dataclass(frozen=True, slots=True)
class ConformanceResult:
    decision: str
    remediation_codes: tuple[str, ...]
    checks: dict[str, bool]
    normalized_by_transport: dict[str, dict[str, Any]]
    failure_matrix: dict[str, dict[str, str]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "remediation_codes": list(self.remediation_codes),
            "checks": dict(self.checks),
            "normalized_by_transport": {
                key: dict(value) for key, value in self.normalized_by_transport.items()
            },
            "failure_matrix": {
                key: dict(value) for key, value in self.failure_matrix.items()
            },
        }


def build_packet(sequence: int = 7) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "device_id": DEVICE_ID,
        "sequence": sequence,
        "timestamp": TIMESTAMP,
        "ppg": 0.82,
        "accel_x": 0.02,
        "accel_y": 0.01,
        "accel_z": 1.01,
        "skin_temp": 36.7,
        "battery_pct": 87.0,
        "heart_rate": 72.0,
        "spo2": 98.0,
    }


def build_envelope(sequence: int = 7) -> dict[str, Any]:
    return {
        "packet": build_packet(sequence),
        "source_device_id": DEVICE_ID,
        "key_id": KEY_ID,
        "signature_b64": SIGNATURE,
        "mapping_version": "conformance-fixture-v1",
        "gateway_attested": False,
    }


def _context(transport: str, *, max_frame_bytes: int = 16_384) -> TransportContext:
    return TransportContext(
        adapter_id=f"adapter-{transport}-conformance",
        transport=transport,  # type: ignore[arg-type]
        source_id=DEVICE_ID,
        require_signature=True,
        max_frame_bytes=max_frame_bytes,
        gateway_attested=False,
    )


def _encode(payload: Mapping[str, Any], transport: str) -> bytes | str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    if transport == "mqtt" or transport == "websocket":
        return encoded
    frame = encoded.encode("utf-8")
    return frame + b"\r\n" if transport == "serial" else frame


def _decode(transport: str, payload: Mapping[str, Any], *, max_frame_bytes: int = 16_384):
    adapter = build_adapter(transport, f"adapter-{transport}-conformance")  # type: ignore[arg-type]
    return adapter.decode(_encode(payload, transport), _context(transport, max_frame_bytes=max_frame_bytes))


def _normalized_fields(result: Any) -> dict[str, Any]:
    if not result.normalized or result.packet is None:
        return {}
    packet = result.packet.model_dump(mode="json")
    return {field: packet.get(field) for field in NORMALIZED_FIELDS}


def _failure_payloads() -> dict[str, dict[str, Any]]:
    missing = build_envelope()
    missing.pop("key_id")
    missing.pop("signature_b64")

    pii = build_envelope()
    pii["packet"] = {**pii["packet"], "patient_token": "opaque-fixture-token"}

    command = build_envelope()
    command["command_type"] = "RESET_CONFIRM"

    mismatch = build_envelope()
    mismatch["source_device_id"] = "device-other-001"

    unknown = build_envelope()
    unknown["unexpected"] = "reject-me"

    return {
        "missing_signature": missing,
        "pii_field": pii,
        "command_field": command,
        "source_identity_mismatch": mismatch,
        "unknown_outer_field": unknown,
    }


def _add(codes: list[str], code: ConformanceCode) -> None:
    if code.value not in codes:
        codes.append(code.value)


def evaluate_conformance(
    *,
    authorization_boundary: Mapping[str, Any] | None = None,
    external_submission_allowed: bool = False,
    authorization_promoted: bool = False,
    runtime_mutation_performed: bool = False,
    external_transmission_performed: bool = False,
) -> ConformanceResult:
    """Evaluate all four adapters using deterministic local fixtures only."""
    codes: list[str] = []
    normalized_by_transport: dict[str, dict[str, Any]] = {}
    failure_matrix: dict[str, dict[str, str]] = {}
    baseline = build_envelope()
    baseline_before = json.loads(json.dumps(baseline, sort_keys=True))

    for transport in TRANSPORTS:
        normalized_by_transport[transport] = _normalized_fields(_decode(transport, baseline))
        failure_matrix[transport] = {}
        for case_name, expected_failure in FAILURE_CASES.items():
            if case_name == "oversized_frame":
                result = _decode(transport, baseline, max_frame_bytes=16)
            elif case_name == "wrong_transport_context":
                adapter = build_adapter(transport, f"adapter-{transport}-conformance")  # type: ignore[arg-type]
                wrong_transport = "websocket" if transport != "websocket" else "mqtt"
                result = adapter.decode(_encode(baseline, transport), _context(wrong_transport))
            else:
                result = _decode(transport, _failure_payloads()[case_name])
            failure_matrix[transport][case_name] = result.failure_class or "NONE"

    expected_normalized = _normalized_fields(_decode("mqtt", baseline))
    checks = {
        "all_transports_normalized": all(
            normalized_by_transport[transport] == expected_normalized for transport in TRANSPORTS
        ),
        "normalized_contract_fields_complete": all(
            set(normalized_by_transport[transport]) == set(NORMALIZED_FIELDS)
            for transport in TRANSPORTS
        ),
        "failure_matrix_complete": all(
            all(failure_matrix[transport].get(case) == expected for case, expected in FAILURE_CASES.items())
            for transport in TRANSPORTS
        ),
        "no_pii_or_command_forwarded": all(
            failure_matrix[transport]["pii_field"] == "pii_or_secret_field_detected"
            and failure_matrix[transport]["command_field"] == "command_field_detected"
            for transport in TRANSPORTS
        ),
        "fixture_input_unchanged": baseline == baseline_before,
        "hardware_evidence_unverified": True,
        "authorization_boundary_locked": dict(authorization_boundary or LOCKED_BOUNDARY) == LOCKED_BOUNDARY,
        "execution_boundary_locked": (
            external_submission_allowed is False
            and authorization_promoted is False
            and runtime_mutation_performed is False
            and external_transmission_performed is False
        ),
    }
    if not checks["all_transports_normalized"] or not checks["normalized_contract_fields_complete"]:
        _add(codes, ConformanceCode.NORMALIZATION_MISMATCH)
    if not checks["failure_matrix_complete"]:
        _add(codes, ConformanceCode.FAILURE_MATRIX_MISMATCH)
    if not checks["no_pii_or_command_forwarded"]:
        _add(codes, ConformanceCode.REDACTION_FAILURE)
    if not checks["fixture_input_unchanged"]:
        _add(codes, ConformanceCode.INPUT_MUTATION)
    if not checks["authorization_boundary_locked"]:
        _add(codes, ConformanceCode.AUTHORIZATION_BOUNDARY_MUTATED)
    if not checks["execution_boundary_locked"]:
        _add(codes, ConformanceCode.EXECUTION_BOUNDARY_MUTATED)

    decision = (
        ConformanceDecision.P2_002_ADAPTER_CONFORMANCE_VERIFIED.value
        if not codes
        else ConformanceDecision.P2_002_ADAPTER_CONFORMANCE_BLOCKED.value
    )
    return ConformanceResult(
        decision=decision,
        remediation_codes=tuple(codes),
        checks=checks,
        normalized_by_transport=normalized_by_transport,
        failure_matrix=failure_matrix,
    )


def check_conformance() -> dict[str, Any]:
    result = evaluate_conformance()
    return {
        "evidence_type": "P2_002_ADAPTER_CONFORMANCE",
        "schema_version": "smart-ward-p2-002-adapter-conformance-v1",
        "decision": result.decision,
        "remediation_codes": list(result.remediation_codes),
        "checks": result.checks,
        "normalized_by_transport": result.normalized_by_transport,
        "failure_matrix": result.failure_matrix,
        "transports": list(TRANSPORTS),
        "selected_software_transport": "serial",
        "hardware_evidence": "UNVERIFIED",
        "fixture_only": True,
        "read_only": True,
        "authorization_boundary": dict(LOCKED_BOUNDARY),
        "external_submission_allowed": False,
        "authorization_promoted": False,
        "runtime_mutation_performed": False,
        "external_transmission_performed": False,
        "claim_boundary": {
            "status": "CONTROLLED_PRODUCTION_PROTOTYPE",
            "clinical_validation": "PENDING",
            "production_ready": False,
        },
    }


if __name__ == "__main__":
    report = check_conformance()
    print(json.dumps(report, sort_keys=True, indent=2))
    print(
        "P2_002_ADAPTER_CONFORMANCE_VERIFIED"
        if report["decision"] == ConformanceDecision.P2_002_ADAPTER_CONFORMANCE_VERIFIED.value
        else "P2_002_ADAPTER_CONFORMANCE_BLOCKED"
    )
