"""Read-only drift detector for the Smart Ward Hub release freeze.

The monitor compares current repository bytes and local evidence boundaries with
the authoritative release-freeze manifest. It reports drift and remediation
codes but never rewrites the manifest, evidence, runtime state, or authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import hashlib
import json
from pathlib import Path
import re
import subprocess
from typing import Any, Mapping

from consolidated_internal_handoff_index import build_index


ROOT = Path(__file__).resolve().parent
FREEZE_RELATIVE = Path("evals/micro_rag/evidence/release-candidate-freeze-20260820.json")
BINDING_RELATIVE = Path("evals/micro_rag/evidence/cross-package-binding-local.json")
HANDOFF_RELATIVE = Path("evals/micro_rag/evidence/consolidated-internal-handoff-index-local.json")
HEX40 = re.compile(r"^[0-9a-f]{40}$")
RUNTIME_NAMES = {
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
LOCKED_BOUNDARY = {
    "external_authority": "NONE",
    "clinical_validation_authorized": False,
    "production_authorized": False,
    "runtime_authority": "NONE",
    "pilot_gate_status": "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION",
}
LOCKED_GATES = {"blocked": 7, "open": 3, "evidence_submitted": 0, "passed": 0}


class DriftDecision(StrEnum):
    DRIFT_FREE = "DRIFT_FREE"
    DRIFT_DETECTED = "DRIFT_DETECTED"


class DriftCode(StrEnum):
    FREEZE_MANIFEST_INVALID = "FREEZE_MANIFEST_INVALID"
    FREEZE_STATUS_NOT_PASS = "FREEZE_STATUS_NOT_PASS"
    FREEZE_SOURCE_REVISION_INVALID = "FREEZE_SOURCE_REVISION_INVALID"
    FREEZE_ORIGIN_REVISION_INVALID = "FREEZE_ORIGIN_REVISION_INVALID"
    HEAD_NOT_ALIGNED_TO_FREEZE = "HEAD_NOT_ALIGNED_TO_FREEZE"
    FREEZE_TRACKED_FILE_MISSING = "FREEZE_TRACKED_FILE_MISSING"
    FREEZE_TRACKED_FILE_HASH_MISMATCH = "FREEZE_TRACKED_FILE_HASH_MISMATCH"
    UNFROZEN_TRACKED_FILE = "UNFROZEN_TRACKED_FILE"
    RUNTIME_ARTIFACT_PRESENT = "RUNTIME_ARTIFACT_PRESENT"
    SECRET_HIT_REPORTED = "SECRET_HIT_REPORTED"
    FREEZE_BOUNDARY_MUTATED = "FREEZE_BOUNDARY_MUTATED"
    EXTERNAL_GATE_SNAPSHOT_MUTATED = "EXTERNAL_GATE_SNAPSHOT_MUTATED"
    CROSS_PACKAGE_BINDING_DRIFTED = "CROSS_PACKAGE_BINDING_DRIFTED"
    HANDOFF_INDEX_DRIFTED = "HANDOFF_INDEX_DRIFTED"
    HANDOFF_INDEX_NOT_BOUND = "HANDOFF_INDEX_NOT_BOUND"


@dataclass(frozen=True, slots=True)
class DriftResult:
    decision: str
    remediation_codes: tuple[str, ...]
    checks: dict[str, bool]
    artifact_results: tuple[dict[str, Any], ...]
    revisions: dict[str, str | None]
    read_only: bool
    mutation_performed: bool
    authorization_boundary: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "remediation_codes": list(self.remediation_codes),
            "checks": dict(self.checks),
            "artifact_results": [dict(item) for item in self.artifact_results],
            "revisions": dict(self.revisions),
            "read_only": self.read_only,
            "mutation_performed": self.mutation_performed,
            "authorization_boundary": dict(self.authorization_boundary),
        }


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _git(root: Path, *args: str) -> str | None:
    try:
        return subprocess.check_output(["git", *args], cwd=root, text=True, stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.SubprocessError):
        return None


def revision_is_ancestor(root: Path, ancestor: Any, descendant: Any) -> bool:
    """Return whether a valid local Git revision is an ancestor of another."""
    if not _revision(ancestor) or not _revision(descendant):
        return False
    return _git(root, "merge-base", "--is-ancestor", str(ancestor), str(descendant)) is not None


def _revision(value: Any) -> bool:
    return isinstance(value, str) and HEX40.fullmatch(value) is not None


def _freeze_files(freeze: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    files = freeze.get("files")
    if not isinstance(files, list):
        return {}
    return {
        entry.get("path"): entry
        for entry in files
        if isinstance(entry, Mapping) and isinstance(entry.get("path"), str)
    }


def _runtime_artifacts(root: Path) -> list[str]:
    return sorted(
        str(path.relative_to(root))
        for path in root.rglob("*")
        if path.is_file() and path.name in RUNTIME_NAMES
    )


def _add(codes: list[str], code: DriftCode) -> None:
    if code.value not in codes:
        codes.append(code.value)


def evaluate_drift(
    *,
    root: Path,
    freeze: Mapping[str, Any] | None,
    binding: Mapping[str, Any] | None,
    handoff: Mapping[str, Any] | None,
    current_head: str | None,
    current_parent: str | None,
    origin_main: str | None,
    tracked_paths: list[str] | None = None,
    runtime_artifacts: list[str] | None = None,
    file_hashes: Mapping[str, str | None] | None = None,
) -> DriftResult:
    """Evaluate drift using supplied snapshots without modifying the filesystem."""
    codes: list[str] = []
    checks: dict[str, bool] = {}
    artifact_results: list[dict[str, Any]] = []
    freeze = freeze or {}
    binding = binding or {}
    handoff = handoff or {}
    freeze_source = freeze.get("source_revision")
    freeze_origin = freeze.get("origin_main_revision")

    checks["freeze_manifest_object"] = bool(freeze)
    if not checks["freeze_manifest_object"]:
        _add(codes, DriftCode.FREEZE_MANIFEST_INVALID)
    checks["freeze_status_pass"] = freeze.get("freeze_status") == "PASS"
    if not checks["freeze_status_pass"]:
        _add(codes, DriftCode.FREEZE_STATUS_NOT_PASS)
    checks["freeze_source_revision_valid"] = _revision(freeze_source)
    if not checks["freeze_source_revision_valid"]:
        _add(codes, DriftCode.FREEZE_SOURCE_REVISION_INVALID)
    checks["freeze_origin_revision_valid"] = _revision(freeze_origin)
    if not checks["freeze_origin_revision_valid"]:
        _add(codes, DriftCode.FREEZE_ORIGIN_REVISION_INVALID)
    checks["freeze_origin_equals_source"] = checks["freeze_source_revision_valid"] and freeze_source == freeze_origin
    if not checks["freeze_origin_equals_source"]:
        _add(codes, DriftCode.HEAD_NOT_ALIGNED_TO_FREEZE)
    checks["head_parent_matches_freeze_source"] = (
        checks["freeze_source_revision_valid"] and current_parent == freeze_source
    )
    if not checks["head_parent_matches_freeze_source"]:
        _add(codes, DriftCode.HEAD_NOT_ALIGNED_TO_FREEZE)
    checks["head_matches_origin_main"] = current_head is not None and current_head == origin_main
    if not checks["head_matches_origin_main"]:
        _add(codes, DriftCode.HEAD_NOT_ALIGNED_TO_FREEZE)

    freeze_files = _freeze_files(freeze)
    tracked_paths = tracked_paths or []
    tracked_set = set(tracked_paths)
    # freeze_release_candidate.py deliberately excludes its own manifest from
    # files[]. Treat that self-hash exclusion as authoritative rather than
    # reporting the manifest itself as an unfrozen tracked asset.
    tracked_set_without_manifest = tracked_set - {FREEZE_RELATIVE.as_posix()}
    freeze_set = set(freeze_files)
    checks["tracked_set_matches_freeze"] = tracked_set_without_manifest == freeze_set
    if not checks["tracked_set_matches_freeze"]:
        for path in sorted(tracked_set_without_manifest - freeze_set):
            artifact_results.append({"path": path, "status": "UNFROZEN_TRACKED_FILE"})
            _add(codes, DriftCode.UNFROZEN_TRACKED_FILE)
        for path in sorted(freeze_set - tracked_set_without_manifest):
            artifact_results.append({"path": path, "status": "FREEZE_TRACKED_FILE_MISSING"})
            _add(codes, DriftCode.FREEZE_TRACKED_FILE_MISSING)

    file_hashes = file_hashes or {}
    for path, entry in sorted(freeze_files.items()):
        expected = entry.get("sha256")
        actual = file_hashes.get(path)
        if actual is None:
            artifact_results.append({"path": path, "status": "MISSING", "expected_sha256": expected})
            _add(codes, DriftCode.FREEZE_TRACKED_FILE_MISSING)
        elif actual != expected:
            artifact_results.append({"path": path, "status": "HASH_MISMATCH", "expected_sha256": expected, "actual_sha256": actual})
            _add(codes, DriftCode.FREEZE_TRACKED_FILE_HASH_MISMATCH)
        else:
            artifact_results.append({"path": path, "status": "MATCH", "sha256": actual})
    checks["freeze_file_hashes_match"] = not any(row["status"] in {"MISSING", "HASH_MISMATCH"} for row in artifact_results)

    runtime_artifacts = runtime_artifacts if runtime_artifacts is not None else _runtime_artifacts(root)
    checks["runtime_artifacts_absent"] = not runtime_artifacts
    if runtime_artifacts:
        _add(codes, DriftCode.RUNTIME_ARTIFACT_PRESENT)
    secret_hits = freeze.get("secret_hits")
    checks["freeze_secret_hits_empty"] = secret_hits == []
    if not checks["freeze_secret_hits_empty"]:
        _add(codes, DriftCode.SECRET_HIT_REPORTED)
    checks["freeze_boundary_locked"] = freeze.get("authorization_boundary") == LOCKED_BOUNDARY
    if not checks["freeze_boundary_locked"]:
        _add(codes, DriftCode.FREEZE_BOUNDARY_MUTATED)
    checks["external_gate_snapshot_locked"] = freeze.get("external_gate_snapshot") == LOCKED_GATES
    if not checks["external_gate_snapshot_locked"]:
        _add(codes, DriftCode.EXTERNAL_GATE_SNAPSHOT_MUTATED)

    binding_ok = (
        binding.get("decision") == "BOUND"
        and binding.get("remediation_codes") == ["EVIDENCE_PACKAGES_BOUND"]
        and binding.get("read_only") is True
        and binding.get("external_transmission_performed") is False
        and binding.get("redaction_verified") is True
        and all(value is True for value in binding.get("checks", {}).values())
    )
    checks["cross_package_binding_bound"] = binding_ok
    if not binding_ok:
        _add(codes, DriftCode.CROSS_PACKAGE_BINDING_DRIFTED)

    handoff_ok = (
        handoff.get("decision") == "BOUND"
        and handoff.get("remediation_codes") == ["HANDOFF_INDEX_BOUND"]
        and handoff.get("read_only") is True
        and handoff.get("external_submission_allowed") is False
        and handoff.get("authorization_promoted") is False
        and handoff.get("runtime_mutation_performed") is False
        and handoff.get("redaction_verified") is True
        and handoff.get("index", {}).get("decision") == "BOUND"
    )
    checks["handoff_index_bound"] = handoff_ok
    if not handoff_ok:
        _add(codes, DriftCode.HANDOFF_INDEX_NOT_BOUND)
        _add(codes, DriftCode.HANDOFF_INDEX_DRIFTED)

    revisions = {
        "current_head": current_head,
        "current_parent": current_parent,
        "origin_main": origin_main,
        "freeze_source": str(freeze_source) if freeze_source is not None else None,
        "freeze_origin": str(freeze_origin) if freeze_origin is not None else None,
        "binding_source": str(binding.get("source_revision")) if binding.get("source_revision") is not None else None,
        "handoff_source": str(handoff.get("source_revision")) if handoff.get("source_revision") is not None else None,
    }
    if not codes:
        codes = [DriftDecision.DRIFT_FREE.value]
    decision = DriftDecision.DRIFT_FREE.value if codes == [DriftDecision.DRIFT_FREE.value] else DriftDecision.DRIFT_DETECTED.value
    return DriftResult(
        decision=decision,
        remediation_codes=tuple(codes),
        checks=checks,
        artifact_results=tuple(artifact_results),
        revisions=revisions,
        read_only=True,
        mutation_performed=False,
        authorization_boundary=deepcopy_boundary(),
    )


def deepcopy_boundary() -> dict[str, Any]:
    return dict(LOCKED_BOUNDARY)


def check_repository(root: Path = ROOT) -> dict[str, Any]:
    """Run a local drift scan and return a redacted machine-readable result."""
    freeze = _load_json(root / FREEZE_RELATIVE)
    binding = _load_json(root / BINDING_RELATIVE)
    handoff = _load_json(root / HANDOFF_RELATIVE)
    current_head = _git(root, "rev-parse", "HEAD")
    current_parent = _git(root, "rev-parse", "HEAD^")
    origin_main = _git(root, "rev-parse", "origin/main")
    tracked_output = _git(root, "ls-files") or ""
    tracked_paths = [line for line in tracked_output.splitlines() if line]
    freeze_files = _freeze_files(freeze or {})
    file_hashes = {
        relative: _sha256_path(root / relative)
        if (root / relative).is_file()
        else None
        for relative in freeze_files
    }
    result = evaluate_drift(
        root=root,
        freeze=freeze,
        binding=binding,
        handoff=handoff,
        current_head=current_head,
        current_parent=current_parent,
        origin_main=origin_main,
        tracked_paths=tracked_paths,
        runtime_artifacts=_runtime_artifacts(root),
        file_hashes=file_hashes,
    )
    return {
        "evidence_type": "FREEZE_INTEGRITY_DRIFT_SCAN",
        "schema_version": "smart-ward-freeze-drift-v1",
        "decision": result.decision,
        "remediation_codes": list(result.remediation_codes),
        "checks": result.checks,
        "artifact_results": list(result.artifact_results),
        "revisions": result.revisions,
        "tracked_file_count": len(tracked_paths),
        "freeze_file_count": len(freeze_files),
        "read_only": True,
        "mutation_performed": False,
        "external_transmission_performed": False,
        "authorization_boundary": result.authorization_boundary,
        "claim_boundary": {
            "status": "CONTROLLED_PRODUCTION_PROTOTYPE",
            "functional_verification": "PASSED" if result.decision == DriftDecision.DRIFT_FREE.value else "PENDING_RECONCILIATION",
            "clinical_validation": "PENDING",
            "production_ready": False,
        },
    }


if __name__ == "__main__":
    report = check_repository()
    print(json.dumps(report, sort_keys=True, indent=2))
    print("FREEZE_DRIFT_FREE" if report["decision"] == DriftDecision.DRIFT_FREE.value else "FREEZE_DRIFT_DETECTED")
