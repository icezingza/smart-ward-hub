from __future__ import annotations

import hashlib
import json
import re
from typing import Any

SCHEMA_VERSION = "wave2-integration-forensic-readiness-v1"
PROJECT = "smart-ward-hub"
PENDING = "PENDING_EXTERNAL_APPOINTMENT"
OPAQUE_REF = re.compile(r"^(?:opaque|org|approval|evidence|artifact|scope|window|incident|rollback|commit|freeze|anchor|provider|custody|his|fhir|worm|timestamp|retention|verify):[A-Za-z0-9._-]+$")
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
    "GV-03": {
        "title": "HIS/FHIR integration boundary",
        "software_state": "SOFTWARE_CONTRACT_VERIFIED",
        "external_evidence": (
            "real_his_transcript",
            "fhir_ack_reconciliation",
            "failure_recovery_transcript",
            "hospital_fhir_profile_decision",
        ),
    },
    "GV-07": {
        "title": "External forensic anchor boundary",
        "software_state": "LOCAL_ANCHOR_SOFTWARE_VERIFIED",
        "external_evidence": (
            "external_worm_receipt",
            "trusted_timestamp",
            "retention_legal_hold",
            "cross_boundary_verification",
        ),
    },
}


class Wave2ReadinessError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise Wave2ReadinessError(message)


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


def validate_wave2_manifest(payload: dict[str, Any], *, template_only: bool = False) -> dict[str, Any]:
    _require(isinstance(payload, dict), "manifest must be an object")
    allowed = {
        "schema_version", "project", "source_revision", "freeze_manifest_sha256", "status",
        "execution_status", "external_integration", "clinical_validation", "software_evidence_only",
        "external_owner_appointment", "authorization_boundary", "tracks", "common_controls",
        "required_external_prerequisites", "independent_verification_required",
    }
    unknown = sorted(set(payload) - allowed)
    _require(not unknown, f"unknown fields: {unknown}")
    _require(payload.get("schema_version") == SCHEMA_VERSION, "schema_version mismatch")
    _require(payload.get("project") == PROJECT, "project mismatch")
    if template_only:
        _require(payload.get("source_revision") == PENDING, "template source_revision must remain pending")
        _require(payload.get("freeze_manifest_sha256") == "0" * 64, "template freeze hash must remain blank-safe")
    else:
        _opaque(payload.get("source_revision"), "source_revision")
        _require(isinstance(payload.get("freeze_manifest_sha256"), str) and HEX64.fullmatch(payload["freeze_manifest_sha256"]) is not None, "freeze_manifest_sha256 must be lowercase SHA-256")
    _require(payload.get("status") == "WAVE2_SOFTWARE_PREPARATION_READY", "status must remain software preparation ready")
    _require(payload.get("execution_status") == "NOT_STARTED", "execution_status must remain NOT_STARTED")
    _require(payload.get("external_integration") == "UNVERIFIED", "external_integration must remain UNVERIFIED")
    _require(payload.get("clinical_validation") == "PENDING", "clinical_validation must remain PENDING")
    _require(payload.get("software_evidence_only") is True, "software_evidence_only must be true")
    _require(payload.get("external_owner_appointment") == PENDING, "external owner appointment must remain pending")
    _require(payload.get("authorization_boundary") == LOCKED_AUTHORIZATION, "authorization boundary must remain locked")
    _require(payload.get("independent_verification_required") is True, "independent_verification_required must be true")

    common = payload.get("common_controls")
    _require(isinstance(common, dict), "common_controls must be an object")
    common_allowed = {
        "raw_identity_boundary", "ack_purge_rule", "local_anchor_claim", "external_receipt_required",
        "scope_ref", "window_ref", "rollback_ref", "stop_rule",
    }
    unknown_common = sorted(set(common) - common_allowed)
    _require(not unknown_common, f"unknown common_controls fields: {unknown_common}")
    _require(common.get("raw_identity_boundary") == "RAW_HIS_REFERENCE_GATEWAY_ONLY_OPAQUE_TOKEN_IN_HUB", "raw identity boundary mismatch")
    _require(common.get("ack_purge_rule") == "STRUCTURED_ACK_MATCH_EXACT_SCOPE_ONLY", "ack purge rule mismatch")
    _require(common.get("local_anchor_claim") == "LOCAL_TAMPER_EVIDENT_ONLY_NOT_EXTERNAL_WORM", "local anchor claim mismatch")
    _require(common.get("external_receipt_required") is True, "external receipt requirement must be true")
    _safe_text(common.get("stop_rule"), "common_controls.stop_rule")
    for field in ("scope_ref", "window_ref", "rollback_ref"):
        _opaque(common.get(field), f"common_controls.{field}", pending=template_only)

    tracks = payload.get("tracks")
    _require(isinstance(tracks, dict) and set(tracks) == set(TRACKS), "tracks must contain exactly GV-03 and GV-07")
    for gate, spec in TRACKS.items():
        track = tracks[gate]
        _require(isinstance(track, dict), f"tracks.{gate} must be an object")
        track_allowed = {"gate", "title", "software_state", "external_required", "evidence_refs", "stop_conditions"}
        unknown_track = sorted(set(track) - track_allowed)
        _require(not unknown_track, f"unknown {gate} fields: {unknown_track}")
        _require(track.get("gate") == gate, f"tracks.{gate}.gate mismatch")
        _require(track.get("title") == spec["title"], f"tracks.{gate}.title mismatch")
        _require(track.get("software_state") == spec["software_state"], f"tracks.{gate}.software_state mismatch")
        _require(track.get("external_required") is True, f"tracks.{gate}.external_required must be true")
        refs = track.get("evidence_refs")
        _require(isinstance(refs, dict) and set(refs) == set(spec["external_evidence"]), f"tracks.{gate}.evidence_refs mismatch")
        for ref_name, ref_value in refs.items():
            _opaque(ref_value, f"tracks.{gate}.evidence_refs.{ref_name}", pending=template_only)
        stops = track.get("stop_conditions")
        _require(isinstance(stops, list) and len(stops) >= 3, f"tracks.{gate}.stop_conditions must contain at least 3 rules")
        for index, stop in enumerate(stops):
            _safe_text(stop, f"tracks.{gate}.stop_conditions[{index}]")

    prerequisites = payload.get("required_external_prerequisites")
    _require(isinstance(prerequisites, list) and len(prerequisites) == 8, "required_external_prerequisites must contain exactly 8 entries")
    expected = {item for spec in TRACKS.values() for item in spec["external_evidence"]}
    _require(set(prerequisites) == expected, "required_external_prerequisites mismatch")
    for index, item in enumerate(prerequisites):
        _safe_text(item, f"required_external_prerequisites[{index}]")
    return {
        "valid": True,
        "status": payload["status"],
        "execution_status": payload["execution_status"],
        "external_integration": payload["external_integration"],
        "external_prerequisite_count": len(prerequisites),
    }


def template() -> dict[str, Any]:
    stop_conditions = {
        "GV-03": [
            "Stop if a raw HN/AN/MRN or direct patient identity crosses into Hub-facing payload.",
            "Stop if a structured acknowledgment does not match bundle, receiving system, version and profile.",
            "Stop if transport/authentication failure would purge aggregates or retry without a bounded policy.",
        ],
        "GV-07": [
            "Stop if a local receipt is labeled external WORM, trusted timestamp or tamper-proof evidence.",
            "Stop if an external receipt provider/package/hash/idempotency field mismatches or readback fails.",
            "Stop if retention, custody, trusted time or cross-boundary verification is asserted without external evidence.",
        ],
    }
    tracks: dict[str, Any] = {}
    for gate, spec in TRACKS.items():
        tracks[gate] = {
            "gate": gate,
            "title": spec["title"],
            "software_state": spec["software_state"],
            "external_required": True,
            "evidence_refs": {name: PENDING for name in spec["external_evidence"]},
            "stop_conditions": stop_conditions[gate],
        }
    return {
        "schema_version": SCHEMA_VERSION,
        "project": PROJECT,
        "source_revision": PENDING,
        "freeze_manifest_sha256": "0" * 64,
        "status": "WAVE2_SOFTWARE_PREPARATION_READY",
        "execution_status": "NOT_STARTED",
        "external_integration": "UNVERIFIED",
        "clinical_validation": "PENDING",
        "software_evidence_only": True,
        "external_owner_appointment": PENDING,
        "authorization_boundary": dict(LOCKED_AUTHORIZATION),
        "tracks": tracks,
        "common_controls": {
            "raw_identity_boundary": "RAW_HIS_REFERENCE_GATEWAY_ONLY_OPAQUE_TOKEN_IN_HUB",
            "ack_purge_rule": "STRUCTURED_ACK_MATCH_EXACT_SCOPE_ONLY",
            "local_anchor_claim": "LOCAL_TAMPER_EVIDENT_ONLY_NOT_EXTERNAL_WORM",
            "external_receipt_required": True,
            "scope_ref": PENDING,
            "window_ref": PENDING,
            "rollback_ref": PENDING,
            "stop_rule": "Stop on raw identity crossing, purge without structured matching acknowledgement, local-to-external claim escalation, receipt mutation, unbounded retry or missing independent verification.",
        },
        "required_external_prerequisites": [
            "real_his_transcript",
            "fhir_ack_reconciliation",
            "failure_recovery_transcript",
            "hospital_fhir_profile_decision",
            "external_worm_receipt",
            "trusted_timestamp",
            "retention_legal_hold",
            "cross_boundary_verification",
        ],
        "independent_verification_required": True,
    }


def template_sha256() -> str:
    return hashlib.sha256(json.dumps(template(), sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


if __name__ == "__main__":
    print(json.dumps({"schema_version": SCHEMA_VERSION, "status": template()["status"], "template_sha256": template_sha256()}, indent=2))
