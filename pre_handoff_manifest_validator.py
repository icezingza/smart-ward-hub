"""Read-only validator for the internal pre-handoff evidence snapshot."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import json
from pathlib import Path
import subprocess
from typing import Any, Mapping

from canonical_file_hash import canonical_sha256
from consolidated_internal_handoff_index import LOCKED_BOUNDARY, LOCKED_EXTERNAL_GATE_SNAPSHOT
from pre_handoff_readiness import check_pre_handoff


ROOT = Path(__file__).resolve().parent
SNAPSHOT_RELATIVE = Path("evals/micro_rag/evidence/pre-handoff-readiness-local.json")
FREEZE_RELATIVE = Path("evals/micro_rag/evidence/release-candidate-freeze-20260820.json")


class ManifestDecision(StrEnum):
    VALID = "MANIFEST_VALID"
    INVALID = "MANIFEST_INVALID"


class ManifestCode(StrEnum):
    SNAPSHOT_MISSING = "SNAPSHOT_MISSING"
    SNAPSHOT_HASH_MISMATCH = "SNAPSHOT_HASH_MISMATCH"
    SNAPSHOT_NOT_IN_FREEZE = "SNAPSHOT_NOT_IN_FREEZE"
    SNAPSHOT_SOURCE_REVISION_MISMATCH = "SNAPSHOT_SOURCE_REVISION_MISMATCH"
    SNAPSHOT_ORIGIN_REVISION_MISMATCH = "SNAPSHOT_ORIGIN_REVISION_MISMATCH"
    SNAPSHOT_DECISION_MISMATCH = "SNAPSHOT_DECISION_MISMATCH"
    SNAPSHOT_CHECKS_MISMATCH = "SNAPSHOT_CHECKS_MISMATCH"
    SNAPSHOT_CLAIM_BOUNDARY_MUTATED = "SNAPSHOT_CLAIM_BOUNDARY_MUTATED"
    SNAPSHOT_AUTHORIZATION_MUTATED = "SNAPSHOT_AUTHORIZATION_MUTATED"
    SNAPSHOT_GATE_BOUNDARY_MUTATED = "SNAPSHOT_GATE_BOUNDARY_MUTATED"
    SNAPSHOT_EXTERNAL_SUBMISSION_ENABLED = "SNAPSHOT_EXTERNAL_SUBMISSION_ENABLED"
    SNAPSHOT_RUNTIME_MUTATION = "SNAPSHOT_RUNTIME_MUTATION"
    SNAPSHOT_EXTERNAL_TRANSMISSION = "SNAPSHOT_EXTERNAL_TRANSMISSION"
    FRESH_READINESS_BLOCKED = "FRESH_READINESS_BLOCKED"
    FRESH_READINESS_MISMATCH = "FRESH_READINESS_MISMATCH"
    FREEZE_NOT_PASS = "FREEZE_NOT_PASS"


@dataclass(frozen=True, slots=True)
class ManifestValidationResult:
    decision: str
    remediation_codes: tuple[str, ...]
    checks: dict[str, bool]
    snapshot: dict[str, Any]
    fresh_readiness: dict[str, Any]
    freeze: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "remediation_codes": list(self.remediation_codes),
            "checks": dict(self.checks),
            "snapshot": dict(self.snapshot),
            "fresh_readiness": dict(self.fresh_readiness),
            "freeze": dict(self.freeze),
        }


def _sha256(path: Path) -> str:
    return canonical_sha256(path)


def _load(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _freeze_file(freeze: Mapping[str, Any], relative: str) -> Mapping[str, Any] | None:
    files = freeze.get("files")
    if not isinstance(files, list):
        return None
    for entry in files:
        if isinstance(entry, Mapping) and entry.get("path") == relative:
            return entry
    return None


def _add(codes: list[str], code: ManifestCode) -> None:
    if code.value not in codes:
        codes.append(code.value)


def evaluate_manifest(
    *,
    snapshot: Mapping[str, Any] | None,
    freeze: Mapping[str, Any],
    fresh_readiness: Mapping[str, Any],
    snapshot_sha256: str | None = None,
    snapshot_relative: str = SNAPSHOT_RELATIVE.as_posix(),
    snapshot_source_ancestor: bool | None = None,
    snapshot_origin_ancestor: bool | None = None,
) -> ManifestValidationResult:
    """Validate a supplied snapshot against current readiness and freeze metadata."""
    codes: list[str] = []
    snapshot = dict(snapshot or {})
    fresh_readiness = dict(fresh_readiness)
    freeze = dict(freeze)
    freeze_entry = _freeze_file(freeze, snapshot_relative)

    checks = {
        "snapshot_present": bool(snapshot),
        "snapshot_in_freeze": isinstance(freeze_entry, Mapping),
        "snapshot_hash_matches": (
            isinstance(freeze_entry, Mapping)
            and snapshot_sha256 is not None
            and freeze_entry.get("sha256") == snapshot_sha256
        ),
        "freeze_pass": freeze.get("freeze_status") == "PASS",
        "snapshot_source_matches_freeze": (
            snapshot_source_ancestor
            if snapshot_source_ancestor is not None
            else snapshot.get("source_revision") == freeze.get("source_revision")
        ),
        "snapshot_origin_matches_freeze": (
            snapshot_origin_ancestor
            if snapshot_origin_ancestor is not None
            else snapshot.get("origin_main_revision") == freeze.get("origin_main_revision")
        ),
        "snapshot_decision_ready": (
            snapshot.get("decision") == "INTERNAL_HANDOFF_READY"
            and snapshot.get("remediation_codes") == []
        ),
        "snapshot_checks_match_fresh": snapshot.get("checks") == fresh_readiness.get("checks"),
        "fresh_readiness_ready": (
            fresh_readiness.get("decision") == "INTERNAL_HANDOFF_READY"
            and fresh_readiness.get("remediation_codes") == []
        ),
        "snapshot_claim_locked": (
            snapshot.get("claim_boundary", {}).get("production_ready") is False
            and snapshot.get("claim_boundary", {}).get("clinical_validation") == "PENDING"
            and snapshot.get("claim_boundary", {}).get("status") == "CONTROLLED_PRODUCTION_PROTOTYPE"
        ),
        "snapshot_authorization_locked": snapshot.get("authorization_boundary") == LOCKED_BOUNDARY,
        "snapshot_gate_locked": snapshot.get("external_gate_snapshot") == LOCKED_EXTERNAL_GATE_SNAPSHOT,
        "snapshot_external_submission_disabled": snapshot.get("external_submission_allowed") is False,
        "snapshot_runtime_mutation_absent": snapshot.get("runtime_mutation_performed") is False,
        "snapshot_external_transmission_absent": snapshot.get("external_transmission_performed") is False,
        "snapshot_read_only": snapshot.get("read_only") is True,
    }
    if not checks["snapshot_present"]:
        _add(codes, ManifestCode.SNAPSHOT_MISSING)
    if not checks["snapshot_in_freeze"]:
        _add(codes, ManifestCode.SNAPSHOT_NOT_IN_FREEZE)
    if not checks["snapshot_hash_matches"]:
        _add(codes, ManifestCode.SNAPSHOT_HASH_MISMATCH)
    if not checks["freeze_pass"]:
        _add(codes, ManifestCode.FREEZE_NOT_PASS)
    if not checks["snapshot_source_matches_freeze"]:
        _add(codes, ManifestCode.SNAPSHOT_SOURCE_REVISION_MISMATCH)
    if not checks["snapshot_origin_matches_freeze"]:
        _add(codes, ManifestCode.SNAPSHOT_ORIGIN_REVISION_MISMATCH)
    if not checks["snapshot_decision_ready"]:
        _add(codes, ManifestCode.SNAPSHOT_DECISION_MISMATCH)
    if not checks["snapshot_checks_match_fresh"]:
        _add(codes, ManifestCode.SNAPSHOT_CHECKS_MISMATCH)
    if not checks["fresh_readiness_ready"]:
        _add(codes, ManifestCode.FRESH_READINESS_BLOCKED)
        _add(codes, ManifestCode.FRESH_READINESS_MISMATCH)
    if not checks["snapshot_claim_locked"]:
        _add(codes, ManifestCode.SNAPSHOT_CLAIM_BOUNDARY_MUTATED)
    if not checks["snapshot_authorization_locked"]:
        _add(codes, ManifestCode.SNAPSHOT_AUTHORIZATION_MUTATED)
    if not checks["snapshot_gate_locked"]:
        _add(codes, ManifestCode.SNAPSHOT_GATE_BOUNDARY_MUTATED)
    if not checks["snapshot_external_submission_disabled"]:
        _add(codes, ManifestCode.SNAPSHOT_EXTERNAL_SUBMISSION_ENABLED)
    if not checks["snapshot_runtime_mutation_absent"]:
        _add(codes, ManifestCode.SNAPSHOT_RUNTIME_MUTATION)
    if not checks["snapshot_external_transmission_absent"] or not checks["snapshot_read_only"]:
        _add(codes, ManifestCode.SNAPSHOT_EXTERNAL_TRANSMISSION)

    decision = ManifestDecision.VALID.value if not codes else ManifestDecision.INVALID.value
    return ManifestValidationResult(
        decision=decision,
        remediation_codes=tuple(codes),
        checks=checks,
        snapshot=snapshot,
        fresh_readiness=fresh_readiness,
        freeze=freeze,
    )


def _is_ancestor(root: Path, older: Any, newer: Any) -> bool:
    if not isinstance(older, str) or not isinstance(newer, str):
        return False
    try:
        return subprocess.run(
            ["git", "merge-base", "--is-ancestor", older, newer],
            cwd=root,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def validate_repository(root: Path = ROOT) -> dict[str, Any]:
    """Validate the tracked pre-handoff snapshot without writing any files."""
    snapshot_path = root / SNAPSHOT_RELATIVE
    freeze_path = root / FREEZE_RELATIVE
    snapshot = _load(snapshot_path)
    freeze = _load(freeze_path) or {}
    fresh = check_pre_handoff(root)
    snapshot_sha = _sha256(snapshot_path) if snapshot_path.is_file() else None
    result = evaluate_manifest(
        snapshot=snapshot,
        freeze=freeze,
        fresh_readiness=fresh,
        snapshot_sha256=snapshot_sha,
        snapshot_source_ancestor=_is_ancestor(root, snapshot.get("source_revision"), freeze.get("source_revision")),
        snapshot_origin_ancestor=_is_ancestor(root, snapshot.get("origin_main_revision"), freeze.get("origin_main_revision")),
    )
    return {
        "evidence_type": "PRE_HANDOFF_EVIDENCE_MANIFEST_VALIDATION",
        "schema_version": "smart-ward-pre-handoff-manifest-v1",
        "decision": result.decision,
        "remediation_codes": list(result.remediation_codes),
        "checks": result.checks,
        "snapshot_source_revision": result.snapshot.get("source_revision"),
        "freeze_source_revision": result.freeze.get("source_revision"),
        "origin_main_revision": result.freeze.get("origin_main_revision"),
        "snapshot_relative": SNAPSHOT_RELATIVE.as_posix(),
        "external_gate_snapshot": result.freeze.get("external_gate_snapshot"),
        "read_only": True,
        "external_submission_allowed": False,
        "authorization_promoted": False,
        "runtime_mutation_performed": False,
        "external_transmission_performed": False,
        "claim_boundary": {
            "status": "CONTROLLED_PRODUCTION_PROTOTYPE",
            "clinical_validation": "PENDING",
            "production_ready": False,
        },
        "authorization_boundary": dict(LOCKED_BOUNDARY),
    }


if __name__ == "__main__":
    report = validate_repository()
    print(json.dumps(report, sort_keys=True, indent=2))
    print("PRE_HANDOFF_MANIFEST_VALID" if report["decision"] == ManifestDecision.VALID.value else "PRE_HANDOFF_MANIFEST_INVALID")
