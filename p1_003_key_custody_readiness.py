from __future__ import annotations

import hashlib
import json
import re
from typing import Any

SCHEMA_VERSION = "p1-003-key-custody-readiness-v1"
PROJECT = "smart-ward-hub"
PENDING = "PENDING_EXTERNAL_APPOINTMENT"
OPAQUE_REF = re.compile(r"^(?:opaque|org|approval|evidence|artifact|scope|window|incident|rollback|commit|freeze|custody|key|device):[A-Za-z0-9._-]+$")
SECRET_MARKER = re.compile(r"(?:BEGIN (?:RSA|EC|OPENSSH|DSA|PRIVATE) KEY|Bearer\s+\S+|(?:password|secret|token|private_key|seed)\s*[:=]\s*\S+)", re.IGNORECASE)
RAW_CONTACT = re.compile(r"(?:@|\+?\d[\d\s().-]{6,}|\b(?:mr|mrs|ms|นาย|นาง|นางสาว)\b)", re.IGNORECASE)
HEX64 = re.compile(r"^[a-f0-9]{64}$")

LOCKED_AUTHORIZATION = {
    "external_authority": "NONE",
    "clinical_validation_authorized": False,
    "production_authorized": False,
    "runtime_authority": "NONE",
    "pilot_gate_status": "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION",
}

TRACKS = {
    "KT-001": {
        "title": "stable device/key identity and Ed25519 contract",
        "required_state": "unique_device_key_identity_ed25519_only",
        "evidence_required": "device_provenance_and_algorithm_policy",
    },
    "KT-002": {
        "title": "private-key material boundary",
        "required_state": "public_fingerprint_only_private_material_never_entered",
        "evidence_required": "secret_scan_and_custody_boundary_record",
    },
    "KT-003": {
        "title": "dual-control activation",
        "required_state": "two_distinct_approver_refs_required",
        "evidence_required": "dual_control_ceremony_record",
    },
    "KT-004": {
        "title": "manufacturer attestation",
        "required_state": "ca_secure_element_non_exportable_flags_captured",
        "evidence_required": "manufacturer_ca_and_hardware_attestation_transcript",
    },
    "KT-005": {
        "title": "linked key rotation",
        "required_state": "new_key_links_previous_and_old_key_suspends",
        "evidence_required": "rotation_rollout_and_rollback_record",
    },
    "KT-006": {
        "title": "revocation and lost-device handling",
        "required_state": "revoked_lost_terminal_with_reason_and_incident",
        "evidence_required": "revocation_distribution_and_lost_device_drill",
    },
    "KT-007": {
        "title": "custody evidence and independent verification",
        "required_state": "snapshot_excludes_private_material_and_has_chain_reference",
        "evidence_required": "protected_audit_retention_and_independent_readback",
    },
}


class KeyCustodyReadinessError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise KeyCustodyReadinessError(message)


def _opaque(value: Any, field: str, *, pending: bool = False) -> None:
    _require(isinstance(value, str) and value.strip(), f"{field} must be non-empty")
    if pending and value == PENDING:
        return
    _require(OPAQUE_REF.fullmatch(value) is not None, f"{field} must be an opaque reference")
    _require(RAW_CONTACT.search(value) is None, f"{field} must not contain raw identity/contact")
    _require(SECRET_MARKER.search(value) is None, f"{field} must not contain secret material")


def _safe_text(value: Any, field: str) -> None:
    _require(isinstance(value, str) and value.strip(), f"{field} must be non-empty")
    _require(RAW_CONTACT.search(value) is None, f"{field} must not contain raw identity/contact")
    _require(SECRET_MARKER.search(value) is None, f"{field} must not contain secret material")


def validate_key_custody_manifest(payload: dict[str, Any], *, template_only: bool = False) -> dict[str, Any]:
    _require(isinstance(payload, dict), "manifest must be an object")
    allowed = {
        "schema_version", "project", "package_id", "source_revision", "freeze_manifest_sha256", "status",
        "key_custody_execution", "hardware_custody_validation", "clinical_validation", "software_evidence_only",
        "external_owner_appointment", "authorization_boundary", "software_fixture_mode", "no_private_key_material",
        "tracks", "common_controls", "independent_verification_required",
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
        _require(isinstance(payload.get("freeze_manifest_sha256"), str) and HEX64.fullmatch(payload["freeze_manifest_sha256"]) is not None, "freeze_manifest_sha256 must be lowercase SHA-256")

    _require(payload.get("status") == "KEY_CUSTODY_SOFTWARE_PREPARATION_READY", "status must remain software preparation ready")
    _require(payload.get("key_custody_execution") == "NOT_STARTED", "key custody execution must remain NOT_STARTED")
    _require(payload.get("hardware_custody_validation") == "UNVERIFIED", "hardware custody validation must remain UNVERIFIED")
    _require(payload.get("clinical_validation") == "PENDING", "clinical validation must remain PENDING")
    _require(payload.get("software_evidence_only") is True, "software_evidence_only must be true")
    _require(payload.get("external_owner_appointment") == PENDING, "external owner appointment must remain pending")
    _require(payload.get("authorization_boundary") == LOCKED_AUTHORIZATION, "authorization boundary must remain locked")
    _require(payload.get("software_fixture_mode") == "ALLOW_FOR_TESTS_ONLY_UNVERIFIED", "software fixture mode must remain explicitly unverified")
    _require(payload.get("no_private_key_material") is True, "no_private_key_material must be true")
    _require(payload.get("independent_verification_required") is True, "independent_verification_required must be true")

    common = payload.get("common_controls")
    _require(isinstance(common, dict), "common_controls must be an object")
    _require(common.get("algorithm") == "Ed25519", "algorithm must remain Ed25519")
    _require(common.get("private_key_storage") == "EXTERNAL_CUSTODY_ONLY", "private_key_storage must remain external custody only")
    _require(common.get("registry_material") == "PUBLIC_KEY_FINGERPRINT_AND_LIFECYCLE_METADATA_ONLY", "registry material boundary mismatch")
    _require(common.get("evidence_class") == "SOFTWARE_PREPARATION_ONLY", "evidence class mismatch")
    _require(common.get("production_credentials_present") is False, "production credentials must not be present")
    _safe_text(common.get("stop_rule"), "common_controls.stop_rule")
    for key in ("scope_ref", "window_ref", "rollback_ref", "custody_ref"):
        _opaque(common.get(key), f"common_controls.{key}", pending=template_only)

    tracks = payload.get("tracks")
    _require(isinstance(tracks, dict) and set(tracks) == set(TRACKS), "tracks must contain exactly KT-001 through KT-007")
    for track_id, contract in TRACKS.items():
        track = tracks[track_id]
        _require(isinstance(track, dict), f"tracks.{track_id} must be an object")
        _require(track.get("title") == contract["title"], f"tracks.{track_id}.title mismatch")
        _require(track.get("required_state") == contract["required_state"], f"tracks.{track_id}.required_state mismatch")
        _require(track.get("evidence_required") == contract["evidence_required"], f"tracks.{track_id}.evidence_required mismatch")
        _require(track.get("status") == "SOFTWARE_PASS_EXTERNAL_PENDING", f"tracks.{track_id}.status mismatch")
        _require(track.get("external_required") is True, f"tracks.{track_id}.external_required must be true")
        if template_only:
            _require(track.get("evidence_ref") == PENDING, f"template tracks.{track_id}.evidence_ref must remain pending")
        else:
            _opaque(track.get("evidence_ref"), f"tracks.{track_id}.evidence_ref")
        _safe_text(track.get("stop_condition"), f"tracks.{track_id}.stop_condition")

    return {
        "valid": True,
        "status": payload["status"],
        "key_custody_execution": payload["key_custody_execution"],
        "hardware_custody_validation": payload["hardware_custody_validation"],
        "software_fixture_mode": payload["software_fixture_mode"],
        "software_evidence_only": payload["software_evidence_only"],
    }


def template() -> dict[str, Any]:
    tracks: dict[str, Any] = {}
    stop_conditions = {
        "KT-001": "Stop if device/key identity is duplicated, algorithm is not Ed25519 or manufacturer provenance is absent.",
        "KT-002": "Stop if private key, seed, factory secret or production credential enters source, database, log or evidence.",
        "KT-003": "Stop if activation lacks two distinct approver references or separation of duties is not evidenced.",
        "KT-004": "Stop if manufacturer CA, secure element or non-exportability is only asserted by local code.",
        "KT-005": "Stop if rotation lacks previous-key linkage, rollback or old-key suspension evidence.",
        "KT-006": "Stop if revocation/lost state lacks reason, incident reference or independent distribution evidence.",
        "KT-007": "Stop if evidence has no custody reference, retention decision or independent read-back.",
    }
    for track_id, contract in TRACKS.items():
        tracks[track_id] = {
            "title": contract["title"],
            "required_state": contract["required_state"],
            "evidence_required": contract["evidence_required"],
            "status": "SOFTWARE_PASS_EXTERNAL_PENDING",
            "external_required": True,
            "evidence_ref": PENDING,
            "stop_condition": stop_conditions[track_id],
        }
    return {
        "schema_version": SCHEMA_VERSION,
        "project": PROJECT,
        "package_id": PENDING,
        "source_revision": PENDING,
        "freeze_manifest_sha256": "0" * 64,
        "status": "KEY_CUSTODY_SOFTWARE_PREPARATION_READY",
        "key_custody_execution": "NOT_STARTED",
        "hardware_custody_validation": "UNVERIFIED",
        "clinical_validation": "PENDING",
        "software_evidence_only": True,
        "external_owner_appointment": PENDING,
        "authorization_boundary": dict(LOCKED_AUTHORIZATION),
        "software_fixture_mode": "ALLOW_FOR_TESTS_ONLY_UNVERIFIED",
        "no_private_key_material": True,
        "common_controls": {
            "algorithm": "Ed25519",
            "private_key_storage": "EXTERNAL_CUSTODY_ONLY",
            "registry_material": "PUBLIC_KEY_FINGERPRINT_AND_LIFECYCLE_METADATA_ONLY",
            "evidence_class": "SOFTWARE_PREPARATION_ONLY",
            "production_credentials_present": False,
            "scope_ref": PENDING,
            "window_ref": PENDING,
            "rollback_ref": PENDING,
            "custody_ref": PENDING,
            "stop_rule": "Stop all custody execution on private-material exposure, failed dual control, unverified hardware assertion, broken rotation/revocation linkage or incomplete independent read-back.",
        },
        "tracks": tracks,
        "independent_verification_required": True,
    }


def template_sha256() -> str:
    encoded = json.dumps(template(), sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


if __name__ == "__main__":
    print(json.dumps({"schema_version": SCHEMA_VERSION, "status": template()["status"], "template_sha256": template_sha256()}, indent=2))
