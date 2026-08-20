from __future__ import annotations

import hashlib
import json
import re
from typing import Any


SCHEMA_VERSION = "p1-008-independent-review-readiness-v1"
PROJECT = "smart-ward-hub"
PENDING = "PENDING_EXTERNAL_APPOINTMENT"
OPAQUE_REF = re.compile(
    r"^(?:software-test|review|dossier|artifact|scope|window|rollback|export|appointment|decision|evidence):[A-Za-z0-9._-]+$"
)
RAW_ID = re.compile(
    r"\b(?:HN|AN|MRN|NATIONAL_ID)(?:\s*[-_:]\s*[A-Z0-9-]{2,}|\s+\d[A-Z0-9-]{1,})\b",
    re.IGNORECASE,
)
RAW_CONTACT = re.compile(
    r"(?:@|(?<![A-Za-z0-9])\+?\d[\d\s().-]{7,}\d(?![A-Za-z0-9])|\b(?:mr|mrs|ms|นาย|นาง|นางสาว)\b)",
    re.IGNORECASE,
)
SECRET_MARKER = re.compile(
    r"(?:BEGIN (?:RSA|EC|OPENSSH|DSA|PRIVATE) KEY|Bearer\s+\S+|(?:password|secret|token|private_key|seed)\s*[:=]\s*\S+)",
    re.IGNORECASE,
)
LOCKED_AUTHORIZATION = {
    "external_authority": "NONE",
    "clinical_validation_authorized": False,
    "production_authorized": False,
    "runtime_authority": "NONE",
    "pilot_gate_status": "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION",
}
TRACK_DEFINITIONS = {
    "IR-001": ("session_lifecycle", "software-test:independent-review-session-lifecycle"),
    "IR-002": ("evidence_binding", "software-test:independent-review-evidence-binding"),
    "IR-003": ("finding_traceability", "software-test:independent-review-finding-traceability"),
    "IR-004": ("severity_and_outcome", "software-test:independent-review-severity-outcome"),
    "IR-005": ("post_close_mutation_lock", "software-test:independent-review-post-close-lock"),
    "IR-006": ("authorization_boundary", "software-test:independent-review-authorization-boundary"),
    "IR-007": ("pilot_gate", "software-test:independent-review-pilot-gate"),
}


class IndependentReviewReadinessError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise IndependentReviewReadinessError(message)


def _safe_text(value: Any, field: str, *, max_length: int = 512) -> None:
    _require(isinstance(value, str) and value.strip(), f"{field} must be non-empty")
    _require(len(value) <= max_length, f"{field} too large")
    _require(RAW_ID.search(value) is None, f"{field} must not contain raw identity")
    _require(RAW_CONTACT.search(value) is None, f"{field} must not contain raw identity/contact")
    _require(SECRET_MARKER.search(value) is None, f"{field} must not contain secret material")


def _opaque(value: Any, field: str, *, pending: bool = False) -> None:
    _require(isinstance(value, str) and value.strip(), f"{field} must be non-empty")
    if pending and value == PENDING:
        return
    _require(OPAQUE_REF.fullmatch(value) is not None, f"{field} must be an opaque reference")
    _require(RAW_ID.search(value) is None and RAW_CONTACT.search(value) is None, f"{field} must not contain raw identity/contact")
    _require(SECRET_MARKER.search(value) is None, f"{field} must not contain secret material")


def _opaque_list(value: Any, field: str, *, allow_empty: bool = True) -> None:
    _require(isinstance(value, list), f"{field} must be a list")
    if not allow_empty:
        _require(bool(value), f"{field} must not be empty")
    for index, item in enumerate(value):
        _opaque(item, f"{field}[{index}]")


def validate_manifest(payload: dict[str, Any], *, template_only: bool = False) -> dict[str, Any]:
    _require(isinstance(payload, dict), "manifest must be an object")
    allowed = {
        "schema_version",
        "project",
        "status",
        "track_count",
        "software_track_status_counts",
        "external_review_status_counts",
        "review_session_status",
        "external_review_status",
        "external_owner_appointment",
        "real_world_authorization",
        "clinical_validation_authorized",
        "production_authorized",
        "runtime_authority",
        "pilot_gate_status",
        "authorization_boundary",
        "software_evidence_only",
        "independent_verification_required",
        "evidence_class",
        "claim_boundary",
        "tracks",
        "review_session_ref",
        "dossier_ref",
        "findings_export_ref",
        "external_decision_ref",
        "rollback_ref",
        "stop_rule",
    }
    unknown = sorted(set(payload) - allowed)
    _require(not unknown, f"unknown fields: {unknown}")
    _require(payload.get("schema_version") == SCHEMA_VERSION, "schema_version mismatch")
    _require(payload.get("project") == PROJECT, "project mismatch")
    _require(payload.get("status") == "SOFTWARE_REVIEW_READY", "status must remain software review ready")
    _require(payload.get("track_count") == 7, "track_count must remain 7")
    _require(payload.get("software_track_status_counts") == {"SOFTWARE_VERIFIED": 7}, "software track status counts mismatch")
    _require(payload.get("external_review_status_counts") == {"PENDING_EXTERNAL_REVIEW": 7}, "external review status counts mismatch")
    _require(payload.get("review_session_status") == "SOFTWARE_DRY_RUN_VERIFIED", "review session status mismatch")
    _require(payload.get("external_review_status") == "PENDING_EXTERNAL_REVIEW", "external review must remain pending")
    _require(payload.get("external_owner_appointment") == PENDING, "external owner appointment must remain pending")
    _require(payload.get("real_world_authorization") is False, "real_world_authorization must remain false")
    _require(payload.get("clinical_validation_authorized") is False, "clinical_validation_authorized must remain false")
    _require(payload.get("production_authorized") is False, "production_authorized must remain false")
    _require(payload.get("runtime_authority") == "NONE", "runtime_authority must remain NONE")
    _require(payload.get("pilot_gate_status") == "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION", "pilot gate must remain blocked")
    _require(payload.get("authorization_boundary") == LOCKED_AUTHORIZATION, "authorization boundary must remain locked")
    _require(payload.get("software_evidence_only") is True, "software_evidence_only must be true")
    _require(payload.get("independent_verification_required") is True, "independent_verification_required must be true")
    _require(payload.get("evidence_class") == "SOFTWARE_VERIFIED_EXTERNAL_REVIEW_PENDING", "evidence class mismatch")
    _require(
        payload.get("claim_boundary") == "CONTROLLED_PRODUCTION_PROTOTYPE_SOFTWARE_VERIFICATION_ONLY_CLINICAL_VALIDATION_PENDING",
        "claim boundary mismatch",
    )

    _opaque(payload.get("review_session_ref"), "review_session_ref", pending=template_only)
    _opaque(payload.get("dossier_ref"), "dossier_ref", pending=template_only)
    _opaque(payload.get("findings_export_ref"), "findings_export_ref", pending=template_only)
    _opaque(payload.get("external_decision_ref"), "external_decision_ref", pending=True)
    _opaque(payload.get("rollback_ref"), "rollback_ref", pending=template_only)
    _safe_text(payload.get("stop_rule"), "stop_rule", max_length=512)

    tracks = payload.get("tracks")
    _require(isinstance(tracks, dict) and set(tracks) == set(TRACK_DEFINITIONS), "tracks must contain exactly IR-001 through IR-007")
    for track_id, (domain, software_ref) in TRACK_DEFINITIONS.items():
        track = tracks[track_id]
        _require(isinstance(track, dict), f"tracks.{track_id} must be an object")
        expected = {"domain", "software_status", "external_status", "software_evidence_refs", "external_evidence_refs", "stop_condition"}
        _require(set(track) == expected, f"tracks.{track_id} fields mismatch")
        _require(track.get("domain") == domain, f"tracks.{track_id}.domain mismatch")
        _require(track.get("software_status") == "SOFTWARE_VERIFIED", f"tracks.{track_id}.software_status mismatch")
        _require(track.get("external_status") == "PENDING_EXTERNAL_REVIEW", f"tracks.{track_id}.external_status mismatch")
        _require(track.get("software_evidence_refs") == [software_ref], f"tracks.{track_id}.software_evidence_refs mismatch")
        if template_only:
            _require(track.get("external_evidence_refs") == [], f"tracks.{track_id}.external_evidence_refs must remain empty in template")
        else:
            _opaque_list(track.get("external_evidence_refs"), f"tracks.{track_id}.external_evidence_refs")
        _safe_text(track.get("stop_condition"), f"tracks.{track_id}.stop_condition", max_length=512)

    return {
        "valid": True,
        "status": payload["status"],
        "track_count": payload["track_count"],
        "review_session_status": payload["review_session_status"],
        "external_review_status": payload["external_review_status"],
        "pilot_gate_status": payload["pilot_gate_status"],
        "software_evidence_only": payload["software_evidence_only"],
    }


def template() -> dict[str, Any]:
    stop_conditions = {
        "IR-001": "Stop if session identity, timezone-aware lifecycle or OPEN/CLOSED transition validation is missing.",
        "IR-002": "Stop if evidence is duplicate, invalid, unverified or not bound to the accepted registry.",
        "IR-003": "Stop if a finding cannot trace to accepted evidence from the same external gate.",
        "IR-004": "Stop if severity/outcome values are outside the controlled vocabulary or the summary contains raw identity/contact/secret markers.",
        "IR-005": "Stop if any evidence or finding can mutate after the review session is closed.",
        "IR-006": "Stop if clinical, production or real-world authorization can be self-asserted by software.",
        "IR-007": "Stop if the pilot gate is not blocked pending an external authorization decision.",
    }
    tracks = {}
    for track_id, (domain, software_ref) in TRACK_DEFINITIONS.items():
        tracks[track_id] = {
            "domain": domain,
            "software_status": "SOFTWARE_VERIFIED",
            "external_status": "PENDING_EXTERNAL_REVIEW",
            "software_evidence_refs": [software_ref],
            "external_evidence_refs": [],
            "stop_condition": stop_conditions[track_id],
        }
    return {
        "schema_version": SCHEMA_VERSION,
        "project": PROJECT,
        "status": "SOFTWARE_REVIEW_READY",
        "track_count": 7,
        "software_track_status_counts": {"SOFTWARE_VERIFIED": 7},
        "external_review_status_counts": {"PENDING_EXTERNAL_REVIEW": 7},
        "review_session_status": "SOFTWARE_DRY_RUN_VERIFIED",
        "external_review_status": "PENDING_EXTERNAL_REVIEW",
        "external_owner_appointment": PENDING,
        "real_world_authorization": False,
        "clinical_validation_authorized": False,
        "production_authorized": False,
        "runtime_authority": "NONE",
        "pilot_gate_status": "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION",
        "authorization_boundary": dict(LOCKED_AUTHORIZATION),
        "software_evidence_only": True,
        "independent_verification_required": True,
        "evidence_class": "SOFTWARE_VERIFIED_EXTERNAL_REVIEW_PENDING",
        "claim_boundary": "CONTROLLED_PRODUCTION_PROTOTYPE_SOFTWARE_VERIFICATION_ONLY_CLINICAL_VALIDATION_PENDING",
        "tracks": tracks,
        "review_session_ref": PENDING,
        "dossier_ref": PENDING,
        "findings_export_ref": PENDING,
        "external_decision_ref": PENDING,
        "rollback_ref": PENDING,
        "stop_rule": "Do not enable clinical validation, production, real-world runtime or pilot deployment from this software manifest; require external governance and independent review decision first.",
    }


def template_sha256() -> str:
    return hashlib.sha256(json.dumps(template(), sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


if __name__ == "__main__":
    print(json.dumps({"schema_version": SCHEMA_VERSION, "status": template()["status"], "template_sha256": template_sha256()}, indent=2))
