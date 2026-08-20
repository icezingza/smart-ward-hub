from __future__ import annotations

import hashlib
import json
import re
from typing import Any

SCHEMA_VERSION = "p1-004-external-anchor-readiness-v1"
PROJECT = "smart-ward-hub"
PENDING = "PENDING_EXTERNAL_APPOINTMENT"
OPAQUE_REF = re.compile(r"^(?:opaque|org|approval|evidence|artifact|scope|window|incident|rollback|commit|freeze|anchor|provider|custody):[A-Za-z0-9._-]+$")
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
    "AC-001": ("independent provider identity", "non_local_provider_id_explicitly_bound", "provider_identity_and_service_ownership_record"),
    "AC-002": ("request receipt binding", "package_block_chain_and_receipt_fields_match", "redacted_request_receipt_transcript"),
    "AC-003": ("stable idempotency and replay", "deterministic_key_and_single_receipt_per_request", "duplicate_replay_transcript"),
    "AC-004": ("append-only delete refusal", "provider_record_delete_is_rejected", "retention_immutability_and_delete_refusal_record"),
    "AC-005": ("receipt verification and readback", "provider_verification_required_before_success", "independent_readback_and_receipt_verification"),
    "AC-006": ("failure and retry boundary", "rejected_mutation_outage_and_malformed_receipt_fail_closed", "outage_retry_duplicate_and_recovery_transcript"),
    "AC-007": ("external trust boundary", "trusted_time_retention_access_and_external_custody_are_not_local_claims", "external_worm_trusted_time_retention_and_custody_record"),
}


class ExternalAnchorReadinessError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ExternalAnchorReadinessError(message)


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


def validate_anchor_manifest(payload: dict[str, Any], *, template_only: bool = False) -> dict[str, Any]:
    _require(isinstance(payload, dict), "manifest must be an object")
    allowed = {"schema_version", "project", "package_id", "source_revision", "freeze_manifest_sha256", "status", "anchor_execution", "independent_provider_validation", "clinical_validation", "software_evidence_only", "external_owner_appointment", "authorization_boundary", "software_provider_identity", "local_anchor_claim", "external_worm_verified", "tracks", "common_controls", "independent_verification_required"}
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
    _require(payload.get("status") == "EXTERNAL_ANCHOR_SOFTWARE_PREPARATION_READY", "status must remain software preparation ready")
    _require(payload.get("anchor_execution") == "NOT_STARTED", "anchor execution must remain NOT_STARTED")
    _require(payload.get("independent_provider_validation") == "UNVERIFIED", "independent provider validation must remain UNVERIFIED")
    _require(payload.get("clinical_validation") == "PENDING", "clinical validation must remain PENDING")
    _require(payload.get("software_evidence_only") is True, "software_evidence_only must be true")
    _require(payload.get("external_owner_appointment") == PENDING, "external owner appointment must remain pending")
    _require(payload.get("authorization_boundary") == LOCKED_AUTHORIZATION, "authorization boundary must remain locked")
    _require(payload.get("software_provider_identity") == "software-anchor-stub", "software provider identity mismatch")
    _require(payload.get("local_anchor_claim") == "TAMPER_EVIDENT_WITHIN_EDGE_TRUST_BOUNDARY", "local anchor claim boundary mismatch")
    _require(payload.get("external_worm_verified") is False, "external_worm_verified must remain false")
    _require(payload.get("independent_verification_required") is True, "independent_verification_required must be true")

    common = payload.get("common_controls")
    _require(isinstance(common, dict), "common_controls must be an object")
    _require(common.get("evidence_class") == "EXTERNAL_PROVIDER_RECEIPT_UNVERIFIED", "evidence class mismatch")
    _require(common.get("idempotency_formula") == "sha256(package_id|block_hash|chain_tip)", "idempotency formula mismatch")
    _require(common.get("receipt_verification_required") is True, "receipt verification must be required")
    _require(common.get("delete_refusal_required") is True, "delete refusal must be required")
    _require(common.get("trusted_time") == "EXTERNAL_PENDING", "trusted time must remain external pending")
    _require(common.get("retention_and_access") == "EXTERNAL_PENDING", "retention/access must remain external pending")
    _safe_text(common.get("stop_rule"), "common_controls.stop_rule")
    for field in ("scope_ref", "window_ref", "rollback_ref", "provider_ref"):
        _opaque(common.get(field), f"common_controls.{field}", pending=template_only)

    tracks = payload.get("tracks")
    _require(isinstance(tracks, dict) and set(tracks) == set(TRACKS), "tracks must contain exactly AC-001 through AC-007")
    for track_id, (title, required_state, evidence_required) in TRACKS.items():
        track = tracks[track_id]
        _require(isinstance(track, dict), f"tracks.{track_id} must be an object")
        _require(track.get("title") == title, f"tracks.{track_id}.title mismatch")
        _require(track.get("required_state") == required_state, f"tracks.{track_id}.required_state mismatch")
        _require(track.get("evidence_required") == evidence_required, f"tracks.{track_id}.evidence_required mismatch")
        _require(track.get("status") == "SOFTWARE_PASS_EXTERNAL_PENDING", f"tracks.{track_id}.status mismatch")
        _require(track.get("external_required") is True, f"tracks.{track_id}.external_required must be true")
        if template_only:
            _require(track.get("evidence_ref") == PENDING, f"template tracks.{track_id}.evidence_ref must remain pending")
        else:
            _opaque(track.get("evidence_ref"), f"tracks.{track_id}.evidence_ref")
        _safe_text(track.get("stop_condition"), f"tracks.{track_id}.stop_condition")
    return {"valid": True, "status": payload["status"], "anchor_execution": payload["anchor_execution"], "independent_provider_validation": payload["independent_provider_validation"], "software_evidence_only": payload["software_evidence_only"]}


def template() -> dict[str, Any]:
    stop_conditions = {
        "AC-001": "Stop if provider identity is local/filesystem/none, unowned or mismatched with client identity.",
        "AC-002": "Stop if any request/receipt package, block, chain, provider or status field mismatches.",
        "AC-003": "Stop if idempotency key is unstable, duplicate publish creates a second receipt or replay changes receipt identity.",
        "AC-004": "Stop if a provider record can be deleted or retention immutability is only asserted locally.",
        "AC-005": "Stop if receipt verification/readback is skipped, malformed or performed only inside the same trust boundary.",
        "AC-006": "Stop on provider outage, rejected/mutated receipt, retry ambiguity or unbounded retry behavior.",
        "AC-007": "Stop if local stub evidence is labeled external WORM, trusted-time, tamper-proof or production evidence.",
    }
    tracks = {}
    for track_id, (title, required_state, evidence_required) in TRACKS.items():
        tracks[track_id] = {"title": title, "required_state": required_state, "evidence_required": evidence_required, "status": "SOFTWARE_PASS_EXTERNAL_PENDING", "external_required": True, "evidence_ref": PENDING, "stop_condition": stop_conditions[track_id]}
    return {
        "schema_version": SCHEMA_VERSION,
        "project": PROJECT,
        "package_id": PENDING,
        "source_revision": PENDING,
        "freeze_manifest_sha256": "0" * 64,
        "status": "EXTERNAL_ANCHOR_SOFTWARE_PREPARATION_READY",
        "anchor_execution": "NOT_STARTED",
        "independent_provider_validation": "UNVERIFIED",
        "clinical_validation": "PENDING",
        "software_evidence_only": True,
        "external_owner_appointment": PENDING,
        "authorization_boundary": dict(LOCKED_AUTHORIZATION),
        "software_provider_identity": "software-anchor-stub",
        "local_anchor_claim": "TAMPER_EVIDENT_WITHIN_EDGE_TRUST_BOUNDARY",
        "external_worm_verified": False,
        "common_controls": {"evidence_class": "EXTERNAL_PROVIDER_RECEIPT_UNVERIFIED", "idempotency_formula": "sha256(package_id|block_hash|chain_tip)", "receipt_verification_required": True, "delete_refusal_required": True, "trusted_time": "EXTERNAL_PENDING", "retention_and_access": "EXTERNAL_PENDING", "scope_ref": PENDING, "window_ref": PENDING, "rollback_ref": PENDING, "provider_ref": PENDING, "stop_rule": "Stop on provider identity mismatch, receipt mutation, idempotency/replay failure, delete acceptance, verification/readback failure, unbounded retry or any local-to-external claim escalation."},
        "tracks": tracks,
        "independent_verification_required": True,
    }


def template_sha256() -> str:
    return hashlib.sha256(json.dumps(template(), sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


if __name__ == "__main__":
    print(json.dumps({"schema_version": SCHEMA_VERSION, "status": template()["status"], "template_sha256": template_sha256()}, indent=2))
