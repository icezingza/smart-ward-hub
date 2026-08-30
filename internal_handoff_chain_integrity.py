"""Fail-closed integrity gate for the internal handoff evidence chain."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import json
from pathlib import Path
from typing import Any, Mapping

from canonical_file_hash import canonical_sha256
from freeze_integrity_monitor import revision_is_ancestor


ROOT = Path(__file__).resolve().parent
FREEZE_PATH = Path("evals/micro_rag/evidence/release-candidate-freeze-20260820.json")
HANDOFF_PATH = Path("evals/micro_rag/evidence/consolidated-internal-handoff-index-local.json")
RECONCILIATION_PATH = Path("evals/micro_rag/evidence/pre-handoff-reconciliation-gate-local.json")
EXPOSURE_PATH = Path("evals/micro_rag/evidence/public-exposure-quarantine-local.json")
LOCKED_BOUNDARY = {
    "external_authority": "NONE",
    "clinical_validation_authorized": False,
    "production_authorized": False,
    "runtime_authority": "NONE",
    "pilot_gate_status": "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION",
}
LOCKED_EXTERNAL_GATE_SNAPSHOT = {"blocked": 7, "open": 3, "evidence_submitted": 0, "passed": 0}
EXPECTED_CHILD_DECISIONS = {
    "drift": "DRIFT_FREE",
    "manifest": "MANIFEST_VALID",
    "selection": "SELECTED_SET_VALID",
    "consistency": "SELECTION_MANIFEST_CONSISTENT",
}
HEX40 = set("0123456789abcdef")
HEX64 = set("0123456789abcdef")


class ChainDecision(StrEnum):
    INTERNAL_HANDOFF_CHAIN_BOUND = "INTERNAL_HANDOFF_CHAIN_BOUND"
    INTERNAL_HANDOFF_CHAIN_BLOCKED = "INTERNAL_HANDOFF_CHAIN_BLOCKED"


class ChainCode(StrEnum):
    FREEZE_NOT_PASS = "FREEZE_NOT_PASS"
    FREEZE_BOUNDARY_MUTATED = "FREEZE_BOUNDARY_MUTATED"
    EXTERNAL_GATE_SNAPSHOT_MUTATED = "EXTERNAL_GATE_SNAPSHOT_MUTATED"
    HANDOFF_INDEX_NOT_BOUND = "HANDOFF_INDEX_NOT_BOUND"
    HANDOFF_INDEX_ARTIFACT_INVALID = "HANDOFF_INDEX_ARTIFACT_INVALID"
    RECONCILIATION_NOT_READY = "RECONCILIATION_NOT_READY"
    RECONCILIATION_CHILD_DRIFT = "RECONCILIATION_CHILD_DRIFT"
    RECONCILIATION_ARTIFACT_INVALID = "RECONCILIATION_ARTIFACT_INVALID"
    ARTIFACT_NOT_FROZEN = "ARTIFACT_NOT_FROZEN"
    ARTIFACT_HASH_MISMATCH = "ARTIFACT_HASH_MISMATCH"
    SOURCE_REVISION_INVALID = "SOURCE_REVISION_INVALID"
    SOURCE_REVISION_NOT_ANCESTOR = "SOURCE_REVISION_NOT_ANCESTOR"
    CHAIN_READ_ONLY_INVALID = "CHAIN_READ_ONLY_INVALID"
    CHAIN_EXTERNAL_LOCK_INVALID = "CHAIN_EXTERNAL_LOCK_INVALID"
    EXPOSURE_QUARANTINED = "EXPOSURE_QUARANTINED"
    EXPOSURE_ARTIFACT_NOT_FROZEN = "EXPOSURE_ARTIFACT_NOT_FROZEN"
    EXPOSURE_ARTIFACT_HASH_MISMATCH = "EXPOSURE_ARTIFACT_HASH_MISMATCH"
    EXPOSURE_BOUNDARY_INVALID = "EXPOSURE_BOUNDARY_INVALID"


@dataclass(frozen=True, slots=True)
class ChainResult:
    decision: str
    remediation_codes: tuple[str, ...]
    checks: dict[str, bool]
    source_revision_lineage: dict[str, dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "remediation_codes": list(self.remediation_codes),
            "checks": dict(self.checks),
            "source_revision_lineage": {
                key: dict(value) for key, value in self.source_revision_lineage.items()
            },
        }


def _valid_revision(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 40 and set(value).issubset(HEX40)


def _valid_sha256(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and set(value).issubset(HEX64)


def _sha256(path: Path) -> str | None:
    try:
        return canonical_sha256(path)
    except OSError:
        return None


def _load_json(path: Path) -> dict[str, Any] | None:
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


def _add(codes: list[str], code: ChainCode) -> None:
    if code.value not in codes:
        codes.append(code.value)


def _locked_output(payload: Mapping[str, Any]) -> bool:
    return (
        payload.get("read_only") is True
        and payload.get("external_submission_allowed") is False
        and payload.get("authorization_promoted") is False
        and payload.get("runtime_mutation_performed") is False
    )


def _artifact_hash_matches(
    *,
    root: Path,
    freeze_files: Mapping[str, Mapping[str, Any]],
    relative: Path,
) -> bool:
    entry = freeze_files.get(relative.as_posix())
    if not isinstance(entry, Mapping):
        return False
    expected = entry.get("sha256")
    actual = _sha256(root / relative)
    return _valid_sha256(expected) and actual == expected


def evaluate_chain(
    *,
    root: Path,
    freeze: Mapping[str, Any],
    handoff: Mapping[str, Any],
    reconciliation: Mapping[str, Any],
    exposure: Mapping[str, Any],
) -> ChainResult:
    """Evaluate the complete internal chain without mutating any input."""
    root = root.expanduser().resolve()
    exposure = dict(exposure)
    codes: list[str] = []
    freeze_files = _freeze_files(freeze)
    checks = {
        "freeze_pass": freeze.get("freeze_status") == "PASS",
        "freeze_boundary_locked": freeze.get("authorization_boundary") == LOCKED_BOUNDARY,
        "external_gate_snapshot_locked": freeze.get("external_gate_snapshot") == LOCKED_EXTERNAL_GATE_SNAPSHOT,
        "handoff_index_bound": (
            handoff.get("decision") == "BOUND"
            and handoff.get("remediation_codes") == ["HANDOFF_INDEX_BOUND"]
            and handoff.get("index", {}).get("decision") == "BOUND"
        ),
        "handoff_index_artifact_frozen": _artifact_hash_matches(
            root=root, freeze_files=freeze_files, relative=HANDOFF_PATH
        ),
        "reconciliation_ready": reconciliation.get("decision") == "INTERNAL_HANDOFF_RECONCILIATION_READY",
        "reconciliation_remediation_empty": reconciliation.get("remediation_codes") == [],
        "reconciliation_children_locked": reconciliation.get("child_decisions") == EXPECTED_CHILD_DECISIONS,
        "reconciliation_checks_pass": (
            isinstance(reconciliation.get("checks"), Mapping)
            and bool(reconciliation.get("checks"))
            and all(value is True for value in reconciliation["checks"].values())
        ),
        "reconciliation_artifact_frozen": _artifact_hash_matches(
            root=root, freeze_files=freeze_files, relative=RECONCILIATION_PATH
        ),
        "exposure_clear": (
            exposure.get("decision") == "PUBLIC_EXPOSURE_CLEAR"
            and exposure.get("remediation_codes") == []
            and isinstance(exposure.get("checks"), Mapping)
            and bool(exposure.get("checks"))
            and all(value is True for value in exposure["checks"].values())
        ),
        "exposure_artifact_frozen": _artifact_hash_matches(
            root=root, freeze_files=freeze_files, relative=EXPOSURE_PATH
        ),
        "exposure_output_locked": _locked_output(exposure),
        "handoff_output_locked": _locked_output(handoff),
        "reconciliation_output_locked": _locked_output(reconciliation),
        "boundaries_equal": (
            handoff.get("authorization_boundary") == LOCKED_BOUNDARY
            and reconciliation.get("authorization_boundary") == LOCKED_BOUNDARY
            and exposure.get("authorization_boundary") == LOCKED_BOUNDARY
        ),
        "claim_boundaries_locked": (
            handoff.get("claim_boundary", {}).get("production_ready") is False
            and handoff.get("claim_boundary", {}).get("clinical_validation") == "PENDING"
            and reconciliation.get("claim_boundary", {}).get("production_ready") is False
            and reconciliation.get("claim_boundary", {}).get("clinical_validation") == "PENDING"
            and exposure.get("claim_boundary", {}).get("production_ready") is False
            and exposure.get("claim_boundary", {}).get("clinical_validation") == "PENDING"
        ),
        "external_gate_snapshot_equal": (
            handoff.get("index", {}).get("freeze", {}).get("external_gate_snapshot") == LOCKED_EXTERNAL_GATE_SNAPSHOT
            and reconciliation.get("external_gate_snapshot") == LOCKED_EXTERNAL_GATE_SNAPSHOT
            and exposure.get("external_gate_snapshot", LOCKED_EXTERNAL_GATE_SNAPSHOT) == LOCKED_EXTERNAL_GATE_SNAPSHOT
        ),
    }
    if not checks["freeze_pass"]:
        _add(codes, ChainCode.FREEZE_NOT_PASS)
    if not checks["freeze_boundary_locked"]:
        _add(codes, ChainCode.FREEZE_BOUNDARY_MUTATED)
    if not checks["external_gate_snapshot_locked"] or not checks["external_gate_snapshot_equal"]:
        _add(codes, ChainCode.EXTERNAL_GATE_SNAPSHOT_MUTATED)
    if not checks["handoff_index_bound"]:
        _add(codes, ChainCode.HANDOFF_INDEX_NOT_BOUND)
    if not checks["handoff_index_artifact_frozen"]:
        _add(codes, ChainCode.ARTIFACT_HASH_MISMATCH if HANDOFF_PATH.as_posix() in freeze_files else ChainCode.ARTIFACT_NOT_FROZEN)
    if not checks["reconciliation_ready"] or not checks["reconciliation_remediation_empty"]:
        _add(codes, ChainCode.RECONCILIATION_NOT_READY)
    if not checks["reconciliation_children_locked"] or not checks["reconciliation_checks_pass"]:
        _add(codes, ChainCode.RECONCILIATION_CHILD_DRIFT)
    if not checks["reconciliation_artifact_frozen"]:
        _add(codes, ChainCode.ARTIFACT_HASH_MISMATCH if RECONCILIATION_PATH.as_posix() in freeze_files else ChainCode.ARTIFACT_NOT_FROZEN)
    if not checks["exposure_clear"]:
        _add(codes, ChainCode.EXPOSURE_QUARANTINED)
    if not checks["exposure_artifact_frozen"]:
        _add(codes, ChainCode.EXPOSURE_ARTIFACT_HASH_MISMATCH if EXPOSURE_PATH.as_posix() in freeze_files else ChainCode.EXPOSURE_ARTIFACT_NOT_FROZEN)
    if not checks["exposure_output_locked"] or not checks["handoff_output_locked"] or not checks["reconciliation_output_locked"] or not checks["boundaries_equal"]:
        _add(codes, ChainCode.CHAIN_EXTERNAL_LOCK_INVALID)
    if not checks["claim_boundaries_locked"]:
        _add(codes, ChainCode.CHAIN_READ_ONLY_INVALID)
    if not checks["external_gate_snapshot_equal"]:
        _add(codes, ChainCode.EXTERNAL_GATE_SNAPSHOT_MUTATED)

    freeze_source = freeze.get("source_revision")
    source_lineage: dict[str, dict[str, Any]] = {}
    for label, revision in (
        ("freeze", freeze_source),
        ("handoff", handoff.get("source_revision")),
        ("handoff_index", handoff.get("index", {}).get("freeze", {}).get("source_revision")),
        ("reconciliation", reconciliation.get("freeze_source_revision")),
        ("exposure", exposure.get("freeze_source_revision")),
    ):
        valid = _valid_revision(revision)
        ancestor = valid and _valid_revision(freeze_source) and revision_is_ancestor(root, revision, freeze_source)
        relation = "INVALID" if not valid else ("MATCH" if revision == freeze_source else ("ANCESTOR" if ancestor else "NON_ANCESTOR"))
        source_lineage[label] = {
            "revision": revision,
            "valid": valid,
            "ancestor_verified": bool(ancestor),
            "relation": relation,
        }
        if not valid:
            _add(codes, ChainCode.SOURCE_REVISION_INVALID)
        elif not ancestor:
            _add(codes, ChainCode.SOURCE_REVISION_NOT_ANCESTOR)

    decision = ChainDecision.INTERNAL_HANDOFF_CHAIN_BOUND.value if not codes else ChainDecision.INTERNAL_HANDOFF_CHAIN_BLOCKED.value
    return ChainResult(
        decision=decision,
        remediation_codes=tuple(codes),
        checks=checks,
        source_revision_lineage=source_lineage,
    )


def check_repository(root: Path = ROOT) -> dict[str, Any]:
    """Load the three chain artifacts and return a redacted, read-only decision."""
    root = root.expanduser().resolve()
    freeze = _load_json(root / FREEZE_PATH) or {}
    handoff = _load_json(root / HANDOFF_PATH) or {}
    reconciliation = _load_json(root / RECONCILIATION_PATH) or {}
    exposure = _load_json(root / EXPOSURE_PATH) or {}
    result = evaluate_chain(root=root, freeze=freeze, handoff=handoff, reconciliation=reconciliation, exposure=exposure)
    return {
        "evidence_type": "INTERNAL_HANDOFF_CHAIN_INTEGRITY",
        "schema_version": "smart-ward-internal-handoff-chain-v1",
        "decision": result.decision,
        "remediation_codes": list(result.remediation_codes),
        "checks": result.checks,
        "source_revision_lineage": result.source_revision_lineage,
        "exposure_decision": exposure.get("decision"),
        "exposure_remediation_codes": exposure.get("remediation_codes"),
        "freeze_source_revision": freeze.get("source_revision"),
        "origin_main_revision": freeze.get("origin_main_revision"),
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
    print(
        "INTERNAL_HANDOFF_CHAIN_BOUND"
        if report["decision"] == ChainDecision.INTERNAL_HANDOFF_CHAIN_BOUND.value
        else "INTERNAL_HANDOFF_CHAIN_BLOCKED"
    )
