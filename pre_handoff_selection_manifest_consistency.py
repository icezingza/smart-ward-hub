"""Read-only consistency check across pre-handoff evidence artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import json
from pathlib import Path
import subprocess
from typing import Any, Mapping

from canonical_file_hash import canonical_sha256
from consolidated_internal_handoff_index import LOCKED_BOUNDARY, LOCKED_EXTERNAL_GATE_SNAPSHOT
from pre_handoff_evidence_selection import DEPENDENCY_ORDER, SELECTED_SET, select_repository


ROOT = Path(__file__).resolve().parent
SELECTION_RELATIVE = Path("evals/micro_rag/evidence/pre-handoff-evidence-selection-local.json")
READINESS_RELATIVE = Path("evals/micro_rag/evidence/pre-handoff-readiness-local.json")
MANIFEST_RELATIVE = Path("evals/micro_rag/evidence/pre-handoff-manifest-validation-local.json")
FREEZE_RELATIVE = Path("evals/micro_rag/evidence/release-candidate-freeze-20260820.json")


class ConsistencyDecision(StrEnum):
    CONSISTENT = "SELECTION_MANIFEST_CONSISTENT"
    INCONSISTENT = "SELECTION_MANIFEST_INCONSISTENT"


class ConsistencyCode(StrEnum):
    SELECTION_SNAPSHOT_MISSING = "SELECTION_SNAPSHOT_MISSING"
    READINESS_SNAPSHOT_MISSING = "READINESS_SNAPSHOT_MISSING"
    MANIFEST_SNAPSHOT_MISSING = "MANIFEST_SNAPSHOT_MISSING"
    FREEZE_SNAPSHOT_MISSING = "FREEZE_SNAPSHOT_MISSING"
    SELECTION_DECISION_MISMATCH = "SELECTION_DECISION_MISMATCH"
    SELECTION_DEPENDENCY_ORDER_MISMATCH = "SELECTION_DEPENDENCY_ORDER_MISMATCH"
    SELECTION_ARTIFACT_LIST_MISMATCH = "SELECTION_ARTIFACT_LIST_MISMATCH"
    SELECTION_ARTIFACT_HASH_MISMATCH = "SELECTION_ARTIFACT_HASH_MISMATCH"
    SELECTION_FREEZE_LINEAGE_MISMATCH = "SELECTION_FREEZE_LINEAGE_MISMATCH"
    READINESS_DECISION_MISMATCH = "READINESS_DECISION_MISMATCH"
    MANIFEST_DECISION_MISMATCH = "MANIFEST_DECISION_MISMATCH"
    MANIFEST_READINESS_BINDING_MISMATCH = "MANIFEST_READINESS_BINDING_MISMATCH"
    PACKAGE_BOUNDARY_MISMATCH = "PACKAGE_BOUNDARY_MISMATCH"
    CLAIM_BOUNDARY_MISMATCH = "CLAIM_BOUNDARY_MISMATCH"
    AUTHORIZATION_BOUNDARY_MISMATCH = "AUTHORIZATION_BOUNDARY_MISMATCH"
    EXTERNAL_GATE_BOUNDARY_MISMATCH = "EXTERNAL_GATE_BOUNDARY_MISMATCH"
    EXTERNAL_SUBMISSION_ENABLED = "EXTERNAL_SUBMISSION_ENABLED"
    RUNTIME_MUTATION_DETECTED = "RUNTIME_MUTATION_DETECTED"
    EXTERNAL_TRANSMISSION_DETECTED = "EXTERNAL_TRANSMISSION_DETECTED"
    CONSISTENCY_CHECK_NOT_READ_ONLY = "CONSISTENCY_CHECK_NOT_READ_ONLY"


@dataclass(frozen=True, slots=True)
class ConsistencyResult:
    decision: str
    remediation_codes: tuple[str, ...]
    checks: dict[str, bool]
    selection: dict[str, Any]
    readiness: dict[str, Any]
    manifest: dict[str, Any]
    freeze: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "remediation_codes": list(self.remediation_codes),
            "checks": dict(self.checks),
            "selection": dict(self.selection),
            "readiness": dict(self.readiness),
            "manifest": dict(self.manifest),
            "freeze": dict(self.freeze),
        }


def _load(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _sha256(path: Path) -> str | None:
    try:
        return canonical_sha256(path)
    except OSError:
        return None


def _is_ancestor(root: Path | None, older: Any, newer: Any) -> bool:
    if root is None:
        return bool(isinstance(older, str) and isinstance(newer, str) and older == newer)
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


def _freeze_entries(freeze: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    files = freeze.get("files")
    if not isinstance(files, list):
        return {}
    return {
        entry.get("path"): entry
        for entry in files
        if isinstance(entry, Mapping) and isinstance(entry.get("path"), str)
    }


def _add(codes: list[str], code: ConsistencyCode) -> None:
    if code.value not in codes:
        codes.append(code.value)


def _rows(value: Any) -> list[dict[str, Any]]:
    return [dict(item) for item in value] if isinstance(value, list) and all(isinstance(item, Mapping) for item in value) else []


def evaluate_consistency(
    *,
    selection: Mapping[str, Any] | None,
    readiness: Mapping[str, Any] | None,
    manifest: Mapping[str, Any] | None,
    freeze: Mapping[str, Any] | None,
    current_selection: Mapping[str, Any] | None = None,
    lineage_valid: bool | None = None,
) -> ConsistencyResult:
    """Compare snapshots and fail closed on any cross-artifact mismatch."""
    selection = dict(selection or {})
    readiness = dict(readiness or {})
    manifest = dict(manifest or {})
    freeze = dict(freeze or {})
    current_selection = dict(current_selection or {})
    codes: list[str] = []
    freeze_entries = _freeze_entries(freeze)
    selected_rows = _rows(selection.get("selected"))
    current_rows = _rows(current_selection.get("selected"))
    required_paths = {path for _package_id, path, _role in SELECTED_SET}
    selected_paths = {row.get("path") for row in selected_rows}
    current_path_hashes = {row.get("path"): row.get("sha256") for row in current_rows}
    selected_path_hashes = {row.get("path"): row.get("sha256") for row in selected_rows}
    all_boundary_objects_locked = (
        selection.get("authorization_boundary") == LOCKED_BOUNDARY
        and readiness.get("authorization_boundary") == LOCKED_BOUNDARY
        and manifest.get("authorization_boundary") == LOCKED_BOUNDARY
        and freeze.get("authorization_boundary") == LOCKED_BOUNDARY
    )
    all_claims_locked = all(
        artifact.get("claim_boundary", {}).get("status") == "CONTROLLED_PRODUCTION_PROTOTYPE"
        and artifact.get("claim_boundary", {}).get("clinical_validation") == "PENDING"
        and artifact.get("claim_boundary", {}).get("production_ready") is False
        for artifact in (selection, readiness, manifest)
    )
    gates_locked = (
        selection.get("external_gate_snapshot") == LOCKED_EXTERNAL_GATE_SNAPSHOT
        and readiness.get("external_gate_snapshot") == LOCKED_EXTERNAL_GATE_SNAPSHOT
        and manifest.get("external_gate_snapshot") == LOCKED_EXTERNAL_GATE_SNAPSHOT
        and freeze.get("external_gate_snapshot") == LOCKED_EXTERNAL_GATE_SNAPSHOT
    )
    snapshots_present = bool(selection) and bool(readiness) and bool(manifest) and bool(freeze)
    if not selection:
        _add(codes, ConsistencyCode.SELECTION_SNAPSHOT_MISSING)
    if not readiness:
        _add(codes, ConsistencyCode.READINESS_SNAPSHOT_MISSING)
    if not manifest:
        _add(codes, ConsistencyCode.MANIFEST_SNAPSHOT_MISSING)
    if not freeze:
        _add(codes, ConsistencyCode.FREEZE_SNAPSHOT_MISSING)

    checks = {
        "snapshots_present": snapshots_present,
        "selection_valid": selection.get("decision") == "SELECTED_SET_VALID" and selection.get("remediation_codes") == [],
        "readiness_valid": readiness.get("decision") == "INTERNAL_HANDOFF_READY" and readiness.get("remediation_codes") == [],
        "manifest_valid": manifest.get("decision") == "MANIFEST_VALID" and manifest.get("remediation_codes") == [],
        "freeze_pass": freeze.get("freeze_status") == "PASS",
        "dependency_order_matches": selection.get("dependency_order") == list(DEPENDENCY_ORDER),
        "selected_artifacts_complete": selected_paths == required_paths and len(selected_rows) == len(SELECTED_SET),
        "selected_artifacts_match_current": selected_path_hashes == current_path_hashes,
        "selected_artifacts_match_freeze": all(
            path in freeze_entries and freeze_entries[path].get("sha256") == selected_path_hashes.get(path)
            for path in required_paths
        ),
        "freeze_lineage_valid": (
            lineage_valid
            if lineage_valid is not None
            else _is_ancestor(None, selection.get("freeze_source_revision"), freeze.get("source_revision"))
        ),
        "manifest_binds_readiness": (
            manifest.get("snapshot_relative") == READINESS_RELATIVE.as_posix()
            and manifest.get("snapshot_source_revision") == readiness.get("source_revision")
            and manifest.get("decision") == "MANIFEST_VALID"
        ),
        "selection_statuses_bind_upstream": (
            next((row.get("status") for row in selected_rows if row.get("package_id") == "pre_handoff_readiness"), None) == "INTERNAL_HANDOFF_READY"
            and next((row.get("status") for row in selected_rows if row.get("package_id") == "pre_handoff_manifest_validation"), None) == "MANIFEST_VALID"
        ),
        "authorization_boundary_locked": all_boundary_objects_locked,
        "claim_boundary_locked": all_claims_locked,
        "external_gate_boundary_locked": gates_locked,
        "external_submission_disabled": all(artifact.get("external_submission_allowed") is False for artifact in (selection, readiness, manifest)),
        "runtime_mutation_absent": all(artifact.get("runtime_mutation_performed") is False for artifact in (selection, readiness, manifest)),
        "external_transmission_absent": all(artifact.get("external_transmission_performed") is False for artifact in (selection, readiness, manifest)),
        "read_only": all(artifact.get("read_only") is True for artifact in (selection, readiness, manifest)),
    }
    if not checks["selection_valid"]:
        _add(codes, ConsistencyCode.SELECTION_DECISION_MISMATCH)
    if not checks["readiness_valid"]:
        _add(codes, ConsistencyCode.READINESS_DECISION_MISMATCH)
    if not checks["manifest_valid"]:
        _add(codes, ConsistencyCode.MANIFEST_DECISION_MISMATCH)
    if not checks["freeze_pass"]:
        _add(codes, ConsistencyCode.FREEZE_SNAPSHOT_MISSING)
    if not checks["dependency_order_matches"]:
        _add(codes, ConsistencyCode.SELECTION_DEPENDENCY_ORDER_MISMATCH)
    if not checks["selected_artifacts_complete"]:
        _add(codes, ConsistencyCode.SELECTION_ARTIFACT_LIST_MISMATCH)
    if not checks["selected_artifacts_match_current"] or not checks["selected_artifacts_match_freeze"]:
        _add(codes, ConsistencyCode.SELECTION_ARTIFACT_HASH_MISMATCH)
    if not checks["freeze_lineage_valid"]:
        _add(codes, ConsistencyCode.SELECTION_FREEZE_LINEAGE_MISMATCH)
    if not checks["manifest_binds_readiness"]:
        _add(codes, ConsistencyCode.MANIFEST_READINESS_BINDING_MISMATCH)
    if not checks["selection_statuses_bind_upstream"]:
        _add(codes, ConsistencyCode.PACKAGE_BOUNDARY_MISMATCH)
    if not checks["authorization_boundary_locked"]:
        _add(codes, ConsistencyCode.AUTHORIZATION_BOUNDARY_MISMATCH)
    if not checks["claim_boundary_locked"]:
        _add(codes, ConsistencyCode.CLAIM_BOUNDARY_MISMATCH)
    if not checks["external_gate_boundary_locked"]:
        _add(codes, ConsistencyCode.EXTERNAL_GATE_BOUNDARY_MISMATCH)
    if not checks["external_submission_disabled"]:
        _add(codes, ConsistencyCode.EXTERNAL_SUBMISSION_ENABLED)
    if not checks["runtime_mutation_absent"]:
        _add(codes, ConsistencyCode.RUNTIME_MUTATION_DETECTED)
    if not checks["external_transmission_absent"]:
        _add(codes, ConsistencyCode.EXTERNAL_TRANSMISSION_DETECTED)
    if not checks["read_only"]:
        _add(codes, ConsistencyCode.CONSISTENCY_CHECK_NOT_READ_ONLY)

    return ConsistencyResult(
        decision=ConsistencyDecision.CONSISTENT.value if not codes else ConsistencyDecision.INCONSISTENT.value,
        remediation_codes=tuple(codes),
        checks=checks,
        selection=selection,
        readiness=readiness,
        manifest=manifest,
        freeze=freeze,
    )


def _lineage_valid(root: Path, revisions: tuple[Any, ...], freeze_source: Any) -> bool:
    return all(_is_ancestor(root, revision, freeze_source) for revision in revisions)


def check_repository(root: Path = ROOT) -> dict[str, Any]:
    selection = _load(root / SELECTION_RELATIVE)
    readiness = _load(root / READINESS_RELATIVE)
    manifest = _load(root / MANIFEST_RELATIVE)
    freeze = _load(root / FREEZE_RELATIVE)
    current_selection = select_repository(root)
    lineage = _lineage_valid(
        root,
        (
            selection.get("freeze_source_revision") if selection else None,
            readiness.get("freeze_source_revision") if readiness else None,
            manifest.get("freeze_source_revision") if manifest else None,
            readiness.get("source_revision") if readiness else None,
            manifest.get("source_revision") if manifest else None,
        ),
        freeze.get("source_revision") if freeze else None,
    )
    result = evaluate_consistency(
        selection=selection,
        readiness=readiness,
        manifest=manifest,
        freeze=freeze,
        current_selection=current_selection,
        lineage_valid=lineage,
    )
    return {
        "evidence_type": "PRE_HANDOFF_SELECTION_MANIFEST_CONSISTENCY",
        "schema_version": "smart-ward-pre-handoff-consistency-v1",
        "decision": result.decision,
        "remediation_codes": list(result.remediation_codes),
        "checks": result.checks,
        "selected_set_decision": selection.get("decision") if selection else None,
        "pre_handoff_decision": readiness.get("decision") if readiness else None,
        "manifest_decision": manifest.get("decision") if manifest else None,
        "freeze_source_revision": freeze.get("source_revision") if freeze else None,
        "origin_main_revision": freeze.get("origin_main_revision") if freeze else None,
        "selected_count": len(result.selection.get("selected", [])),
        "dependency_order": list(DEPENDENCY_ORDER),
        "external_gate_snapshot": LOCKED_EXTERNAL_GATE_SNAPSHOT,
        "claim_boundary": {
            "status": "CONTROLLED_PRODUCTION_PROTOTYPE",
            "clinical_validation": "PENDING",
            "production_ready": False,
        },
        "authorization_boundary": dict(LOCKED_BOUNDARY),
        "read_only": True,
        "external_submission_allowed": False,
        "authorization_promoted": False,
        "runtime_mutation_performed": False,
        "external_transmission_performed": False,
    }


if __name__ == "__main__":
    report = check_repository()
    print(json.dumps(report, sort_keys=True, indent=2))
    print("PRE_HANDOFF_SELECTION_MANIFEST_CONSISTENT" if report["decision"] == ConsistencyDecision.CONSISTENT.value else "PRE_HANDOFF_SELECTION_MANIFEST_INCONSISTENT")
