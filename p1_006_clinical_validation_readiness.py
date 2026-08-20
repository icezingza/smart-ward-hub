from __future__ import annotations

import hashlib
import json
import re
from typing import Any

SCHEMA_VERSION = "p1-006-clinical-validation-readiness-v1"
PROJECT = "smart-ward-hub"
PENDING = "PENDING_EXTERNAL_APPOINTMENT"
OPAQUE_REF = re.compile(r"^(?:opaque|org|approval|evidence|artifact|scope|window|incident|rollback|commit|freeze|protocol|review|retention|training|fallback|analysis|consent|device|transport|his):[A-Za-z0-9._-]+$")
RAW_CONTACT = re.compile(r"(?:@|\+?\d[\d\s().-]{6,}|\b(?:mr|mrs|ms|นาย|นาง|นางสาว)\b)", re.IGNORECASE)
SECRET_MARKER = re.compile(r"(?:BEGIN (?:RSA|EC|OPENSSH|DSA|PRIVATE) KEY|Bearer\s+\S+|(?:password|secret|token|private_key|seed)\s*[:=]\s*\S+)", re.IGNORECASE)
LOCKED_AUTHORIZATION = {
    "external_authority": "NONE",
    "clinical_validation_authorized": False,
    "production_authorized": False,
    "runtime_authority": "NONE",
    "pilot_gate_status": "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION",
}
TRACKS = {
    "CV-001": ("intended use and excluded use", "decision-support scope and excluded clinical actions are explicit", "approved protocol and population/scope decision"),
    "CV-002": ("owners and governance", "clinical/technical owners, governance and escalation roles are assigned", "named accountable owners and signed governance approval"),
    "CV-003": ("privacy, consent and retention", "privacy/security review, consent or waiver and retention decision are required", "approved privacy/consent/retention evidence"),
    "CV-004": ("operational safety and fallback", "stop, incident, rollback, manual fallback and escalation paths are required", "approved safety protocol and fallback drill"),
    "CV-005": ("backup and recovery", "backup/restore evidence is a prerequisite and not inferred from code tests", "approved recovery/DR evidence"),
    "CV-006": ("device and host qualification", "device, clock, host and recovery qualification remain external", "qualified device/host evidence"),
    "CV-007": ("identity, transport and HIS", "auth/mTLS/IdP and HIS acknowledgment are required before real evaluation", "real transport/HIS integration evidence"),
    "CV-008": ("training and human factors", "staff walkthrough, wording, alarm-fatigue and no-treatment-order interpretation are required", "training and human-factors review"),
    "CV-009": ("independent review and analysis", "independent review plan and non-accuracy analysis semantics are required", "approved analysis plan and adjudication owner"),
    "CV-010": ("decision and promotion gate", "continue/modify/pause/reject requires governance decision; no automatic treatment promotion", "signed decision gate record"),
}


class ClinicalValidationReadinessManifestError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ClinicalValidationReadinessManifestError(message)


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


def validate_manifest(payload: dict[str, Any], *, template_only: bool = False) -> dict[str, Any]:
    _require(isinstance(payload, dict), "manifest must be an object")
    allowed = {"schema_version", "project", "status", "preflight_status", "execution_status", "clinical_governance", "clinical_validation", "real_world_authorization", "software_evidence_only", "external_owner_appointment", "authorization_boundary", "evidence_class", "clinical_claim_boundary", "clinical_shadow_dependency", "protocol_ref", "scope_ref", "window_ref", "rollback_ref", "consent_ref", "retention_ref", "training_ref", "analysis_ref", "tracks", "hard_stops", "analysis_semantics", "independent_verification_required"}
    unknown = sorted(set(payload) - allowed)
    _require(not unknown, f"unknown fields: {unknown}")
    _require(payload.get("schema_version") == SCHEMA_VERSION, "schema_version mismatch")
    _require(payload.get("project") == PROJECT, "project mismatch")
    _require(payload.get("status") == "CLINICAL_VALIDATION_SOFTWARE_PREFLIGHT_READY", "status must remain software preflight ready")
    _require(payload.get("preflight_status") == "READY_FOR_EXTERNAL_GOVERNANCE_REVIEW", "preflight status must remain external-review only")
    _require(payload.get("execution_status") == "NOT_STARTED", "execution status must remain NOT_STARTED")
    _require(payload.get("clinical_governance") == "PENDING", "clinical governance must remain PENDING")
    _require(payload.get("clinical_validation") == "PENDING", "clinical validation must remain PENDING")
    _require(payload.get("real_world_authorization") is False, "real_world_authorization must remain false")
    _require(payload.get("software_evidence_only") is True, "software_evidence_only must be true")
    _require(payload.get("external_owner_appointment") == PENDING, "external owner appointment must remain pending")
    _require(payload.get("authorization_boundary") == LOCKED_AUTHORIZATION, "authorization boundary must remain locked")
    _require(payload.get("evidence_class") == "SOFTWARE_PREFLIGHT_UNVERIFIED", "evidence class mismatch")
    _require(payload.get("clinical_claim_boundary") == "NO_CLINICAL_VALIDATION_OR_ACCURACY_CLAIM", "clinical claim boundary mismatch")
    _require(payload.get("clinical_shadow_dependency") == "P1_005_SOFTWARE_SHADOW_CONTRACT_EXTERNAL_APPROVAL_PENDING", "P1-005 dependency boundary mismatch")
    _require(payload.get("independent_verification_required") is True, "independent_verification_required must be true")

    analysis = payload.get("analysis_semantics")
    _require(isinstance(analysis, dict), "analysis_semantics must be an object")
    _require(analysis.get("accuracy_claim_forbidden") is True, "accuracy claim must remain forbidden")
    _require(analysis.get("clinical_effectiveness_claim_forbidden") is True, "clinical effectiveness claim must remain forbidden")
    _require(analysis.get("review_coverage_required") is True, "review coverage must be required")
    _require(analysis.get("denominator_explicit") is True, "denominator must be explicit")
    _require(analysis.get("unreviewed_events_visible") is True, "unreviewed events must remain visible")
    _require(analysis.get("synthetic_data_not_clinical_evidence") is True, "synthetic data boundary must remain locked")
    _safe_text(analysis.get("note"), "analysis_semantics.note")

    shadow = payload.get("clinical_shadow_dependency")
    _require(isinstance(shadow, str), "shadow dependency must be a string")
    for field in ("protocol_ref", "scope_ref", "window_ref", "rollback_ref", "consent_ref", "retention_ref", "training_ref", "analysis_ref"):
        _opaque(payload.get(field, PENDING), field, pending=template_only)

    hard_stops = payload.get("hard_stops")
    _require(isinstance(hard_stops, list) and len(hard_stops) == 10, "hard_stops must contain exactly 10 rules")
    for index, rule in enumerate(hard_stops):
        _safe_text(rule, f"hard_stops[{index}]")

    tracks = payload.get("tracks")
    _require(isinstance(tracks, dict) and set(tracks) == set(TRACKS), "tracks must contain exactly CV-001 through CV-010")
    for track_id, (title, required_state, evidence_required) in TRACKS.items():
        track = tracks[track_id]
        _require(isinstance(track, dict), f"tracks.{track_id} must be an object")
        _require(track.get("title") == title, f"tracks.{track_id}.title mismatch")
        _require(track.get("required_state") == required_state, f"tracks.{track_id}.required_state mismatch")
        _require(track.get("evidence_required") == evidence_required, f"tracks.{track_id}.evidence_required mismatch")
        _require(track.get("status") == "SOFTWARE_PREFLIGHT_EXTERNAL_PENDING", f"tracks.{track_id}.status mismatch")
        _require(track.get("external_required") is True, f"tracks.{track_id}.external_required must be true")
        _require(track.get("evidence_ref") == PENDING if template_only else OPAQUE_REF.fullmatch(str(track.get("evidence_ref"))) is not None, f"tracks.{track_id}.evidence_ref boundary mismatch")
        _safe_text(track.get("stop_condition"), f"tracks.{track_id}.stop_condition")
    return {"valid": True, "status": payload["status"], "preflight_status": payload["preflight_status"], "execution_status": payload["execution_status"], "real_world_authorization": payload["real_world_authorization"], "software_evidence_only": payload["software_evidence_only"]}


def template() -> dict[str, Any]:
    stop_conditions = {
        "CV-001": "Stop if intended use, excluded use, population or non-interventional scope is ambiguous.",
        "CV-002": "Stop if accountable clinical, technical, governance or incident roles are not named and separated.",
        "CV-003": "Stop on unresolved privacy leakage, missing consent/waiver, retention ambiguity or unsafe access/export boundary.",
        "CV-004": "Stop if stop, incident, escalation, rollback or manual fallback cannot be executed and evidenced.",
        "CV-005": "Stop if backup/restore and recovery evidence is absent or only inferred from software simulation.",
        "CV-006": "Stop if device, host, clock, network, power-loss or recovery qualification is incomplete.",
        "CV-007": "Stop if real identity transport, mTLS/IdP, HIS acknowledgment or integration evidence is absent.",
        "CV-008": "Stop if staff can interpret a shadow signal as diagnosis/treatment or human-factors review is incomplete.",
        "CV-009": "Stop if independent review, analysis denominator, review coverage or missed-event handling is incomplete.",
        "CV-010": "Stop if any system or local operator attempts automatic promotion to clinical treatment workflow.",
    }
    tracks = {}
    for track_id, (title, required_state, evidence_required) in TRACKS.items():
        tracks[track_id] = {"title": title, "required_state": required_state, "evidence_required": evidence_required, "status": "SOFTWARE_PREFLIGHT_EXTERNAL_PENDING", "external_required": True, "evidence_ref": PENDING, "stop_condition": stop_conditions[track_id]}
    return {
        "schema_version": SCHEMA_VERSION,
        "project": PROJECT,
        "status": "CLINICAL_VALIDATION_SOFTWARE_PREFLIGHT_READY",
        "preflight_status": "READY_FOR_EXTERNAL_GOVERNANCE_REVIEW",
        "execution_status": "NOT_STARTED",
        "clinical_governance": "PENDING",
        "clinical_validation": "PENDING",
        "real_world_authorization": False,
        "software_evidence_only": True,
        "external_owner_appointment": PENDING,
        "authorization_boundary": dict(LOCKED_AUTHORIZATION),
        "evidence_class": "SOFTWARE_PREFLIGHT_UNVERIFIED",
        "clinical_claim_boundary": "NO_CLINICAL_VALIDATION_OR_ACCURACY_CLAIM",
        "clinical_shadow_dependency": "P1_005_SOFTWARE_SHADOW_CONTRACT_EXTERNAL_APPROVAL_PENDING",
        "protocol_ref": PENDING,
        "scope_ref": PENDING,
        "window_ref": PENDING,
        "rollback_ref": PENDING,
        "consent_ref": PENDING,
        "retention_ref": PENDING,
        "training_ref": PENDING,
        "analysis_ref": PENDING,
        "analysis_semantics": {"accuracy_claim_forbidden": True, "clinical_effectiveness_claim_forbidden": True, "review_coverage_required": True, "denominator_explicit": True, "unreviewed_events_visible": True, "synthetic_data_not_clinical_evidence": True, "note": "Software preflight and synthetic/replay evidence do not establish clinical accuracy, effectiveness, safety or patient outcomes."},
        "hard_stops": list(stop_conditions.values()),
        "tracks": tracks,
        "independent_verification_required": True,
    }


def template_sha256() -> str:
    return hashlib.sha256(json.dumps(template(), sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


if __name__ == "__main__":
    print(json.dumps({"schema_version": SCHEMA_VERSION, "status": template()["status"], "template_sha256": template_sha256()}, indent=2))
