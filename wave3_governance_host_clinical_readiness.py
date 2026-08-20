from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from typing import Any

SCHEMA_VERSION = "wave3-governance-host-clinical-readiness-v1"
PROJECT = "smart-ward-hub"
PENDING = "PENDING_EXTERNAL_APPOINTMENT"
OPAQUE_REF = re.compile(r"^(?:opaque|org|approval|evidence|artifact|scope|window|incident|rollback|commit|freeze|host|privacy|training|clinical|protocol|risk|retention|review|site):[A-Za-z0-9._-]+$")
SECRET_MARKER = re.compile(r"(?:BEGIN (?:RSA|EC|OPENSSH|DSA|PRIVATE) KEY|Bearer\s+\S+|(?:password|secret|token|private_key|seed)\s*[:=]\s*\S+)", re.IGNORECASE)
RAW_ID = re.compile(r"\b(?:HN|AN|MRN|NATIONAL_ID)\s*[-_:]\s*[A-Z0-9-]+\b", re.IGNORECASE)
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
    "GV-02": {
        "title": "Privacy and security review",
        "software_state": "SOFTWARE_PRIVACY_BOUNDARY_VERIFIED",
        "external_evidence": ("zero_pii_dataflow_review", "retention_rbac_decision", "screen_site_privacy_review", "incident_residual_risk_register"),
    },
    "GV-05": {
        "title": "Acer host hardening",
        "software_state": "HOST_SOFTWARE_PREPARATION_VERIFIED",
        "external_evidence": ("windows_identity_acl_transcript", "encryption_firewall_patch_record", "power_recovery_transcript", "privacy_kiosk_monitoring_record"),
    },
    "GV-09": {
        "title": "Clinical operations",
        "software_state": "CLINICAL_OPERATIONS_SOFTWARE_CONTRACT_VERIFIED",
        "external_evidence": ("staff_competency_record", "manual_fallback_sop_signoff", "alarm_escalation_fatigue_review", "downtime_walkthrough_stop_drill"),
    },
    "GV-01": {
        "title": "Clinical governance",
        "software_state": "CLINICAL_PREFLIGHT_CONTRACT_VERIFIED",
        "external_evidence": ("approved_clinical_protocol", "consent_waiver_decision", "safety_hazard_human_factors_review", "committee_decision_record"),
    },
}


class Wave3ReadinessError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise Wave3ReadinessError(message)


def _opaque(value: Any, field: str, *, pending: bool = False) -> None:
    _require(isinstance(value, str) and value.strip(), f"{field} must be non-empty")
    if pending and value == PENDING:
        return
    _require(OPAQUE_REF.fullmatch(value) is not None, f"{field} must be an opaque reference")
    _require(not RAW_ID.search(value), f"{field} must not contain raw identity")
    _require(not RAW_CONTACT.search(value), f"{field} must not contain raw identity/contact")
    _require(not SECRET_MARKER.search(value), f"{field} must not contain secret material")


def _safe_text(value: Any, field: str) -> None:
    _require(isinstance(value, str) and value.strip(), f"{field} must be non-empty")
    _require(not RAW_ID.search(value), f"{field} must not contain raw identity")
    _require(not RAW_CONTACT.search(value), f"{field} must not contain raw identity/contact")
    _require(not SECRET_MARKER.search(value), f"{field} must not contain secret material")


def validate_wave3_manifest(payload: dict[str, Any], *, template_only: bool = False) -> dict[str, Any]:
    _require(isinstance(payload, dict), "manifest must be an object")
    allowed = {"schema_version", "project", "source_revision", "freeze_manifest_sha256", "status", "execution_status", "clinical_governance", "host_validation", "privacy_review", "clinical_operations", "clinical_validation", "software_evidence_only", "external_owner_appointment", "authorization_boundary", "tracks", "common_controls", "required_external_prerequisites", "independent_verification_required"}
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
    _require(payload.get("status") == "WAVE3_SOFTWARE_PREPARATION_READY", "status must remain software preparation ready")
    _require(payload.get("execution_status") == "NOT_STARTED", "execution_status must remain NOT_STARTED")
    _require(payload.get("clinical_governance") == "PENDING", "clinical governance must remain PENDING")
    _require(payload.get("host_validation") == "UNVERIFIED", "host validation must remain UNVERIFIED")
    _require(payload.get("privacy_review") == "UNVERIFIED", "privacy review must remain UNVERIFIED")
    _require(payload.get("clinical_operations") == "NOT_STARTED", "clinical operations must remain NOT_STARTED")
    _require(payload.get("clinical_validation") == "PENDING", "clinical validation must remain PENDING")
    _require(payload.get("software_evidence_only") is True, "software_evidence_only must be true")
    _require(payload.get("external_owner_appointment") == PENDING, "external owner appointment must remain pending")
    _require(payload.get("authorization_boundary") == LOCKED_AUTHORIZATION, "authorization boundary must remain locked")
    _require(payload.get("independent_verification_required") is True, "independent_verification_required must be true")

    common = payload.get("common_controls")
    _require(isinstance(common, dict), "common_controls must be an object")
    common_allowed = {"zero_pii_claim", "host_claim", "clinical_claim", "change_control", "scope_ref", "window_ref", "rollback_ref", "stop_rule"}
    _require(not (set(common) - common_allowed), f"unknown common_controls fields: {sorted(set(common) - common_allowed)}")
    _require(common.get("zero_pii_claim") == "TESTED_MARKER_AND_FLOW_BOUNDARY_NOT_SYSTEMWIDE_PRIVACY_PROOF", "zero_pii claim boundary mismatch")
    _require(common.get("host_claim") == "SOFTWARE_CONFIGURATION_PREPARED_HOST_UNVERIFIED", "host claim boundary mismatch")
    _require(common.get("clinical_claim") == "WORKFLOW_AND_PREFLIGHT_CONTRACT_ONLY_NOT_CLINICAL_AUTHORIZATION", "clinical claim boundary mismatch")
    _require(common.get("change_control") == "EXTERNAL_APPROVAL_AND_ROLLBACK_REQUIRED", "change-control boundary mismatch")
    _safe_text(common.get("stop_rule"), "common_controls.stop_rule")
    for field in ("scope_ref", "window_ref", "rollback_ref"):
        _opaque(common.get(field), f"common_controls.{field}", pending=template_only)

    tracks = payload.get("tracks")
    _require(isinstance(tracks, dict) and set(tracks) == set(TRACKS), "tracks must contain exactly GV-02, GV-05, GV-09 and GV-01")
    for gate, spec in TRACKS.items():
        track = tracks[gate]
        _require(isinstance(track, dict), f"tracks.{gate} must be an object")
        allowed_track = {"gate", "title", "software_state", "external_required", "evidence_refs", "stop_conditions"}
        _require(not (set(track) - allowed_track), f"unknown {gate} fields: {sorted(set(track) - allowed_track)}")
        _require(track.get("gate") == gate, f"tracks.{gate}.gate mismatch")
        _require(track.get("title") == spec["title"], f"tracks.{gate}.title mismatch")
        _require(track.get("software_state") == spec["software_state"], f"tracks.{gate}.software_state mismatch")
        _require(track.get("external_required") is True, f"tracks.{gate}.external_required must be true")
        refs = track.get("evidence_refs")
        _require(isinstance(refs, dict) and set(refs) == set(spec["external_evidence"]), f"tracks.{gate}.evidence_refs mismatch")
        for name, value in refs.items():
            _opaque(value, f"tracks.{gate}.evidence_refs.{name}", pending=template_only)
        stops = track.get("stop_conditions")
        _require(isinstance(stops, list) and len(stops) >= 3, f"tracks.{gate}.stop_conditions must contain at least 3 rules")
        for index, stop in enumerate(stops):
            _safe_text(stop, f"tracks.{gate}.stop_conditions[{index}]")

    prerequisites = payload.get("required_external_prerequisites")
    expected = {item for spec in TRACKS.values() for item in spec["external_evidence"]}
    _require(isinstance(prerequisites, list) and set(prerequisites) == expected and len(prerequisites) == len(expected), "required_external_prerequisites mismatch")
    for index, item in enumerate(prerequisites):
        _safe_text(item, f"required_external_prerequisites[{index}]")
    return {"valid": True, "status": payload["status"], "execution_status": payload["execution_status"], "clinical_governance": payload["clinical_governance"], "host_validation": payload["host_validation"], "privacy_review": payload["privacy_review"], "clinical_operations": payload["clinical_operations"], "prerequisite_count": len(prerequisites)}


def template() -> dict[str, Any]:
    stop_conditions = {
        "GV-02": ["Stop on raw identity, contact or secret leakage in flow, export, log or backup.", "Stop if retention, RBAC, screen privacy or incident owner is unreviewed.", "Stop if local redaction output is used to claim systemwide privacy compliance."],
        "GV-05": ["Stop on source-tree runtime path, exposed docs, non-loopback bind or embedded credentials.", "Stop if encryption, ACL, firewall, patch, time or restore evidence is missing.", "Stop if rollback version, power behavior, kiosk privacy or monitoring owner is unknown."],
        "GV-09": ["Stop if an untrained operator enters workflow or manual fallback is unsigned.", "Stop on alert flood, missing escalation roster, unreviewed alarm fatigue or failed downtime drill.", "Stop if clinical stop authority or outside-in/walk-round workflow is not approved."],
        "GV-01": ["Stop if intended use, excluded use or safety thresholds are ambiguous.", "Stop if protocol, consent/waiver, human-factors or adverse-event plan is not approved.", "Stop if local preflight is used to claim clinical-ready, accuracy or authorization."],
    }
    tracks = {}
    for gate, spec in TRACKS.items():
        tracks[gate] = {"gate": gate, "title": spec["title"], "software_state": spec["software_state"], "external_required": True, "evidence_refs": {name: PENDING for name in spec["external_evidence"]}, "stop_conditions": stop_conditions[gate]}
    return {"schema_version": SCHEMA_VERSION, "project": PROJECT, "source_revision": PENDING, "freeze_manifest_sha256": "0" * 64, "status": "WAVE3_SOFTWARE_PREPARATION_READY", "execution_status": "NOT_STARTED", "clinical_governance": "PENDING", "host_validation": "UNVERIFIED", "privacy_review": "UNVERIFIED", "clinical_operations": "NOT_STARTED", "clinical_validation": "PENDING", "software_evidence_only": True, "external_owner_appointment": PENDING, "authorization_boundary": deepcopy(LOCKED_AUTHORIZATION), "tracks": tracks, "common_controls": {"zero_pii_claim": "TESTED_MARKER_AND_FLOW_BOUNDARY_NOT_SYSTEMWIDE_PRIVACY_PROOF", "host_claim": "SOFTWARE_CONFIGURATION_PREPARED_HOST_UNVERIFIED", "clinical_claim": "WORKFLOW_AND_PREFLIGHT_CONTRACT_ONLY_NOT_CLINICAL_AUTHORIZATION", "change_control": "EXTERNAL_APPROVAL_AND_ROLLBACK_REQUIRED", "scope_ref": PENDING, "window_ref": PENDING, "rollback_ref": PENDING, "stop_rule": "Stop on raw identity/secret leakage, unsafe host exposure, missing restore or rollback, untrained clinical operation, absent manual fallback, unapproved clinical change or local-to-external claim escalation."}, "required_external_prerequisites": [item for spec in TRACKS.values() for item in spec["external_evidence"]], "independent_verification_required": True}


def template_sha256() -> str:
    return hashlib.sha256(json.dumps(template(), sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


if __name__ == "__main__":
    print(json.dumps({"schema_version": SCHEMA_VERSION, "status": template()["status"], "template_sha256": template_sha256()}, indent=2))
