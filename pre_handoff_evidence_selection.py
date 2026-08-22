"""Read-only policy for selecting an internal pre-handoff evidence set.

The selector produces a navigation/selection record only. It never copies,
submits, deletes, signs, or promotes evidence and authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any, Mapping

from consolidated_internal_handoff_index import LOCKED_BOUNDARY, LOCKED_EXTERNAL_GATE_SNAPSHOT


ROOT = Path(__file__).resolve().parent
FREEZE_RELATIVE = Path("evals/micro_rag/evidence/release-candidate-freeze-20260820.json")

SELECTED_SET = (
    ("wave0_governance_handoff", "evals/micro_rag/evidence/wave0-governance-handoff-20260820.json", "governance"),
    ("p2_external_review_handoff", "evals/micro_rag/evidence/p2-004-external-review-handoff-20260820.json", "governance"),
    ("worker_recovery_transcript", "evals/micro_rag/evidence/worker-recovery-transcript-local.json", "worker_recovery"),
    ("worker_recovery_approval_readback", "evals/micro_rag/evidence/worker-recovery-approval-local.json", "worker_recovery"),
    ("durable_worker_replay", "evals/micro_rag/evidence/durable-worker-replay-local.json", "worker_recovery"),
    ("cross_package_binding", "evals/micro_rag/evidence/cross-package-binding-local.json", "binding"),
    ("consolidated_internal_handoff", "evals/micro_rag/evidence/consolidated-internal-handoff-index-local.json", "handoff"),
    ("pre_handoff_readiness", "evals/micro_rag/evidence/pre-handoff-readiness-local.json", "readiness"),
    ("pre_handoff_manifest_validation", "evals/micro_rag/evidence/pre-handoff-manifest-validation-local.json", "validation"),
)
DEPENDENCY_ORDER = (
    "wave0_governance_handoff",
    "p2_external_review_handoff",
    "worker_recovery_transcript",
    "worker_recovery_approval_readback",
    "durable_worker_replay",
    "cross_package_binding",
    "consolidated_internal_handoff",
    "pre_handoff_readiness",
    "pre_handoff_manifest_validation",
)
EXCLUDED_RUNTIME_NAMES = {
    "ward_hub.db",
    "ward_hub.db-shm",
    "ward_hub.db-wal",
    "audit_events.jsonl",
    "edge_telemetry_state.json",
    "forensic_anchors.jsonl",
    "reliability_validation_result.json",
    "pilot_simulation_result.json",
    "telemetry.jsonl",
    "serial_bench_evidence.json",
}


class SelectionDecision(StrEnum):
    SELECTED_SET_VALID = "SELECTED_SET_VALID"
    SELECTION_BLOCKED = "SELECTION_BLOCKED"


class SelectionCode(StrEnum):
    FREEZE_NOT_PASS = "FREEZE_NOT_PASS"
    FREEZE_BOUNDARY_MUTATED = "FREEZE_BOUNDARY_MUTATED"
    EXTERNAL_GATE_SNAPSHOT_MUTATED = "EXTERNAL_GATE_SNAPSHOT_MUTATED"
    REQUIRED_ARTIFACT_MISSING = "REQUIRED_ARTIFACT_MISSING"
    REQUIRED_ARTIFACT_NOT_FROZEN = "REQUIRED_ARTIFACT_NOT_FROZEN"
    ARTIFACT_HASH_MISMATCH = "ARTIFACT_HASH_MISMATCH"
    DEPENDENCY_ORDER_INVALID = "DEPENDENCY_ORDER_INVALID"
    PACKAGE_DECISION_INVALID = "PACKAGE_DECISION_INVALID"
    PACKAGE_BOUNDARY_INVALID = "PACKAGE_BOUNDARY_INVALID"
    RUNTIME_ARTIFACT_SELECTED = "RUNTIME_ARTIFACT_SELECTED"
    EXTERNAL_SUBMISSION_FORBIDDEN = "EXTERNAL_SUBMISSION_FORBIDDEN"
    AUTHORIZATION_PROMOTION_FORBIDDEN = "AUTHORIZATION_PROMOTION_FORBIDDEN"


@dataclass(frozen=True, slots=True)
class SelectionResult:
    decision: str
    remediation_codes: tuple[str, ...]
    checks: dict[str, bool]
    selected: tuple[dict[str, Any], ...]
    excluded: tuple[dict[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "remediation_codes": list(self.remediation_codes),
            "checks": dict(self.checks),
            "selected": [dict(item) for item in self.selected],
            "excluded": [dict(item) for item in self.excluded],
        }


def _sha256(path: Path) -> str | None:
    try:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return None


def _load(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _freeze_files(freeze: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    files = freeze.get("files")
    if not isinstance(files, list):
        return {}
    return {
        item.get("path"): item
        for item in files
        if isinstance(item, Mapping) and isinstance(item.get("path"), str)
    }


def _add(codes: list[str], code: SelectionCode) -> None:
    if code.value not in codes:
        codes.append(code.value)


def _package_status(package_id: str, payload: Mapping[str, Any]) -> tuple[bool, str]:
    if package_id == "cross_package_binding":
        return payload.get("decision") == "BOUND" and payload.get("read_only") is True, "BOUND"
    if package_id == "consolidated_internal_handoff":
        return payload.get("decision") == "BOUND" and payload.get("read_only") is True, "BOUND"
    if package_id == "pre_handoff_readiness":
        return payload.get("decision") == "INTERNAL_HANDOFF_READY" and payload.get("remediation_codes") == [], "INTERNAL_HANDOFF_READY"
    if package_id == "pre_handoff_manifest_validation":
        return payload.get("decision") == "MANIFEST_VALID" and payload.get("remediation_codes") == [], "MANIFEST_VALID"
    return True, str(payload.get("decision", "PRESENT"))


def evaluate_selection(
    *,
    root: Path,
    freeze: Mapping[str, Any],
    packages: Mapping[str, Mapping[str, Any] | None],
    package_hashes: Mapping[str, str | None],
    tracked_paths: set[str],
    runtime_artifacts: set[str],
    dependency_order: tuple[str, ...] = DEPENDENCY_ORDER,
) -> SelectionResult:
    """Select the approved internal set or fail closed with remediation codes."""
    codes: list[str] = []
    freeze_files = _freeze_files(freeze)
    selected_rows: list[dict[str, Any]] = []
    excluded_rows = [
        {"path": path, "reason": "RUNTIME_ARTIFACT_EXCLUDED"}
        for path in sorted(runtime_artifacts)
    ]

    checks = {
        "freeze_pass": freeze.get("freeze_status") == "PASS",
        "freeze_boundary_locked": freeze.get("authorization_boundary") == LOCKED_BOUNDARY,
        "external_gate_snapshot_locked": freeze.get("external_gate_snapshot") == LOCKED_EXTERNAL_GATE_SNAPSHOT,
        "dependency_order_valid": tuple(dependency_order) == DEPENDENCY_ORDER,
        "required_artifacts_present": True,
        "required_artifacts_frozen": True,
        "artifact_hashes_match": True,
        "package_boundaries_valid": True,
        "runtime_artifacts_excluded": not runtime_artifacts,
        "external_submission_disabled": True,
        "authorization_promotion_disabled": True,
    }
    if not checks["freeze_pass"]:
        _add(codes, SelectionCode.FREEZE_NOT_PASS)
    if not checks["freeze_boundary_locked"]:
        _add(codes, SelectionCode.FREEZE_BOUNDARY_MUTATED)
    if not checks["external_gate_snapshot_locked"]:
        _add(codes, SelectionCode.EXTERNAL_GATE_SNAPSHOT_MUTATED)
    if not checks["dependency_order_valid"]:
        _add(codes, SelectionCode.DEPENDENCY_ORDER_INVALID)
    if runtime_artifacts:
        checks["runtime_artifacts_excluded"] = False
        _add(codes, SelectionCode.RUNTIME_ARTIFACT_SELECTED)

    for package_id, relative, role in SELECTED_SET:
        payload = packages.get(package_id)
        actual_hash = package_hashes.get(package_id)
        frozen = freeze_files.get(relative)
        if payload is None:
            checks["required_artifacts_present"] = False
            _add(codes, SelectionCode.REQUIRED_ARTIFACT_MISSING)
            selected_rows.append({"package_id": package_id, "path": relative, "role": role, "status": "MISSING"})
            continue
        if frozen is None:
            checks["required_artifacts_frozen"] = False
            _add(codes, SelectionCode.REQUIRED_ARTIFACT_NOT_FROZEN)
        elif actual_hash is None or frozen.get("sha256") != actual_hash:
            checks["artifact_hashes_match"] = False
            _add(codes, SelectionCode.ARTIFACT_HASH_MISMATCH)
        valid, status = _package_status(package_id, payload)
        if not valid:
            checks["package_boundaries_valid"] = False
            _add(codes, SelectionCode.PACKAGE_DECISION_INVALID)
        selected_rows.append(
            {
                "package_id": package_id,
                "path": relative,
                "role": role,
                "status": status if valid else "BLOCKED",
                "sha256": actual_hash,
            }
        )

    if not checks["external_submission_disabled"]:
        _add(codes, SelectionCode.EXTERNAL_SUBMISSION_FORBIDDEN)
    if not checks["authorization_promotion_disabled"]:
        _add(codes, SelectionCode.AUTHORIZATION_PROMOTION_FORBIDDEN)

    decision = SelectionDecision.SELECTED_SET_VALID.value if not codes else SelectionDecision.SELECTION_BLOCKED.value
    return SelectionResult(
        decision=decision,
        remediation_codes=tuple(codes),
        checks=checks,
        selected=tuple(selected_rows),
        excluded=tuple(excluded_rows),
    )


def select_repository(root: Path = ROOT) -> dict[str, Any]:
    freeze = _load(root / FREEZE_RELATIVE) or {}
    packages: dict[str, Mapping[str, Any] | None] = {}
    package_hashes: dict[str, str | None] = {}
    for package_id, relative, _role in SELECTED_SET:
        path = root / relative
        packages[package_id] = _load(path)
        package_hashes[package_id] = _sha256(path)
    try:
        tracked_paths = {
            item for item in subprocess.check_output(
                ["git", "ls-files"], cwd=root, text=True, stderr=subprocess.DEVNULL
            ).splitlines() if item
        }
    except (OSError, subprocess.SubprocessError):
        tracked_paths = set()
    runtime_artifacts = {
        str(path.relative_to(root))
        for path in root.rglob("*")
        if path.is_file() and path.name in EXCLUDED_RUNTIME_NAMES
    }
    result = evaluate_selection(
        root=root,
        freeze=freeze,
        packages=packages,
        package_hashes=package_hashes,
        tracked_paths=tracked_paths,
        runtime_artifacts=runtime_artifacts,
    )
    return {
        "evidence_type": "PRE_HANDOFF_EVIDENCE_SELECTION",
        "schema_version": "smart-ward-pre-handoff-selection-v1",
        "decision": result.decision,
        "remediation_codes": list(result.remediation_codes),
        "checks": result.checks,
        "dependency_order": list(DEPENDENCY_ORDER),
        "selected": list(result.selected),
        "excluded": list(result.excluded),
        "freeze_source_revision": freeze.get("source_revision"),
        "origin_main_revision": freeze.get("origin_main_revision"),
        "external_gate_snapshot": freeze.get("external_gate_snapshot"),
        "authorization_boundary": dict(LOCKED_BOUNDARY),
        "claim_boundary": {
            "status": "CONTROLLED_PRODUCTION_PROTOTYPE",
            "clinical_validation": "PENDING",
            "production_ready": False,
        },
        "read_only": True,
        "external_submission_allowed": False,
        "authorization_promoted": False,
        "runtime_mutation_performed": False,
        "external_transmission_performed": False,
    }


if __name__ == "__main__":
    report = select_repository()
    print(json.dumps(report, sort_keys=True, indent=2))
    print("PRE_HANDOFF_SELECTION_VALID" if report["decision"] == SelectionDecision.SELECTED_SET_VALID.value else "PRE_HANDOFF_SELECTION_BLOCKED")
