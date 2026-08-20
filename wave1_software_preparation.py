from __future__ import annotations

import hashlib
import json
import re
from typing import Any

SCHEMA_VERSION = "wave1-software-preparation-v1"
PROJECT = "smart-ward-hub"
PENDING = "PENDING_EXTERNAL_APPOINTMENT"
OPAQUE_REF = re.compile(r"^(?:opaque|org|approval|evidence|artifact|scope|window|incident|rollback|commit|freeze):[A-Za-z0-9._-]+$")
SECRET_MARKER = re.compile(r"(?:BEGIN (?:RSA|EC|OPENSSH|DSA|PRIVATE) KEY|Bearer\s+\S+|(?:password|secret|token|private_key)\s*[:=]\s*\S+)", re.IGNORECASE)
RAW_CONTACT = re.compile(r"(?:@|(?<![A-Za-z0-9])\+?\d[\d\s().-]{7,}\d(?![A-Za-z0-9])|\b(?:mr|mrs|ms|นาย|นาง|นางสาว)\b)", re.IGNORECASE)
RAW_IDENTITY = re.compile(r"\b(?:HN|AN|MRN|NATIONAL_ID)(?:\s*[-_:]\s*[A-Z0-9-]{2,}|\s+\d[A-Z0-9-]{1,})\b", re.IGNORECASE)

TRACKS = {
    "oidc_mtls": {
        "gate_id": "GV-04",
        "owner_role": "security_owner",
        "planned_test_ids": ["ID-001", "ID-002", "ID-003", "ID-004", "ID-005", "ID-006", "ID-007"],
        "external_inputs": [
            "isolated_nonproduction_issuer_and_jwks_ref",
            "test_client_and_certificate_chain_ref",
            "approved_dns_network_acl_ref",
            "rotation_revocation_and_rollback_ref",
            "independent_readback_ref",
        ],
    },
    "key_custody": {
        "gate_id": "GV-08",
        "owner_role": "custody_owner",
        "planned_test_ids": ["KT-001", "KT-002", "KT-003", "KT-004", "KT-005", "KT-006", "KT-007"],
        "external_inputs": [
            "manufacturer_ca_or_approved_hsm_ref",
            "dual_control_ceremony_ref",
            "device_inventory_and_public_key_ref",
            "rotation_revocation_distribution_ref",
            "lost_device_and_manual_fallback_ref",
        ],
    },
    "acer_bench": {
        "gate_id": "GV-06",
        "owner_role": "reliability_owner",
        "planned_test_ids": [f"S-{index:03d}" for index in range(1, 16)],
        "external_inputs": [
            "acer_fixture_and_driver_ref",
            "isolated_loopback_fixture_ref",
            "operator_and_independent_witness_ref",
            "power_thermal_soak_window_ref",
            "no_production_network_attestation_ref",
        ],
    },
}

LOCKED_AUTHORIZATION = {
    "external_authority": "NONE",
    "clinical_validation_authorized": False,
    "production_authorized": False,
    "runtime_authority": "NONE",
    "pilot_gate_status": "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION",
}


class PreparationValidationError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise PreparationValidationError(message)


def _exact_keys(value: Any, expected: set[str], field: str) -> None:
    _require(isinstance(value, dict), f"{field} must be an object")
    unknown = sorted(set(value) - expected)
    missing = sorted(expected - set(value))
    _require(not unknown and not missing, f"{field} fields mismatch: unknown={unknown}, missing={missing}")


def _opaque(value: Any, field: str, *, allow_pending: bool = False) -> str:
    _require(isinstance(value, str) and value.strip(), f"{field} must be a non-empty string")
    if allow_pending and value == PENDING:
        return value
    _require(OPAQUE_REF.fullmatch(value) is not None, f"{field} must be an opaque reference")
    _require(RAW_CONTACT.search(value) is None, f"{field} must not contain raw identity/contact data")
    _require(SECRET_MARKER.search(value) is None, f"{field} must not contain secret material")
    return value


def _safe_text(value: Any, field: str) -> str:
    _require(isinstance(value, str) and value.strip(), f"{field} must be non-empty")
    _require(len(value) <= 512, f"{field} too large")
    _require(RAW_CONTACT.search(value) is None and RAW_IDENTITY.search(value) is None, f"{field} must not contain raw identity/contact data")
    _require(SECRET_MARKER.search(value) is None, f"{field} must not contain secret material")
    lowered = value.lower()
    _require("production" not in lowered or "non-production" in lowered or "no production" in lowered, f"{field} must not describe a production target")
    return value


def validate_preparation_manifest(payload: dict[str, Any], *, template_only: bool = False) -> dict[str, Any]:
    _require(isinstance(payload, dict), "manifest must be an object")
    allowed = {
        "schema_version", "project", "package_id", "source_revision", "freeze_manifest_sha256",
        "status", "environment", "execution_status", "external_execution_authorized",
        "authorization_boundary", "tracks", "common_controls", "independent_verification_required",
    }
    unknown = sorted(set(payload) - allowed)
    _require(not unknown, f"unknown fields: {unknown}")
    _require(payload.get("schema_version") == SCHEMA_VERSION, "schema_version mismatch")
    _require(payload.get("project") == PROJECT, "project mismatch")
    if template_only:
        _require(payload.get("package_id") == PENDING, "template package_id must remain pending")
        _require(payload.get("source_revision") == PENDING, "template source_revision must remain pending")
        _require(payload.get("freeze_manifest_sha256") == "0" * 64, "template freeze hash must remain blank-safe")
    else:
        _opaque(payload.get("package_id"), "package_id")
        _opaque(payload.get("source_revision"), "source_revision")
        _require(isinstance(payload.get("freeze_manifest_sha256"), str) and re.fullmatch(r"[a-f0-9]{64}", payload["freeze_manifest_sha256"]) is not None, "freeze_manifest_sha256 must be lowercase SHA-256")
    _require(payload.get("status") == "SOFTWARE_PREPARATION_READY", "status must remain SOFTWARE_PREPARATION_READY")
    _require(payload.get("environment") == "ISOLATED_NON_PRODUCTION_ONLY", "environment must remain isolated non-production")
    _require(payload.get("execution_status") == "NOT_STARTED", "execution_status must remain NOT_STARTED")
    _require(payload.get("external_execution_authorized") is False, "local preparation cannot authorize external execution")
    _require(payload.get("authorization_boundary") == LOCKED_AUTHORIZATION, "authorization boundary must remain locked")
    _require(payload.get("independent_verification_required") is True, "independent_verification_required must be true")

    common = payload.get("common_controls")
    _exact_keys(common, {"synthetic_data_only", "raw_patient_data_allowed", "production_credentials_allowed", "private_key_material_allowed", "raw_serial_frames_allowed", "evidence_class", "scope_ref", "window_ref", "rollback_ref", "stop_rule"}, "common_controls")
    _require(common.get("synthetic_data_only") is True, "synthetic_data_only must be true")
    _require(common.get("raw_patient_data_allowed") is False, "raw_patient_data_allowed must be false")
    _require(common.get("production_credentials_allowed") is False, "production_credentials_allowed must be false")
    _require(common.get("private_key_material_allowed") is False, "private_key_material_allowed must be false")
    _require(common.get("raw_serial_frames_allowed") is False, "raw_serial_frames_allowed must be false")
    _require(common.get("evidence_class") == "SOFTWARE_PREPARATION_ONLY", "evidence class mismatch")
    _safe_text(common.get("stop_rule"), "common_controls.stop_rule")
    if not template_only:
        _opaque(common.get("scope_ref"), "common_controls.scope_ref")
        _opaque(common.get("window_ref"), "common_controls.window_ref")
        _opaque(common.get("rollback_ref"), "common_controls.rollback_ref")
    else:
        for key in ("scope_ref", "window_ref", "rollback_ref"):
            _require(common.get(key) == PENDING, f"template {key} must remain pending")

    tracks = payload.get("tracks")
    _require(isinstance(tracks, dict) and set(tracks) == set(TRACKS), "tracks must contain exactly oidc_mtls, key_custody and acer_bench")
    for name, contract in TRACKS.items():
        track = tracks[name]
        _exact_keys(track, {"gate_id", "owner_role", "owner_appointment_ref", "test_matrix_ref", "status", "execution_status", "hardware_or_external_validation", "planned_test_ids", "external_inputs", "stop_conditions"}, f"tracks.{name}")
        _require(track.get("gate_id") == contract["gate_id"], f"tracks.{name}.gate_id mismatch")
        _require(track.get("owner_role") == contract["owner_role"], f"tracks.{name}.owner_role mismatch")
        _require(track.get("status") == "PREPARED_SOFTWARE_ONLY", f"tracks.{name}.status mismatch")
        _require(track.get("execution_status") == "NOT_STARTED", f"tracks.{name}.execution_status mismatch")
        _require(track.get("hardware_or_external_validation") == "UNVERIFIED", f"tracks.{name} external validation must remain unverified")
        _require(track.get("planned_test_ids") == contract["planned_test_ids"], f"tracks.{name}.planned_test_ids mismatch")
        _require(track.get("external_inputs") == contract["external_inputs"], f"tracks.{name}.external_inputs mismatch")
        _require(all(isinstance(item, str) and item.strip() for item in track["planned_test_ids"]), f"tracks.{name}.planned_test_ids must contain strings")
        _require(all(isinstance(item, str) and item.strip() for item in track["external_inputs"]), f"tracks.{name}.external_inputs must contain strings")
        _require(isinstance(track.get("stop_conditions"), list) and track["stop_conditions"], f"tracks.{name}.stop_conditions must be non-empty")
        for index, condition in enumerate(track["stop_conditions"]):
            _safe_text(condition, f"tracks.{name}.stop_conditions[{index}]")
        if not template_only:
            _opaque(track.get("owner_appointment_ref"), f"tracks.{name}.owner_appointment_ref")
            _opaque(track.get("test_matrix_ref"), f"tracks.{name}.test_matrix_ref")
        else:
            _require(track.get("owner_appointment_ref") == PENDING, f"template tracks.{name}.owner_appointment_ref must remain pending")
            _require(track.get("test_matrix_ref") == PENDING, f"template tracks.{name}.test_matrix_ref must remain pending")

    return {"valid": True, "status": payload["status"], "execution_status": payload["execution_status"], "tracks": sorted(tracks), "external_execution_authorized": False}


def template() -> dict[str, Any]:
    stop_conditions = {
        "oidc_mtls": [
            "issuer/JWKS/TLS host mismatch or untrusted certificate",
            "wrong issuer/audience/role accepted or stale token remains authorized",
            "rotation/revocation/readback failure or endpoint outside allowlist",
        ],
        "key_custody": [
            "private key material appears in any input, log, database or evidence",
            "single-person approval, missing hardware attestation or duplicate device identity",
            "revoked/lost key reactivated or manual fallback not available",
        ],
        "acer_bench": [
            "no approved non-production loopback, unknown driver or unexplained external traffic",
            "COM port absent, raw PII/secret/command observed or replay accepted",
            "memory bound, power/thermal/soak, restart or audit evidence fails",
        ],
    }
    tracks: dict[str, Any] = {}
    for name, contract in TRACKS.items():
        tracks[name] = {
            "gate_id": contract["gate_id"],
            "owner_role": contract["owner_role"],
            "owner_appointment_ref": PENDING,
            "test_matrix_ref": PENDING,
            "status": "PREPARED_SOFTWARE_ONLY",
            "execution_status": "NOT_STARTED",
            "hardware_or_external_validation": "UNVERIFIED",
            "planned_test_ids": list(contract["planned_test_ids"]),
            "external_inputs": list(contract["external_inputs"]),
            "stop_conditions": list(stop_conditions[name]),
        }
    return {
        "schema_version": SCHEMA_VERSION,
        "project": PROJECT,
        "package_id": PENDING,
        "source_revision": PENDING,
        "freeze_manifest_sha256": "0" * 64,
        "status": "SOFTWARE_PREPARATION_READY",
        "environment": "ISOLATED_NON_PRODUCTION_ONLY",
        "execution_status": "NOT_STARTED",
        "external_execution_authorized": False,
        "authorization_boundary": dict(LOCKED_AUTHORIZATION),
        "common_controls": {
            "synthetic_data_only": True,
            "raw_patient_data_allowed": False,
            "production_credentials_allowed": False,
            "private_key_material_allowed": False,
            "raw_serial_frames_allowed": False,
            "evidence_class": "SOFTWARE_PREPARATION_ONLY",
            "scope_ref": PENDING,
            "window_ref": PENDING,
            "rollback_ref": PENDING,
            "stop_rule": "Any scope, identity, trust, privacy, integrity, recovery or clinical safety mismatch stops the track without bypass.",
        },
        "tracks": tracks,
        "independent_verification_required": True,
    }


def template_sha256() -> str:
    encoded = json.dumps(template(), sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


if __name__ == "__main__":
    print(json.dumps({"schema_version": SCHEMA_VERSION, "status": template()["status"], "template_sha256": template_sha256()}, indent=2))
