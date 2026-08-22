"""Aggregate, read-only pre-handoff reconciliation gate."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import json
from pathlib import Path
from typing import Any, Mapping

from freeze_integrity_monitor import check_repository as check_drift
from pre_handoff_evidence_selection import select_repository
from pre_handoff_manifest_validator import validate_repository as validate_manifest
from pre_handoff_selection_manifest_consistency import check_repository as check_consistency


ROOT = Path(__file__).resolve().parent


class ReconciliationDecision(StrEnum):
    INTERNAL_HANDOFF_RECONCILIATION_READY = "INTERNAL_HANDOFF_RECONCILIATION_READY"
    INTERNAL_HANDOFF_RECONCILIATION_BLOCKED = "INTERNAL_HANDOFF_RECONCILIATION_BLOCKED"


class ReconciliationCode(StrEnum):
    DRIFT_GATE_FAILED = "DRIFT_GATE_FAILED"
    MANIFEST_GATE_FAILED = "MANIFEST_GATE_FAILED"
    SELECTION_GATE_FAILED = "SELECTION_GATE_FAILED"
    CONSISTENCY_GATE_FAILED = "CONSISTENCY_GATE_FAILED"
    AUTHORIZATION_BOUNDARY_MUTATED = "AUTHORIZATION_BOUNDARY_MUTATED"
    EXTERNAL_SUBMISSION_ENABLED = "EXTERNAL_SUBMISSION_ENABLED"
    RUNTIME_MUTATION_DETECTED = "RUNTIME_MUTATION_DETECTED"
    EXTERNAL_TRANSMISSION_DETECTED = "EXTERNAL_TRANSMISSION_DETECTED"
    AGGREGATE_READ_ONLY_INVALID = "AGGREGATE_READ_ONLY_INVALID"


@dataclass(frozen=True, slots=True)
class ReconciliationResult:
    decision: str
    remediation_codes: tuple[str, ...]
    checks: dict[str, bool]
    drift: dict[str, Any]
    manifest: dict[str, Any]
    selection: dict[str, Any]
    consistency: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "remediation_codes": list(self.remediation_codes),
            "checks": dict(self.checks),
            "drift": dict(self.drift),
            "manifest": dict(self.manifest),
            "selection": dict(self.selection),
            "consistency": dict(self.consistency),
        }


def _add(codes: list[str], code: ReconciliationCode) -> None:
    if code.value not in codes:
        codes.append(code.value)


def _child_passed(
    payload: Mapping[str, Any],
    *,
    decision: str,
) -> bool:
    return (
        payload.get("decision") == decision
        and payload.get("remediation_codes") == []
        and all(value is True for value in payload.get("checks", {}).values())
    )


def evaluate_reconciliation(
    *,
    drift: Mapping[str, Any],
    manifest: Mapping[str, Any],
    selection: Mapping[str, Any],
    consistency: Mapping[str, Any],
) -> ReconciliationResult:
    """Aggregate child gates; never turns a blocked child into a pass."""
    drift = dict(drift)
    manifest = dict(manifest)
    selection = dict(selection)
    consistency = dict(consistency)
    codes: list[str] = []
    checks = {
        "drift_gate_passed": _child_passed(drift, decision="DRIFT_FREE"),
        "manifest_gate_passed": _child_passed(manifest, decision="MANIFEST_VALID"),
        "selection_gate_passed": _child_passed(selection, decision="SELECTED_SET_VALID"),
        "consistency_gate_passed": _child_passed(consistency, decision="SELECTION_MANIFEST_CONSISTENT"),
        "authorization_boundary_locked": all(
            payload.get("authorization_boundary", {}).get("production_authorized") is False
            and payload.get("authorization_boundary", {}).get("clinical_validation_authorized") is False
            and payload.get("authorization_boundary", {}).get("external_authority") == "NONE"
            and payload.get("authorization_boundary", {}).get("runtime_authority") == "NONE"
            for payload in (manifest, selection, consistency)
        ),
        "external_submission_disabled": all(
            payload.get("external_submission_allowed") is False
            for payload in (manifest, selection, consistency)
        ),
        "runtime_mutation_absent": all(
            payload.get("runtime_mutation_performed") is False
            for payload in (manifest, selection, consistency)
        ),
        "external_transmission_absent": all(
            payload.get("external_transmission_performed") is False
            for payload in (manifest, selection, consistency)
        ),
        "read_only": all(
            payload.get("read_only") is True
            for payload in (drift, manifest, selection, consistency)
        ),
    }
    if not checks["drift_gate_passed"]:
        _add(codes, ReconciliationCode.DRIFT_GATE_FAILED)
    if not checks["manifest_gate_passed"]:
        _add(codes, ReconciliationCode.MANIFEST_GATE_FAILED)
    if not checks["selection_gate_passed"]:
        _add(codes, ReconciliationCode.SELECTION_GATE_FAILED)
    if not checks["consistency_gate_passed"]:
        _add(codes, ReconciliationCode.CONSISTENCY_GATE_FAILED)
    if not checks["authorization_boundary_locked"]:
        _add(codes, ReconciliationCode.AUTHORIZATION_BOUNDARY_MUTATED)
    if not checks["external_submission_disabled"]:
        _add(codes, ReconciliationCode.EXTERNAL_SUBMISSION_ENABLED)
    if not checks["runtime_mutation_absent"]:
        _add(codes, ReconciliationCode.RUNTIME_MUTATION_DETECTED)
    if not checks["external_transmission_absent"]:
        _add(codes, ReconciliationCode.EXTERNAL_TRANSMISSION_DETECTED)
    if not checks["read_only"]:
        _add(codes, ReconciliationCode.AGGREGATE_READ_ONLY_INVALID)

    decision = (
        ReconciliationDecision.INTERNAL_HANDOFF_RECONCILIATION_READY.value
        if not codes
        else ReconciliationDecision.INTERNAL_HANDOFF_RECONCILIATION_BLOCKED.value
    )
    return ReconciliationResult(
        decision=decision,
        remediation_codes=tuple(codes),
        checks=checks,
        drift=drift,
        manifest=manifest,
        selection=selection,
        consistency=consistency,
    )


def check_repository(root: Path = ROOT) -> dict[str, Any]:
    drift = check_drift(root)
    manifest = validate_manifest(root)
    selection = select_repository(root)
    consistency = check_consistency(root)
    result = evaluate_reconciliation(
        drift=drift,
        manifest=manifest,
        selection=selection,
        consistency=consistency,
    )
    return {
        "evidence_type": "PRE_HANDOFF_RECONCILIATION_GATE",
        "schema_version": "smart-ward-pre-handoff-reconciliation-v1",
        "decision": result.decision,
        "remediation_codes": list(result.remediation_codes),
        "checks": result.checks,
        "child_decisions": {
            "drift": drift.get("decision"),
            "manifest": manifest.get("decision"),
            "selection": selection.get("decision"),
            "consistency": consistency.get("decision"),
        },
        "freeze_source_revision": consistency.get("freeze_source_revision"),
        "origin_main_revision": consistency.get("origin_main_revision"),
        "selected_count": consistency.get("selected_count"),
        "external_gate_snapshot": consistency.get("external_gate_snapshot"),
        "claim_boundary": consistency.get("claim_boundary"),
        "authorization_boundary": consistency.get("authorization_boundary"),
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
        "PRE_HANDOFF_RECONCILIATION_READY"
        if report["decision"] == ReconciliationDecision.INTERNAL_HANDOFF_RECONCILIATION_READY.value
        else "PRE_HANDOFF_RECONCILIATION_BLOCKED"
    )
