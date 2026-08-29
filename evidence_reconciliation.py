from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

from freeze_integrity_monitor import revision_is_ancestor


SCHEMA_VERSION = "smart-ward-evidence-reconciliation-v1"
FREEZE_REFERENCE = "TOP_LEVEL_RELEASE_FREEZE"
BOUNDARY = {
    "external_authority": "NONE",
    "clinical_validation_authorized": False,
    "production_authorized": False,
    "runtime_authority": "NONE",
    "pilot_gate_status": "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION",
}
EXPECTED_EXTERNAL_GATE_SNAPSHOT = {"blocked": 7, "open": 3, "evidence_submitted": 0, "passed": 0}
EXPECTED_STATES = {
    "wave4_package_state": "READY_FOR_EXTERNAL_OWNER_APPOINTMENT",
    "wave4_bundle_state": "NOT_EXECUTED",
    "wave4_review_status": "NOT_STARTED",
    "reviewer_package_state": "READY_FOR_EXTERNAL_OWNER_APPOINTMENT",
    "reviewer_submission_status": "NOT_SUBMITTED",
    "reviewer_appointment": "PENDING_EXTERNAL_APPOINTMENT",
    "reviewer_external_decision": "NOT_ISSUED",
    "reviewer_wave_e_state": "NOT_EXECUTED",
    "reviewer_review_status": "NOT_STARTED",
    "wave_e_packet_status": "READY_FOR_EXTERNAL_OWNER_APPOINTMENT",
    "wave_e_execution_permitted": False,
    "wave_e_external_validation_started": False,
}


class EvidenceReconciliationError(ValueError):
    pass


@dataclass(frozen=True)
class ReconciliationFinding:
    finding_id: str
    severity: str
    status: str
    message: str
    remediation: str

    def as_dict(self) -> dict[str, str]:
        return {
            "finding_id": self.finding_id,
            "severity": self.severity,
            "status": self.status,
            "message": self.message,
            "remediation": self.remediation,
        }


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EvidenceReconciliationError(f"json_invalid:{path.name}") from exc
    if not isinstance(value, dict):
        raise EvidenceReconciliationError(f"json_object_required:{path.name}")
    return value


def _sha256(path: Path) -> str:
    raw = path.read_bytes()
    if path.suffix.lower() in {".bat", ".cmd", ".csv", ".css", ".example", ".html", ".ini", ".js", ".json", ".mako", ".md", ".ps1", ".py", ".service", ".sh", ".sql", ".svg", ".toml", ".txt", ".xml", ".yaml", ".yml"} or path.name in {".gitattributes", ".gitignore"}:
        raw = raw.replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()


def _assert_boundary(name: str, value: Any) -> None:
    if value != BOUNDARY:
        raise EvidenceReconciliationError(f"{name}:authorization_boundary_mutation_rejected")


def _assert_exact_state(name: str, value: Any, expected: Any) -> None:
    if value != expected:
        raise EvidenceReconciliationError(f"{name}:unexpected_state:{value!r}")


def _assert_source_revision(name: str, value: Any) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 128:
        raise EvidenceReconciliationError(f"{name}:source_revision_invalid")
    return value


def _freeze_artifact_map(freeze: dict[str, Any], root: Path) -> dict[str, str]:
    if freeze.get("schema_version") != "smart-ward-hub-release-freeze-v1":
        raise EvidenceReconciliationError("freeze_schema_invalid")
    if freeze.get("freeze_status") != "PASS":
        raise EvidenceReconciliationError("freeze_not_pass")
    if freeze.get("manifest_self_hash_excluded") is not True:
        raise EvidenceReconciliationError("freeze_self_hash_contract_invalid")
    _assert_boundary("freeze", freeze.get("authorization_boundary"))
    if freeze.get("claim_boundary", {}).get("forbidden_from_local_freeze") != [
        "clinical-ready",
        "production-ready",
        "tamper-proof",
        "HIPAA/PDPA compliant 100%",
    ]:
        raise EvidenceReconciliationError("freeze_claim_boundary_invalid")
    files = freeze.get("files")
    if not isinstance(files, list) or not files:
        raise EvidenceReconciliationError("freeze_files_invalid")
    artifact_map: dict[str, str] = {}
    for item in files:
        if not isinstance(item, dict) or set(item) != {"classification", "path", "sha256", "size_bytes"}:
            raise EvidenceReconciliationError("freeze_artifact_record_invalid")
        relative = item["path"]
        expected_hash = item["sha256"]
        if not isinstance(relative, str) or Path(relative).is_absolute() or ".." in Path(relative).parts:
            raise EvidenceReconciliationError("freeze_artifact_path_invalid")
        if not isinstance(expected_hash, str) or len(expected_hash) != 64 or any(char not in "0123456789abcdef" for char in expected_hash):
            raise EvidenceReconciliationError("freeze_artifact_hash_invalid")
        artifact = root / relative
        if not artifact.is_file():
            raise EvidenceReconciliationError(f"freeze_artifact_missing:{relative}")
        if _sha256(artifact) != expected_hash:
            raise EvidenceReconciliationError(f"freeze_artifact_hash_mismatch:{relative}")
        artifact_map[relative] = expected_hash
    return artifact_map


def _verify_snapshot_hashes(freeze: dict[str, Any], root: Path, snapshot_paths: dict[str, Path]) -> None:
    expected = {item["path"]: item["sha256"] for item in freeze.get("files", []) if isinstance(item, dict) and "path" in item and "sha256" in item}
    for name, path in snapshot_paths.items():
        relative = path.relative_to(root).as_posix()
        if relative not in expected:
            raise EvidenceReconciliationError(f"{name}:not_bound_to_release_freeze")
        if _sha256(path) != expected[relative]:
            raise EvidenceReconciliationError(f"{name}:release_freeze_hash_mismatch")


def _reviewer_summary(payload: dict[str, Any]) -> dict[str, Any]:
    _assert_boundary("reviewer", payload.get("authorization_boundary"))
    return {
        "source_revision": _assert_source_revision("reviewer", payload.get("source_revision")),
        "package_state": payload.get("package_state"),
        "submission_status": payload.get("submission_status"),
        "reviewer_appointment": payload.get("reviewer_appointment"),
        "external_decision": payload.get("external_decision"),
        "wave_e_bundle_state": payload.get("wave_e_bundle_state"),
        "independent_review_status": payload.get("independent_review_status"),
        "mapping_count": payload.get("mapping_count"),
        "artifact_count": payload.get("artifact_count"),
        "software_evidence_only": payload.get("software_evidence_only"),
        "redaction": payload.get("redaction"),
        "raw_identity_present": payload.get("raw_identity_present"),
    }


def _wave4_summary(payload: dict[str, Any]) -> dict[str, Any]:
    _assert_boundary("wave4", payload.get("authorization_boundary"))
    return {
        "source_revision": _assert_source_revision("wave4", payload.get("source_revision")),
        "package_state": payload.get("package_state"),
        "wave_e_bundle_state": payload.get("wave_e_bundle_state"),
        "independent_review_status": payload.get("independent_review_status"),
        "external_owner_appointment": payload.get("external_owner_appointment"),
        "mapping_count": len(payload.get("mapping", [])) if isinstance(payload.get("mapping"), list) else None,
        "artifact_count": len(payload.get("artifacts", [])) if isinstance(payload.get("artifacts"), list) else None,
        "freeze_manifest_sha256": payload.get("freeze_manifest_sha256"),
        "evidence_class": payload.get("evidence_class"),
        "redaction": payload.get("redaction"),
        "raw_identity_present": payload.get("raw_identity_present"),
    }


def _wave_e_summary(payload: dict[str, Any]) -> dict[str, Any]:
    preflight = payload.get("preflight")
    if not isinstance(preflight, dict):
        raise EvidenceReconciliationError("wave_e:preflight_missing")
    _assert_boundary("wave_e", preflight.get("authorization_snapshot"))
    _assert_exact_state("wave_e.packet_status", payload.get("packet_status"), EXPECTED_STATES["wave_e_packet_status"])
    _assert_exact_state("wave_e.preflight.execution_permitted", preflight.get("execution_permitted"), False)
    _assert_exact_state("wave_e.preflight.external_validation_started", preflight.get("external_validation_started"), False)
    missing = preflight.get("missing_criteria")
    if missing != [f"E-{index:02d}" for index in range(1, 11)]:
        raise EvidenceReconciliationError("wave_e:entry_criteria_drift")
    return {
        "source_revision": _assert_source_revision("wave_e", preflight.get("source_revision")),
        "packet_status": payload.get("packet_status"),
        "execution_permitted": preflight.get("execution_permitted"),
        "external_validation_started": preflight.get("external_validation_started"),
        "missing_criteria": missing,
        "package_hash": payload.get("package_hash"),
    }


def _wave0_summary(payload: dict[str, Any]) -> dict[str, Any]:
    boundary = payload.get("authorization_boundary")
    _assert_boundary("wave0", boundary)
    _assert_exact_state("wave0.status", payload.get("status"), "OWNER_APPOINTMENT_TEMPLATE")
    _assert_exact_state("wave0.external_execution_authorized", payload.get("external_execution_authorized"), False)
    _assert_exact_state("wave0.production_authorized", payload.get("production_authorized"), False)
    _assert_exact_state("wave0.clinical_validation_authorized", payload.get("clinical_validation_authorized"), False)
    return {
        "schema_version": payload.get("schema_version"),
        "status": payload.get("status"),
        "package_id": payload.get("package_id"),
        "source_revision": payload.get("source_revision"),
        "external_execution_authorized": payload.get("external_execution_authorized"),
        "production_authorized": payload.get("production_authorized"),
        "clinical_validation_authorized": payload.get("clinical_validation_authorized"),
    }


def reconcile_packages(
    *,
    root: Path,
    freeze_path: Path,
    wave4_path: Path,
    reviewer_path: Path,
    wave_e_path: Path,
    wave0_template_path: Path,
    lineage_root: Path | None = None,
) -> dict[str, Any]:
    root = root.expanduser().resolve()
    lineage_root = (lineage_root or root).expanduser().resolve()
    freeze_path = freeze_path.expanduser().resolve()
    wave4_path = wave4_path.expanduser().resolve()
    reviewer_path = reviewer_path.expanduser().resolve()
    wave_e_path = wave_e_path.expanduser().resolve()
    wave0_template_path = wave0_template_path.expanduser().resolve()
    for path in (freeze_path, wave4_path, reviewer_path, wave_e_path, wave0_template_path):
        if not path.is_relative_to(root):
            raise EvidenceReconciliationError("path_outside_repository")
        if not path.is_file():
            raise EvidenceReconciliationError(f"required_artifact_missing:{path.name}")

    freeze = _load_json(freeze_path)
    _freeze_artifact_map(freeze, root)
    snapshot_paths = {
        "wave4": wave4_path,
        "reviewer": reviewer_path,
        "wave_e": wave_e_path,
        "wave0": wave0_template_path,
    }
    _verify_snapshot_hashes(freeze, root, snapshot_paths)
    wave4 = _load_json(wave4_path)
    reviewer = _load_json(reviewer_path)
    wave_e = _load_json(wave_e_path)
    wave0 = _load_json(wave0_template_path)
    wave4_summary = _wave4_summary(wave4)
    reviewer_summary = _reviewer_summary(reviewer)
    wave_e_summary = _wave_e_summary(wave_e)
    wave0_summary = _wave0_summary(wave0)
    _assert_exact_state("wave4.freeze_manifest_sha256", wave4.get("freeze_manifest_sha256"), FREEZE_REFERENCE)
    _assert_exact_state("reviewer.freeze_manifest_sha256", reviewer.get("freeze_manifest_sha256"), FREEZE_REFERENCE)

    freeze_source = _assert_source_revision("freeze", freeze.get("source_revision"))
    source_revisions = {
        "freeze": freeze_source,
        "wave4": wave4_summary["source_revision"],
        "reviewer": reviewer_summary["source_revision"],
        "wave_e": wave_e_summary["source_revision"],
        "wave0": wave0_summary["source_revision"],
    }
    findings: list[ReconciliationFinding] = []
    source_revision_lineage: dict[str, dict[str, Any]] = {}
    for name, revision in source_revisions.items():
        if name == "freeze":
            source_revision_lineage[name] = {
                "revision": revision,
                "relation": "FREEZE_SOURCE",
                "ancestor_verified": True,
            }
            continue
        if revision == freeze_source:
            source_revision_lineage[name] = {
                "revision": revision,
                "relation": "MATCH",
                "ancestor_verified": True,
            }
            continue
        ancestor_verified = revision_is_ancestor(lineage_root, revision, freeze_source)
        relation = "ANCESTOR_REQUIRES_REGENERATION" if ancestor_verified else "NON_ANCESTOR_BLOCKED"
        source_revision_lineage[name] = {
            "revision": revision,
            "relation": relation,
            "ancestor_verified": ancestor_verified,
        }
        findings.append(
            ReconciliationFinding(
                finding_id=f"SOURCE_NONIDENTICAL_{name.upper()}",
                severity="MEDIUM" if ancestor_verified else "HIGH",
                status="ANCESTOR_VERIFIED_REQUIRES_REGENERATION" if ancestor_verified else "NON_ANCESTOR_SOURCE_BLOCKED",
                message=(
                    f"{name} source revision is an ancestor of the top-level freeze source but is not byte-identical."
                    if ancestor_verified
                    else f"{name} source revision is not a verified ancestor of the top-level freeze source."
                ),
                remediation=(
                    "Regenerate the package snapshot after the approved freeze source revision before external submission."
                    if ancestor_verified
                    else "Replace the package snapshot with one derived from an approved source revision and rerun reconciliation before external submission."
                ),
            )
        )
    if wave4_summary["mapping_count"] != 12 or wave4_summary["artifact_count"] != 22:
        findings.append(
            ReconciliationFinding(
                finding_id="WAVE4_COUNT_DRIFT",
                severity="HIGH",
                status="BLOCKED",
                message="Wave 4 mapping/artifact counts do not match the expected local package contract.",
                remediation="Rebuild the Wave 4 local index and rerun its phase-end gate.",
            )
        )
    if reviewer_summary["mapping_count"] != 12 or reviewer_summary["artifact_count"] != 22:
        findings.append(
            ReconciliationFinding(
                finding_id="REVIEWER_COUNT_DRIFT",
                severity="HIGH",
                status="BLOCKED",
                message="Reviewer preflight mapping/artifact counts do not match the expected local package contract.",
                remediation="Regenerate the reviewer preflight snapshot from the approved source revision.",
            )
        )
    if wave4_summary["evidence_class"] != "SOFTWARE_COORDINATION_ONLY" or wave4_summary["redaction"] != "PASS" or wave4_summary["raw_identity_present"] is not False:
        raise EvidenceReconciliationError("wave4:claim_or_redaction_boundary_invalid")
    if reviewer_summary["software_evidence_only"] is not True or reviewer_summary["redaction"] != "PASS" or reviewer_summary["raw_identity_present"] is not False:
        raise EvidenceReconciliationError("reviewer:claim_or_redaction_boundary_invalid")

    external_gate_snapshot = freeze.get("external_gate_snapshot")
    if external_gate_snapshot != EXPECTED_EXTERNAL_GATE_SNAPSHOT:
        raise EvidenceReconciliationError("external_gate_snapshot_mutation_rejected")
    expected_state_values = {
        "wave4_package_state": wave4_summary["package_state"],
        "wave4_bundle_state": wave4_summary["wave_e_bundle_state"],
        "wave4_review_status": wave4_summary["independent_review_status"],
        "reviewer_package_state": reviewer_summary["package_state"],
        "reviewer_submission_status": reviewer_summary["submission_status"],
        "reviewer_appointment": reviewer_summary["reviewer_appointment"],
        "reviewer_external_decision": reviewer_summary["external_decision"],
        "reviewer_wave_e_state": reviewer_summary["wave_e_bundle_state"],
        "reviewer_review_status": reviewer_summary["independent_review_status"],
        "wave_e_packet_status": wave_e_summary["packet_status"],
        "wave_e_execution_permitted": wave_e_summary["execution_permitted"],
        "wave_e_external_validation_started": wave_e_summary["external_validation_started"],
    }
    for key, expected in EXPECTED_STATES.items():
        if expected_state_values[key] != expected:
            raise EvidenceReconciliationError(f"state_drift:{key}")

    return {
        "schema_version": SCHEMA_VERSION,
        "reconciliation_id": "evidence-reconciliation-20260821",
        "created_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "reconciliation_status": "RECONCILED_WITH_EXTERNAL_BLOCKERS" if findings else "RECONCILED_OWNER_APPOINTMENT_READY",
        "gate_decision": "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION",
        "evidence_class": "SOFTWARE_COORDINATION_ONLY",
        "source_revisions": source_revisions,
        "source_revision_lineage": source_revision_lineage,
        "source_revision_alignment": "ANCESTOR_VERIFIED_REQUIRES_REGENERATION" if any(
            item["relation"] == "ANCESTOR_REQUIRES_REGENERATION" for item in source_revision_lineage.values()
        ) else ("NON_ANCESTOR_BLOCKED" if findings else "MATCH"),
        "package_checks": {
            "release_freeze": "PASS",
            "wave4": "PASS",
            "reviewer_preflight": "PASS",
            "wave_e_preflight": "PASS",
            "wave0_template": "PASS",
        },
        "findings": [finding.as_dict() for finding in findings],
        "external_gate_snapshot": external_gate_snapshot,
        "states": expected_state_values,
        "authorization_boundary": dict(BOUNDARY),
        "external_inputs_pending": list(reviewer.get("external_inputs_pending", [])),
        "software_evidence_only": True,
        "independent_verification_required": True,
        "claim_boundary": "EXTERNAL_UNVERIFIED_PENDING_OWNER_APPOINTMENT",
        "execution_permitted": False,
        "submission_permitted": False,
    }


def default_paths(root: Path) -> dict[str, Path]:
    evidence = root / "evals" / "micro_rag" / "evidence"
    return {
        "root": root,
        "freeze_path": evidence / "release-candidate-freeze-20260820.json",
        "wave4_path": evidence / "wave4-independent-review-package-local-index-20260821.json",
        "reviewer_path": evidence / "independent-reviewer-readiness-preflight-local-20260821.json",
        "wave_e_path": evidence / "wave-e-execution-preflight-local-20260821.json",
        "wave0_template_path": evidence / "wave0-owner-appointment-intake-template-20260820.json",
    }


__all__ = [
    "BOUNDARY",
    "EvidenceReconciliationError",
    "SCHEMA_VERSION",
    "default_paths",
    "reconcile_packages",
]
