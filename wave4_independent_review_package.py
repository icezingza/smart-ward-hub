from __future__ import annotations

import hashlib
import json
import re
import subprocess
from copy import deepcopy
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "wave4-independent-review-package-v1"
PROJECT = "smart-ward-hub"
PENDING = "PENDING_EXTERNAL_APPOINTMENT"
ZERO_HASH = "0" * 64
TOP_LEVEL_FREEZE_REFERENCE = "TOP_LEVEL_RELEASE_FREEZE"
SHA256_RE = re.compile(r"^[a-f0-9]{64}$")
REVISION_RE = re.compile(r"^[0-9a-f]{40}$")
RAW_ID = re.compile(r"\b(?:HN|AN|MRN|NATIONAL_ID)\s*[-_:]\s*[A-Z0-9-]+\b", re.IGNORECASE)
RAW_CONTACT = re.compile(r"(?:@|\+?\d[\d\s().-]{6,}|\b(?:mr|mrs|ms|นาย|นาง|นางสาว)\b)", re.IGNORECASE)
SECRET_MARKER = re.compile(r"(?:BEGIN (?:RSA|EC|OPENSSH|DSA|PRIVATE) KEY|Bearer\s+\S+|(?:password|secret|token|private_key|seed)\s*[:=]\s*\S+)", re.IGNORECASE)
LOCKED_AUTHORIZATION = {
    "external_authority": "NONE",
    "clinical_validation_authorized": False,
    "production_authorized": False,
    "runtime_authority": "NONE",
    "pilot_gate_status": "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION",
}

TEST_SPECS: dict[str, dict[str, Any]] = {
    "T-01": {"focus": "Approved endpoint identity", "evidence_class": "SOFTWARE_PREPARATION_ONLY", "refs": ("wave1-foundation-report", "wave1-software-preparation")},
    "T-02": {"focus": "OIDC issuer audience and JWKS", "evidence_class": "SOFTWARE_PREPARATION_ONLY", "refs": ("wave1-foundation-report", "wave1-identity-transport-template")},
    "T-03": {"focus": "mTLS lifecycle", "evidence_class": "SOFTWARE_SIMULATION_ONLY", "refs": ("p0-mtls-tests", "wave1-technical-validation")},
    "T-04": {"focus": "ACL and segmentation", "evidence_class": "SOFTWARE_PREPARATION_ONLY", "refs": ("p1-002-host-report", "p1-host-checklist")},
    "T-05": {"focus": "Contract and version negotiation", "evidence_class": "SOFTWARE_VERIFIED_SIMULATION_ONLY", "refs": ("wave-e-contract", "wave-e-tests")},
    "T-06": {"focus": "Freeze scope and governance binding", "evidence_class": "SOFTWARE_COORDINATION_ONLY", "refs": ("wave0-governance-checklist", "wave3-readiness-report", "wave-e-contract")},
    "T-07": {"focus": "Idempotency and uncertain commit", "evidence_class": "SOFTWARE_VERIFIED_SIMULATION_ONLY", "refs": ("external-auth-simulator", "wave-e-contract")},
    "T-08": {"focus": "Expiry and revocation", "evidence_class": "SOFTWARE_PREPARATION_ONLY", "refs": ("p1-003-key-custody-report", "p1-004-anchor-report")},
    "T-09": {"focus": "Response authenticity", "evidence_class": "SOFTWARE_SIMULATION_ONLY", "refs": ("wave2-forensic-report", "external-anchor-runtime")},
    "T-10": {"focus": "Audit and custody", "evidence_class": "SOFTWARE_VERIFIED_LOCAL_ONLY", "refs": ("backup-restore-contract", "p1-001-backup-report", "file-anchor-store")},
    "T-11": {"focus": "Retry and rate limiting", "evidence_class": "SOFTWARE_SIMULATION_ONLY", "refs": ("network-pressure-plan", "external-auth-simulator")},
    "T-12": {"focus": "Stop and recovery", "evidence_class": "SOFTWARE_COORDINATION_ONLY", "refs": ("p1-008-review-report", "wave3-readiness-report", "controlled-pilot-gate")},
}

ARTIFACT_PATHS: dict[str, str] = {
    "wave1-foundation-report": "WAVE_1_TECHNICAL_FOUNDATION_READINESS_REPORT_20260821.md",
    "wave1-software-preparation": "wave1_software_preparation.py",
    "wave1-identity-transport-template": "WAVE_1_IDENTITY_TRANSPORT_CONFIG_TEMPLATE.env.example",
    "p0-mtls-tests": "test_p0_mtls_config.py",
    "wave1-technical-validation": "WAVE_1_TECHNICAL_VALIDATION_PACKAGE_20260820.md",
    "p1-002-host-report": "P1_002_HOST_HARDENING_READINESS_REPORT.md",
    "p1-host-checklist": "P1_HOST_HARDENING_CHECKLIST.md",
    "wave-e-contract": "external_authorization_api_wave_e_evidence.py",
    "wave-e-tests": "test_wave_e_evidence.py",
    "wave0-governance-checklist": "WAVE_0_GOVERNANCE_REVIEW_CHECKLIST.md",
    "wave3-readiness-report": "WAVE_3_GOVERNANCE_HOST_CLINICAL_READINESS_REPORT_20260821.md",
    "external-auth-simulator": "external_authorization_api_simulator.py",
    "p1-003-key-custody-report": "P1_003_KEY_CUSTODY_READINESS_REPORT.md",
    "p1-004-anchor-report": "P1_004_EXTERNAL_ANCHOR_READINESS_REPORT.md",
    "wave2-forensic-report": "WAVE_2_INTEGRATION_FORENSIC_READINESS_REPORT_20260821.md",
    "external-anchor-runtime": "external_anchor.py",
    "backup-restore-contract": "BACKUP_RESTORE_CONTRACT.md",
    "p1-001-backup-report": "P1_001_BACKUP_MANIFEST_HARDENING_REPORT.md",
    "file-anchor-store": "edge_controls.py",
    "network-pressure-plan": "NETWORK_PRESSURE_BACKPRESSURE_PLAN.md",
    "p1-008-review-report": "P1_008_INDEPENDENT_REVIEW_READINESS_REPORT.md",
    "controlled-pilot-gate": "CONTROLLED_PILOT_OPERATIONS_GATE.md",
}


class Wave4PackageError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise Wave4PackageError(message)


def _safe_text(value: Any, field: str) -> None:
    _require(isinstance(value, str) and value.strip(), f"{field} must be non-empty")
    _require(not RAW_ID.search(value), f"{field} must not contain raw identity")
    _require(not RAW_CONTACT.search(value), f"{field} must not contain raw identity/contact")
    _require(not SECRET_MARKER.search(value), f"{field} must not contain secret material")


def _opaque(value: Any, field: str, *, pending: bool = False, allow_numeric: bool = False) -> None:
    _require(isinstance(value, str) and value.strip(), f"{field} must be non-empty")
    if pending and value == PENDING:
        return
    _require(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{2,127}", value) is not None, f"{field} must be opaque")
    _require(not RAW_ID.search(value), f"{field} must not contain raw identity")
    _require(not SECRET_MARKER.search(value), f"{field} must not contain secret material")
    if not allow_numeric:
        _require(not RAW_CONTACT.search(value), f"{field} must not contain raw identity/contact")


def _validate_artifact(artifact: dict[str, Any], expected_ref: str, *, template_only: bool) -> None:
    allowed = {"artifact_ref", "repo_path", "artifact_type", "artifact_sha256", "source_revision", "evidence_class", "prepared_by_role", "redaction", "raw_identity_present", "external_verification_status"}
    _require(set(artifact) == allowed, f"artifact fields mismatch for {expected_ref}")
    _require(artifact.get("artifact_ref") == expected_ref, f"artifact_ref mismatch for {expected_ref}")
    _require(isinstance(artifact.get("repo_path"), str) and not artifact["repo_path"].startswith("/") and ".." not in Path(artifact["repo_path"]).parts, f"artifact repo_path unsafe for {expected_ref}")
    repo_path = artifact.get("repo_path")
    _require(not RAW_ID.search(repo_path), f"artifacts.{expected_ref}.repo_path must not contain raw identity")
    _require(not SECRET_MARKER.search(repo_path), f"artifacts.{expected_ref}.repo_path must not contain secret material")
    _require("@" not in repo_path, f"artifacts.{expected_ref}.repo_path must not contain contact marker")
    _safe_text(artifact.get("artifact_type"), f"artifacts.{expected_ref}.artifact_type")
    if template_only:
        _require(artifact.get("artifact_sha256") == ZERO_HASH, f"template artifact hash must be blank for {expected_ref}")
        _require(artifact.get("source_revision") == PENDING, f"template artifact revision must be pending for {expected_ref}")
    else:
        _require(SHA256_RE.fullmatch(artifact.get("artifact_sha256", "")) is not None, f"artifact hash invalid for {expected_ref}")
        _require(REVISION_RE.fullmatch(artifact.get("source_revision", "")) is not None, f"artifact revision invalid for {expected_ref}")
    _require(artifact.get("evidence_class") == "SOFTWARE_REPOSITORY", f"artifact evidence class mismatch for {expected_ref}")
    _require(artifact.get("prepared_by_role") == "evidence_custodian", f"artifact prepared role mismatch for {expected_ref}")
    _require(artifact.get("redaction") == "PASS", f"artifact redaction mismatch for {expected_ref}")
    _require(artifact.get("raw_identity_present") is False, f"artifact raw identity boundary mismatch for {expected_ref}")
    _require(artifact.get("external_verification_status") == "PENDING_EXTERNAL", f"artifact external status mismatch for {expected_ref}")


def validate_package(payload: dict[str, Any], *, template_only: bool = False) -> dict[str, Any]:
    _require(isinstance(payload, dict), "package must be an object")
    allowed = {"schema_version", "project", "package_id", "source_revision", "freeze_manifest_sha256", "package_state", "evidence_class", "wave_e_bundle_state", "independent_review_status", "external_owner_appointment", "mapping", "artifacts", "review_contract", "authorization_boundary", "independent_verification_required", "redaction", "raw_identity_present"}
    _require(not (set(payload) - allowed), f"unknown package fields: {sorted(set(payload) - allowed)}")
    _require(payload.get("schema_version") == SCHEMA_VERSION, "schema_version mismatch")
    _require(payload.get("project") == PROJECT, "project mismatch")
    _opaque(payload.get("package_id"), "package_id", pending=template_only, allow_numeric=True)
    if template_only:
        _require(payload.get("source_revision") == PENDING, "template source revision must be pending")
        _require(payload.get("freeze_manifest_sha256") == TOP_LEVEL_FREEZE_REFERENCE, "template freeze binding must remain top-level")
    else:
        _require(REVISION_RE.fullmatch(payload.get("source_revision", "")) is not None, "source_revision must be a git SHA-1")
        _require(payload.get("freeze_manifest_sha256") == TOP_LEVEL_FREEZE_REFERENCE, "freeze binding must remain top-level")
    _require(payload.get("package_state") == "READY_FOR_EXTERNAL_OWNER_APPOINTMENT", "package_state must remain owner-appointment ready")
    _require(payload.get("evidence_class") == "SOFTWARE_COORDINATION_ONLY", "package evidence class mismatch")
    _require(payload.get("wave_e_bundle_state") == "NOT_EXECUTED", "Wave E bundle state must remain not executed")
    _require(payload.get("independent_review_status") == "NOT_STARTED", "independent review status must remain not started")
    _require(payload.get("external_owner_appointment") == PENDING, "external owner appointment must remain pending")
    _require(payload.get("review_contract") == "wave-e-evidence-bundle-v1", "review contract mismatch")
    _require(payload.get("authorization_boundary") == LOCKED_AUTHORIZATION, "authorization boundary must remain locked")
    _require(payload.get("independent_verification_required") is True, "independent verification must be required")
    _require(payload.get("redaction") == "PASS", "package redaction must be PASS")
    _require(payload.get("raw_identity_present") is False, "package raw identity boundary must remain false")

    mapping = payload.get("mapping")
    _require(isinstance(mapping, list) and len(mapping) == 12, "mapping must contain exactly 12 entries")
    seen_cases: set[str] = set()
    for index, entry in enumerate(mapping):
        _require(isinstance(entry, dict), f"mapping[{index}] must be an object")
        allowed_entry = {"test_case_id", "focus", "evidence_class", "local_artifact_refs", "external_verification_status", "reviewer_action"}
        _require(set(entry) == allowed_entry, f"mapping[{index}] fields mismatch")
        case_id = entry.get("test_case_id")
        _require(case_id in TEST_SPECS and case_id not in seen_cases, f"mapping test case invalid or duplicate: {case_id}")
        seen_cases.add(case_id)
        spec = TEST_SPECS[case_id]
        _require(entry.get("focus") == spec["focus"], f"mapping focus mismatch for {case_id}")
        _require(entry.get("evidence_class") == spec["evidence_class"], f"mapping evidence class mismatch for {case_id}")
        refs = entry.get("local_artifact_refs")
        _require(isinstance(refs, list) and set(refs) == set(spec["refs"]), f"mapping refs mismatch for {case_id}")
        for ref in refs:
            _opaque(ref, f"mapping.{case_id}.local_artifact_refs", pending=template_only)
        _require(entry.get("external_verification_status") == "PENDING_EXTERNAL", f"mapping external status mismatch for {case_id}")
        _safe_text(entry.get("reviewer_action"), f"mapping.{case_id}.reviewer_action")
    _require(seen_cases == set(TEST_SPECS), "mapping must cover T-01 through T-12 exactly")

    artifacts = payload.get("artifacts")
    _require(isinstance(artifacts, list) and len(artifacts) == len(ARTIFACT_PATHS), "artifacts must cover the complete local artifact index")
    seen_refs: set[str] = set()
    for artifact in artifacts:
        _require(isinstance(artifact, dict), "artifact entry must be an object")
        ref = artifact.get("artifact_ref")
        _require(ref in ARTIFACT_PATHS and ref not in seen_refs, f"artifact ref invalid or duplicate: {ref}")
        seen_refs.add(ref)
        _validate_artifact(artifact, ref, template_only=template_only)
    _require(seen_refs == set(ARTIFACT_PATHS), "artifact index must cover all declared paths exactly")
    return {"valid": True, "package_state": payload["package_state"], "mapping_count": len(mapping), "artifact_count": len(artifacts), "wave_e_bundle_state": payload["wave_e_bundle_state"], "authorization_boundary": dict(LOCKED_AUTHORIZATION)}


def template() -> dict[str, Any]:
    mapping = []
    for case_id, spec in TEST_SPECS.items():
        mapping.append({"test_case_id": case_id, "focus": spec["focus"], "evidence_class": spec["evidence_class"], "local_artifact_refs": list(spec["refs"]), "external_verification_status": "PENDING_EXTERNAL", "reviewer_action": "Independent reviewer must verify hash, source revision, scope, expiry, role separation and external evidence before any decision."})
    artifacts = []
    for ref, path in ARTIFACT_PATHS.items():
        artifacts.append({"artifact_ref": ref, "repo_path": path, "artifact_type": Path(path).suffix.lstrip(".") or "file", "artifact_sha256": ZERO_HASH, "source_revision": PENDING, "evidence_class": "SOFTWARE_REPOSITORY", "prepared_by_role": "evidence_custodian", "redaction": "PASS", "raw_identity_present": False, "external_verification_status": "PENDING_EXTERNAL"})
    return {"schema_version": SCHEMA_VERSION, "project": PROJECT, "package_id": PENDING, "source_revision": PENDING, "freeze_manifest_sha256": TOP_LEVEL_FREEZE_REFERENCE, "package_state": "READY_FOR_EXTERNAL_OWNER_APPOINTMENT", "evidence_class": "SOFTWARE_COORDINATION_ONLY", "wave_e_bundle_state": "NOT_EXECUTED", "independent_review_status": "NOT_STARTED", "external_owner_appointment": PENDING, "mapping": mapping, "artifacts": artifacts, "review_contract": "wave-e-evidence-bundle-v1", "authorization_boundary": deepcopy(LOCKED_AUTHORIZATION), "independent_verification_required": True, "redaction": "PASS", "raw_identity_present": False}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_local_package(root: Path) -> dict[str, Any]:
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    freeze_path = root / "evals/micro_rag/evidence/release-candidate-freeze-20260820.json"
    package = template()
    package["package_id"] = f"wave4-index-{revision[:12]}"
    package["source_revision"] = revision
    package["freeze_manifest_sha256"] = TOP_LEVEL_FREEZE_REFERENCE
    for artifact in package["artifacts"]:
        path = root / artifact["repo_path"]
        _require(path.is_file(), f"missing local artifact: {artifact['repo_path']}")
        artifact["artifact_sha256"] = _sha256(path)
        artifact["source_revision"] = revision
    validate_package(package)
    return package


def template_sha256() -> str:
    return hashlib.sha256(json.dumps(template(), sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
