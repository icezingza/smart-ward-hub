"""Read-only pre-handoff readiness check for internal Smart Ward Hub review.

This check is deliberately scoped to internal evidence handoff. It does not
submit evidence, grant authority, mutate runtime state, or imply production or
clinical readiness.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import json
from pathlib import Path
from typing import Any, Mapping

from consolidated_internal_handoff_index import LOCKED_BOUNDARY, LOCKED_EXTERNAL_GATE_SNAPSHOT, build_index
from freeze_integrity_monitor import check_repository


ROOT = Path(__file__).resolve().parent


class HandoffDecision(StrEnum):
    INTERNAL_HANDOFF_READY = "INTERNAL_HANDOFF_READY"
    INTERNAL_HANDOFF_BLOCKED = "INTERNAL_HANDOFF_BLOCKED"


class HandoffCode(StrEnum):
    FREEZE_DRIFT_DETECTED = "FREEZE_DRIFT_DETECTED"
    HANDOFF_INDEX_NOT_BOUND = "HANDOFF_INDEX_NOT_BOUND"
    CLAIM_BOUNDARY_MUTATED = "CLAIM_BOUNDARY_MUTATED"
    AUTHORIZATION_BOUNDARY_MUTATED = "AUTHORIZATION_BOUNDARY_MUTATED"
    EXTERNAL_GATE_SNAPSHOT_MUTATED = "EXTERNAL_GATE_SNAPSHOT_MUTATED"
    EXTERNAL_SUBMISSION_FORBIDDEN = "EXTERNAL_SUBMISSION_FORBIDDEN"
    RUNTIME_MUTATION_DETECTED = "RUNTIME_MUTATION_DETECTED"
    READ_ONLY_CONTRACT_INVALID = "READ_ONLY_CONTRACT_INVALID"


@dataclass(frozen=True, slots=True)
class PreHandoffResult:
    decision: str
    remediation_codes: tuple[str, ...]
    checks: dict[str, bool]
    drift: dict[str, Any]
    handoff: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "remediation_codes": list(self.remediation_codes),
            "checks": dict(self.checks),
            "drift": dict(self.drift),
            "handoff": dict(self.handoff),
        }


def _add(codes: list[str], code: HandoffCode) -> None:
    if code.value not in codes:
        codes.append(code.value)


def evaluate_pre_handoff(
    *,
    drift: Mapping[str, Any],
    handoff: Mapping[str, Any],
    authorization_boundary: Mapping[str, Any] | None = None,
    claim_boundary: Mapping[str, Any] | None = None,
    external_gate_snapshot: Mapping[str, Any] | None = None,
) -> PreHandoffResult:
    """Evaluate internal handoff eligibility and fail closed on any mismatch."""
    codes: list[str] = []
    authorization_boundary = authorization_boundary or handoff.get("authorization_boundary", {})
    claim_boundary = claim_boundary or handoff.get("claim_boundary", {})
    external_gate_snapshot = external_gate_snapshot or handoff.get("freeze", {}).get("external_gate_snapshot", {})

    checks = {
        "freeze_drift_free": (
            (drift.get("decision") == "DRIFT_FREE" and drift.get("remediation_codes") == ["DRIFT_FREE"])
            or (
                set(drift.get("remediation_codes", [])) <= {"DRIFT_FREE", "HEAD_NOT_ALIGNED_TO_FREEZE"}
                and drift.get("checks", {}).get("freeze_file_hashes_match") is True
                and drift.get("checks", {}).get("tracked_set_matches_freeze") is True
                and drift.get("checks", {}).get("runtime_artifacts_absent") is True
            )
        ),
        "handoff_index_bound": handoff.get("decision") == "BOUND" and handoff.get("remediation_codes") == ["HANDOFF_INDEX_BOUND"],
        "authorization_boundary_locked": dict(authorization_boundary) == LOCKED_BOUNDARY,
        "claim_boundary_locked": (
            claim_boundary.get("status") == "CONTROLLED_PRODUCTION_PROTOTYPE"
            and claim_boundary.get("production_ready") is False
            and claim_boundary.get("clinical_validation") == "PENDING"
        ),
        "external_gate_snapshot_preserved": dict(external_gate_snapshot) == LOCKED_EXTERNAL_GATE_SNAPSHOT,
        "external_submission_disabled": handoff.get("external_submission_allowed") is False,
        "runtime_mutation_absent": handoff.get("runtime_mutation_performed") is False,
        "read_only": handoff.get("read_only") is True and drift.get("read_only") is True,
        "external_transmission_absent": drift.get("external_transmission_performed") is False,
    }
    if not checks["freeze_drift_free"]:
        _add(codes, HandoffCode.FREEZE_DRIFT_DETECTED)
    if not checks["handoff_index_bound"]:
        _add(codes, HandoffCode.HANDOFF_INDEX_NOT_BOUND)
    if not checks["authorization_boundary_locked"]:
        _add(codes, HandoffCode.AUTHORIZATION_BOUNDARY_MUTATED)
    if not checks["claim_boundary_locked"]:
        _add(codes, HandoffCode.CLAIM_BOUNDARY_MUTATED)
    if not checks["external_gate_snapshot_preserved"]:
        _add(codes, HandoffCode.EXTERNAL_GATE_SNAPSHOT_MUTATED)
    if not checks["external_submission_disabled"]:
        _add(codes, HandoffCode.EXTERNAL_SUBMISSION_FORBIDDEN)
    if not checks["runtime_mutation_absent"]:
        _add(codes, HandoffCode.RUNTIME_MUTATION_DETECTED)
    if not checks["read_only"] or not checks["external_transmission_absent"]:
        _add(codes, HandoffCode.READ_ONLY_CONTRACT_INVALID)

    decision = (
        HandoffDecision.INTERNAL_HANDOFF_READY.value
        if not codes
        else HandoffDecision.INTERNAL_HANDOFF_BLOCKED.value
    )
    return PreHandoffResult(
        decision=decision,
        remediation_codes=tuple(codes),
        checks=checks,
        drift=dict(drift),
        handoff=dict(handoff),
    )


def check_pre_handoff(root: Path = ROOT) -> dict[str, Any]:
    """Run local read-only checks and return a redacted readiness record."""
    drift = check_repository(root)
    handoff_result = build_index(root)
    handoff = handoff_result.index
    result = evaluate_pre_handoff(
        drift=drift,
        handoff=handoff,
        authorization_boundary=handoff.get("authorization_boundary"),
        claim_boundary=handoff.get("claim_boundary"),
        external_gate_snapshot=handoff.get("freeze", {}).get("external_gate_snapshot"),
    )
    return {
        "evidence_type": "PRE_HANDOFF_READINESS_CHECK",
        "schema_version": "smart-ward-pre-handoff-v1",
        "decision": result.decision,
        "remediation_codes": list(result.remediation_codes),
        "checks": result.checks,
        "drift_decision": drift.get("decision"),
        "handoff_index_decision": handoff.get("decision"),
        "freeze_source_revision": handoff.get("freeze", {}).get("source_revision"),
        "origin_main_revision": handoff.get("freeze", {}).get("origin_main_revision"),
        "external_gate_snapshot": handoff.get("freeze", {}).get("external_gate_snapshot"),
        "claim_boundary": handoff.get("claim_boundary"),
        "authorization_boundary": LOCKED_BOUNDARY,
        "read_only": True,
        "external_submission_allowed": False,
        "authorization_promoted": False,
        "runtime_mutation_performed": False,
        "external_transmission_performed": False,
    }


if __name__ == "__main__":
    report = check_pre_handoff()
    print(json.dumps(report, sort_keys=True, indent=2))
    print("PRE_HANDOFF_READY" if report["decision"] == HandoffDecision.INTERNAL_HANDOFF_READY.value else "PRE_HANDOFF_BLOCKED")
