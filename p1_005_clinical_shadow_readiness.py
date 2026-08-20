from __future__ import annotations

import hashlib
import json
import re
from typing import Any

SCHEMA_VERSION = "p1-005-clinical-shadow-readiness-v1"
PROJECT = "smart-ward-hub"
PENDING = "PENDING_EXTERNAL_APPOINTMENT"
OPAQUE_REF = re.compile(r"^(?:opaque|org|approval|evidence|artifact|scope|window|incident|rollback|commit|freeze|protocol|review|retention|training|fallback):[A-Za-z0-9._-]+$")
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
    "SM-001": ("governance activation gate", "named owners and governance approval are required", "clinical governance approval and owner appointment"),
    "SM-002": ("non-diagnostic signal vocabulary", "only approved shadow signal labels are accepted", "clinical wording and human-factors review"),
    "SM-003": ("Zero-PII input boundary", "tested opaque-token and marker boundary is enforced", "upstream/export/log/backup privacy review"),
    "SM-004": ("review classification workflow", "reviewer, reason and ordered timestamps are required", "independent event adjudication process"),
    "SM-005": ("non-accuracy metric semantics", "coverage and denominators accompany workflow/data-quality rates", "approved analysis plan and complete review dataset"),
    "SM-006": ("stop/resume safety control", "incident stop blocks intake until separate approval", "clinical escalation and manual fallback drill"),
    "SM-007": ("change and notification boundary", "workflow-changing notifications and threshold changes require separate approval", "signed change-control and rollback record"),
}


class ClinicalShadowReadinessError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ClinicalShadowReadinessError(message)


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


def validate_shadow_manifest(payload: dict[str, Any], *, template_only: bool = False) -> dict[str, Any]:
    _require(isinstance(payload, dict), "manifest must be an object")
    allowed = {"schema_version", "project", "status", "shadow_execution", "clinical_governance", "clinical_validation", "real_world_authorization", "software_evidence_only", "external_owner_appointment", "authorization_boundary", "notification_mode", "evidence_class", "zero_pii_claim", "metrics_claim", "tracks", "common_controls", "independent_verification_required"}
    unknown = sorted(set(payload) - allowed)
    _require(not unknown, f"unknown fields: {unknown}")
    _require(payload.get("schema_version") == SCHEMA_VERSION, "schema_version mismatch")
    _require(payload.get("project") == PROJECT, "project mismatch")
    _require(payload.get("status") == "SHADOW_MODE_SOFTWARE_PREPARATION_READY", "status must remain software preparation ready")
    _require(payload.get("shadow_execution") == "NOT_STARTED", "shadow execution must remain NOT_STARTED")
    _require(payload.get("clinical_governance") == "PENDING", "clinical governance must remain PENDING")
    _require(payload.get("clinical_validation") == "PENDING", "clinical validation must remain PENDING")
    _require(payload.get("real_world_authorization") is False, "real_world_authorization must remain false")
    _require(payload.get("software_evidence_only") is True, "software_evidence_only must be true")
    _require(payload.get("external_owner_appointment") == PENDING, "external owner appointment must remain pending")
    _require(payload.get("authorization_boundary") == LOCKED_AUTHORIZATION, "authorization boundary must remain locked")
    _require(payload.get("notification_mode") == "DISABLED", "notification mode must remain disabled")
    _require(payload.get("evidence_class") == "SOFTWARE_SHADOW_MODE_NOT_CLINICAL_ACCURACY", "evidence class mismatch")
    _require(payload.get("zero_pii_claim") == "TESTED_INPUT_MARKER_BOUNDARY_NOT_SYSTEMWIDE_PRIVACY_PROOF", "Zero-PII claim boundary mismatch")
    _require(payload.get("metrics_claim") == "NON_ACCURACY_WORKFLOW_DATA_QUALITY_ONLY", "metrics claim boundary mismatch")
    _require(payload.get("independent_verification_required") is True, "independent_verification_required must be true")

    common = payload.get("common_controls")
    _require(isinstance(common, dict), "common_controls must be an object")
    _require(common.get("max_context_length") == 512, "max context length mismatch")
    _require(common.get("approved_signal_types") == ["suspected fall", "vital anomaly signal", "device/perimeter warning"], "approved signal types mismatch")
    _require(common.get("review_classifications") == ["TRUE_POSITIVE", "FALSE_POSITIVE", "MISSED_EVENT", "INDETERMINATE", "DEVICE_DATA_FAULT"], "review classifications mismatch")
    _require(common.get("review_coverage_required") is True, "review coverage must be required")
    _require(common.get("denominator_explicit") is True, "denominator must be explicit")
    _require(common.get("accuracy_claim_forbidden") is True, "accuracy claim must remain forbidden")
    _require(common.get("manual_fallback") == "EXTERNAL_PENDING", "manual fallback must remain external pending")
    _require(common.get("retention_decision") == "EXTERNAL_PENDING", "retention decision must remain external pending")
    _safe_text(common.get("stop_rule"), "common_controls.stop_rule")
    for field in ("protocol_ref", "scope_ref", "window_ref", "rollback_ref", "training_ref", "review_plan_ref"):
        _opaque(common.get(field), f"common_controls.{field}", pending=template_only)

    tracks = payload.get("tracks")
    _require(isinstance(tracks, dict) and set(tracks) == set(TRACKS), "tracks must contain exactly SM-001 through SM-007")
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
    return {"valid": True, "status": payload["status"], "shadow_execution": payload["shadow_execution"], "real_world_authorization": payload["real_world_authorization"], "software_evidence_only": payload["software_evidence_only"]}


def template() -> dict[str, Any]:
    stop_conditions = {
        "SM-001": "Stop if any named owner, governance approval or accountable escalation contact is missing.",
        "SM-002": "Stop if a signal is phrased as diagnosis, treatment, medication order or clinical certainty.",
        "SM-003": "Stop on raw identity marker, secret/contact leakage or unreviewed upstream/export/log/backup boundary.",
        "SM-004": "Stop if reviewer, reason, classification or event/received/review time ordering is incomplete.",
        "SM-005": "Stop if review coverage, unreviewed count or denominator semantics are absent or accuracy is inferred.",
        "SM-006": "Stop on privacy, identity, duplicate pairing, sequence, recovery, alert flood, serious missed event or operator misuse incident.",
        "SM-007": "Stop if notification, threshold, risk-weight, deduplication or policy change bypasses approval and rollback control.",
    }
    tracks = {}
    for track_id, (title, required_state, evidence_required) in TRACKS.items():
        tracks[track_id] = {"title": title, "required_state": required_state, "evidence_required": evidence_required, "status": "SOFTWARE_PASS_EXTERNAL_PENDING", "external_required": True, "evidence_ref": PENDING, "stop_condition": stop_conditions[track_id]}
    return {
        "schema_version": SCHEMA_VERSION,
        "project": PROJECT,
        "status": "SHADOW_MODE_SOFTWARE_PREPARATION_READY",
        "shadow_execution": "NOT_STARTED",
        "clinical_governance": "PENDING",
        "clinical_validation": "PENDING",
        "real_world_authorization": False,
        "software_evidence_only": True,
        "external_owner_appointment": PENDING,
        "authorization_boundary": dict(LOCKED_AUTHORIZATION),
        "notification_mode": "DISABLED",
        "evidence_class": "SOFTWARE_SHADOW_MODE_NOT_CLINICAL_ACCURACY",
        "zero_pii_claim": "TESTED_INPUT_MARKER_BOUNDARY_NOT_SYSTEMWIDE_PRIVACY_PROOF",
        "metrics_claim": "NON_ACCURACY_WORKFLOW_DATA_QUALITY_ONLY",
        "common_controls": {"max_context_length": 512, "approved_signal_types": ["suspected fall", "vital anomaly signal", "device/perimeter warning"], "review_classifications": ["TRUE_POSITIVE", "FALSE_POSITIVE", "MISSED_EVENT", "INDETERMINATE", "DEVICE_DATA_FAULT"], "review_coverage_required": True, "denominator_explicit": True, "accuracy_claim_forbidden": True, "manual_fallback": "EXTERNAL_PENDING", "retention_decision": "EXTERNAL_PENDING", "protocol_ref": PENDING, "scope_ref": PENDING, "window_ref": PENDING, "rollback_ref": PENDING, "training_ref": PENDING, "review_plan_ref": PENDING, "stop_rule": "Stop shadow intake on privacy leakage, identity mismatch, duplicate pairing, sequence corruption, recovery failure, alert flood, serious missed event, premature purge or operator interpretation as treatment instruction."},
        "tracks": tracks,
        "independent_verification_required": True,
    }


def template_sha256() -> str:
    return hashlib.sha256(json.dumps(template(), sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


if __name__ == "__main__":
    print(json.dumps({"schema_version": SCHEMA_VERSION, "status": template()["status"], "template_sha256": template_sha256()}, indent=2))
