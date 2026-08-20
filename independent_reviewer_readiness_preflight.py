from __future__ import annotations

import hashlib
import json
import re
import subprocess
from copy import deepcopy
from pathlib import Path
from typing import Any

from wave4_independent_review_package import LOCKED_AUTHORIZATION, PENDING, build_local_package, validate_package

SCHEMA_VERSION = "independent-reviewer-readiness-preflight-v1"
PROJECT = "smart-ward-hub"
ZERO_HASH = "0" * 64
SHA256_RE = re.compile(r"^[a-f0-9]{64}$")
REVISION_RE = re.compile(r"^[0-9a-f]{40}$")
RAW_ID = re.compile(r"\b(?:HN|AN|MRN|NATIONAL_ID)\s*[-_:]\s*[A-Z0-9-]+\b", re.IGNORECASE)
RAW_CONTACT = re.compile(r"(?:@|\+?\d[\d\s().-]{6,}|\b(?:mr|mrs|ms|นาย|นาง|นางสาว)\b)", re.IGNORECASE)
SECRET_MARKER = re.compile(r"(?:BEGIN (?:RSA|EC|OPENSSH|DSA|PRIVATE) KEY|Bearer\s+\S+|(?:password|secret|token|private_key|seed)\s*[:=]\s*\S+)", re.IGNORECASE)

CHECKS: dict[str, dict[str, str]] = {
    "IRP-01": {"title": "Reviewer appointment and conflict declaration", "owner_role": "independent_reviewer", "required_status": "PENDING_EXTERNAL"},
    "IRP-02": {"title": "Signed scope, intended use and expiry", "owner_role": "external_authority", "required_status": "PENDING_EXTERNAL"},
    "IRP-03": {"title": "Role separation and stop/recovery authority", "owner_role": "external_authority", "required_status": "PENDING_EXTERNAL"},
    "IRP-04": {"title": "Release-freeze source and package hash read-back", "owner_role": "independent_reviewer", "required_status": "SOFTWARE_VERIFIED_PENDING_READBACK"},
    "IRP-05": {"title": "Local artifact SHA-256 read-back", "owner_role": "independent_reviewer", "required_status": "SOFTWARE_VERIFIED_PENDING_READBACK"},
    "IRP-06": {"title": "Redaction and zero-PII review", "owner_role": "privacy_security_reviewer", "required_status": "PENDING_EXTERNAL"},
    "IRP-07": {"title": "Reproducibility commands and negative tests", "owner_role": "independent_reviewer", "required_status": "SOFTWARE_VERIFIED_PENDING_READBACK"},
    "IRP-08": {"title": "GV-10/T-01..T-12 traceability review", "owner_role": "independent_reviewer", "required_status": "PENDING_EXTERNAL"},
    "IRP-09": {"title": "External evidence, custody and trusted time", "owner_role": "evidence_custodian", "required_status": "PENDING_EXTERNAL"},
    "IRP-10": {"title": "Findings, residual risks and remediation owners", "owner_role": "independent_reviewer", "required_status": "PENDING_EXTERNAL"},
    "IRP-11": {"title": "Decision record completeness and independent read-back", "owner_role": "external_authority", "required_status": "PENDING_EXTERNAL"},
    "IRP-12": {"title": "Authorization boundary review", "owner_role": "independent_reviewer", "required_status": "SOFTWARE_LOCKED_EXTERNAL_REVIEW_PENDING"},
}

EXTERNAL_INPUTS = (
    "independent reviewer appointment and conflict declaration",
    "external authority appointment with decision scope",
    "signed scope/intended-use/expiry/rollback/stop record",
    "independent read-back channel and evidence custody path",
    "real endpoint/IdP/mTLS/ACL evidence where T-01..T-04 apply",
    "external API version and uncertain-commit transcript for T-05/T-07/T-11",
    "external revocation/response-authenticity evidence for T-08/T-09",
    "independent WORM/trusted-timestamp/custody evidence for T-10",
    "named stop authority and recovery approver with incident channel",
    "clinical governance/protocol/consent and human-factors decisions",
    "review findings, residual-risk acceptance or rejection record",
    "signed external decision or explicit closed-no-authorization record",
)


class ReviewerPreflightError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ReviewerPreflightError(message)


def _safe_text(value: Any, field: str) -> None:
    _require(isinstance(value, str) and value.strip(), f"{field} must be non-empty")
    _require(not RAW_ID.search(value), f"{field} must not contain raw identity")
    _require(not RAW_CONTACT.search(value), f"{field} must not contain raw identity/contact")
    _require(not SECRET_MARKER.search(value), f"{field} must not contain secret material")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_preflight(payload: dict[str, Any], *, template_only: bool = False) -> dict[str, Any]:
    _require(isinstance(payload, dict), "preflight must be an object")
    allowed = {"schema_version", "project", "preflight_id", "source_revision", "freeze_manifest_sha256", "local_index_sha256", "status", "submission_status", "reviewer_appointment", "external_decision", "package_state", "wave_e_bundle_state", "independent_review_status", "mapping_count", "artifact_count", "reviewer_checklist", "external_inputs_pending", "authorization_boundary", "software_evidence_only", "independent_verification_required", "redaction", "raw_identity_present"}
    _require(not (set(payload) - allowed), f"unknown preflight fields: {sorted(set(payload) - allowed)}")
    _require(payload.get("schema_version") == SCHEMA_VERSION, "schema_version mismatch")
    _require(payload.get("project") == PROJECT, "project mismatch")
    if template_only:
        _require(payload.get("preflight_id") == PENDING, "template preflight_id must be pending")
        _require(payload.get("source_revision") == PENDING, "template source_revision must be pending")
        _require(payload.get("freeze_manifest_sha256") == ZERO_HASH, "template freeze hash must be blank")
        _require(payload.get("local_index_sha256") == ZERO_HASH, "template index hash must be blank")
    else:
        _require(isinstance(payload.get("preflight_id"), str) and payload["preflight_id"].startswith("reviewer-preflight-"), "preflight_id must be reviewer-preflight scoped")
        _require(REVISION_RE.fullmatch(payload.get("source_revision", "")) is not None, "source_revision must be git SHA-1")
        _require(SHA256_RE.fullmatch(payload.get("freeze_manifest_sha256", "")) is not None, "freeze hash must be lowercase SHA-256")
        _require(SHA256_RE.fullmatch(payload.get("local_index_sha256", "")) is not None, "local index hash must be lowercase SHA-256")
    _require(payload.get("status") == "REVIEWER_PRECHECK_READY_FOR_EXTERNAL_APPOINTMENT", "status must remain reviewer precheck ready")
    _require(payload.get("submission_status") == "NOT_SUBMITTED", "submission_status must remain NOT_SUBMITTED")
    _require(payload.get("reviewer_appointment") == PENDING, "reviewer appointment must remain pending")
    _require(payload.get("external_decision") == "NOT_ISSUED", "external decision must remain not issued")
    _require(payload.get("package_state") == "READY_FOR_EXTERNAL_OWNER_APPOINTMENT", "package state mismatch")
    _require(payload.get("wave_e_bundle_state") == "NOT_EXECUTED", "Wave E bundle must remain NOT_EXECUTED")
    _require(payload.get("independent_review_status") == "NOT_STARTED", "independent review must remain not started")
    _require(payload.get("mapping_count") == 12, "mapping_count must remain 12")
    _require(payload.get("artifact_count") == 22, "artifact_count must remain 22")
    _require(payload.get("authorization_boundary") == LOCKED_AUTHORIZATION, "authorization boundary must remain locked")
    _require(payload.get("software_evidence_only") is True, "software_evidence_only must be true")
    _require(payload.get("independent_verification_required") is True, "independent verification must remain required")
    _require(payload.get("redaction") == "PASS", "redaction must be PASS")
    _require(payload.get("raw_identity_present") is False, "raw identity boundary must remain false")

    checklist = payload.get("reviewer_checklist")
    _require(isinstance(checklist, list) and len(checklist) == len(CHECKS), "reviewer_checklist must contain exactly 12 checks")
    seen: set[str] = set()
    for entry in checklist:
        _require(isinstance(entry, dict), "reviewer checklist entry must be an object")
        fields = {"check_id", "title", "owner_role", "required_status", "status", "external_action"}
        _require(set(entry) == fields, "reviewer checklist fields mismatch")
        check_id = entry.get("check_id")
        _require(check_id in CHECKS and check_id not in seen, f"reviewer checklist ID invalid or duplicate: {check_id}")
        seen.add(check_id)
        spec = CHECKS[check_id]
        _require(entry.get("title") == spec["title"], f"reviewer checklist title mismatch for {check_id}")
        _require(entry.get("owner_role") == spec["owner_role"], f"reviewer checklist owner mismatch for {check_id}")
        _require(entry.get("required_status") == spec["required_status"], f"reviewer checklist required status mismatch for {check_id}")
        _require(entry.get("status") == spec["required_status"], f"reviewer checklist status mismatch for {check_id}")
        _safe_text(entry.get("external_action"), f"reviewer_checklist.{check_id}.external_action")
    _require(seen == set(CHECKS), "reviewer checklist must cover IRP-01..IRP-12")

    pending = payload.get("external_inputs_pending")
    _require(isinstance(pending, list) and pending == list(EXTERNAL_INPUTS), "external_inputs_pending must remain the authoritative external-input list")
    for index, item in enumerate(pending):
        _safe_text(item, f"external_inputs_pending[{index}]")
    return {"valid": True, "status": payload["status"], "submission_status": payload["submission_status"], "mapping_count": payload["mapping_count"], "artifact_count": payload["artifact_count"], "external_inputs_pending": len(pending), "authorization_boundary": dict(LOCKED_AUTHORIZATION)}


def template() -> dict[str, Any]:
    checklist = []
    for check_id, spec in CHECKS.items():
        checklist.append({"check_id": check_id, "title": spec["title"], "owner_role": spec["owner_role"], "required_status": spec["required_status"], "status": spec["required_status"], "external_action": "Independent reviewer or named external owner must perform this check and record a signed/read-back result; local preflight cannot complete it."})
    return {"schema_version": SCHEMA_VERSION, "project": PROJECT, "preflight_id": PENDING, "source_revision": PENDING, "freeze_manifest_sha256": ZERO_HASH, "local_index_sha256": ZERO_HASH, "status": "REVIEWER_PRECHECK_READY_FOR_EXTERNAL_APPOINTMENT", "submission_status": "NOT_SUBMITTED", "reviewer_appointment": PENDING, "external_decision": "NOT_ISSUED", "package_state": "READY_FOR_EXTERNAL_OWNER_APPOINTMENT", "wave_e_bundle_state": "NOT_EXECUTED", "independent_review_status": "NOT_STARTED", "mapping_count": 12, "artifact_count": 22, "reviewer_checklist": checklist, "external_inputs_pending": list(EXTERNAL_INPUTS), "authorization_boundary": deepcopy(LOCKED_AUTHORIZATION), "software_evidence_only": True, "independent_verification_required": True, "redaction": "PASS", "raw_identity_present": False}


def build_preflight(root: Path) -> dict[str, Any]:
    index_path = root / "evals/micro_rag/evidence/wave4-independent-review-package-local-index-20260821.json"
    freeze_path = root / "evals/micro_rag/evidence/release-candidate-freeze-20260820.json"
    _require(index_path.is_file(), "Wave 4 local index is missing")
    _require(freeze_path.is_file(), "release freeze manifest is missing")
    local_package = json.loads(index_path.read_text(encoding="utf-8"))
    validated = validate_package(local_package)
    _require(validated["mapping_count"] == 12, "local mapping does not cover 12 tests")
    _require(validated["artifact_count"] == 22, "local index does not cover 22 artifacts")
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    _require(local_package["source_revision"] == revision, "local index source revision is stale")
    package = template()
    package["preflight_id"] = f"reviewer-preflight-{revision[:12]}"
    package["source_revision"] = revision
    package["freeze_manifest_sha256"] = _sha256(freeze_path)
    package["local_index_sha256"] = _sha256(index_path)
    validate_preflight(package)
    return package


def template_sha256() -> str:
    return hashlib.sha256(json.dumps(template(), sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
