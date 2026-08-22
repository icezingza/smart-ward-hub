"""Fail-closed governance check for the repository visibility boundary.

This module consumes a checked-in observation only. It never calls GitHub,
changes repository settings, or infers authorization from visibility alone.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import json
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parent
OBSERVATION_PATH = Path("evals/micro_rag/evidence/repository-visibility-observation-local.json")
EXPECTED_REPOSITORY = "icezingza/smart-ward-hub"
EXPECTED_DEFAULT_BRANCH = "main"
LOCKED_BOUNDARY = {
    "external_authority": "NONE",
    "clinical_validation_authorized": False,
    "production_authorized": False,
    "runtime_authority": "NONE",
    "pilot_gate_status": "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION",
}


class VisibilityDecision(StrEnum):
    PRIVATE_REPOSITORY_CONFIRMED = "PRIVATE_REPOSITORY_CONFIRMED"
    REPOSITORY_VISIBILITY_BLOCKED = "REPOSITORY_VISIBILITY_BLOCKED"


class VisibilityCode(StrEnum):
    OBSERVATION_MISSING = "OBSERVATION_MISSING"
    REPOSITORY_IDENTITY_MISMATCH = "REPOSITORY_IDENTITY_MISMATCH"
    REPOSITORY_NOT_PRIVATE = "REPOSITORY_NOT_PRIVATE"
    DEFAULT_BRANCH_MISMATCH = "DEFAULT_BRANCH_MISMATCH"
    OBSERVATION_SOURCE_INVALID = "OBSERVATION_SOURCE_INVALID"
    AUTHORIZATION_BOUNDARY_MUTATED = "AUTHORIZATION_BOUNDARY_MUTATED"
    EXECUTION_BOUNDARY_MUTATED = "EXECUTION_BOUNDARY_MUTATED"


@dataclass(frozen=True, slots=True)
class VisibilityResult:
    decision: str
    remediation_codes: tuple[str, ...]
    checks: dict[str, bool]
    observation: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "remediation_codes": list(self.remediation_codes),
            "checks": dict(self.checks),
            "observation": dict(self.observation),
        }


def _add(codes: list[str], code: VisibilityCode) -> None:
    if code.value not in codes:
        codes.append(code.value)


def evaluate_visibility(observation: Mapping[str, Any] | None) -> VisibilityResult:
    """Evaluate an external observation without mutating it or changing settings."""
    payload = dict(observation or {})
    codes: list[str] = []
    checks = {
        "observation_present": bool(payload),
        "repository_identity_matches": payload.get("repository") == EXPECTED_REPOSITORY,
        "repository_private": payload.get("is_private") is True,
        "default_branch_matches": payload.get("default_branch") == EXPECTED_DEFAULT_BRANCH,
        "observation_source_allowed": payload.get("source") in {"GH_REPO_VIEW", "OPERATOR_CONFIRMED"},
        "authorization_boundary_locked": payload.get("authorization_boundary") == LOCKED_BOUNDARY,
        "execution_boundary_locked": (
            payload.get("external_submission_allowed") is False
            and payload.get("authorization_promoted") is False
            and payload.get("runtime_mutation_performed") is False
            and payload.get("external_transmission_performed") is False
        ),
    }
    if not checks["observation_present"]:
        _add(codes, VisibilityCode.OBSERVATION_MISSING)
    if not checks["repository_identity_matches"]:
        _add(codes, VisibilityCode.REPOSITORY_IDENTITY_MISMATCH)
    if not checks["repository_private"]:
        _add(codes, VisibilityCode.REPOSITORY_NOT_PRIVATE)
    if not checks["default_branch_matches"]:
        _add(codes, VisibilityCode.DEFAULT_BRANCH_MISMATCH)
    if not checks["observation_source_allowed"]:
        _add(codes, VisibilityCode.OBSERVATION_SOURCE_INVALID)
    if not checks["authorization_boundary_locked"]:
        _add(codes, VisibilityCode.AUTHORIZATION_BOUNDARY_MUTATED)
    if not checks["execution_boundary_locked"]:
        _add(codes, VisibilityCode.EXECUTION_BOUNDARY_MUTATED)
    decision = (
        VisibilityDecision.PRIVATE_REPOSITORY_CONFIRMED.value
        if not codes
        else VisibilityDecision.REPOSITORY_VISIBILITY_BLOCKED.value
    )
    return VisibilityResult(decision=decision, remediation_codes=tuple(codes), checks=checks, observation=payload)


def _load_observation(root: Path) -> dict[str, Any] | None:
    try:
        value = json.loads((root / OBSERVATION_PATH).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def check_repository(root: Path = ROOT) -> dict[str, Any]:
    """Return a redacted local visibility decision; never changes remote settings."""
    result = evaluate_visibility(_load_observation(root.expanduser().resolve()))
    return {
        "evidence_type": "REPOSITORY_VISIBILITY_GOVERNANCE",
        "schema_version": "smart-ward-repository-visibility-v1",
        "decision": result.decision,
        "remediation_codes": list(result.remediation_codes),
        "checks": result.checks,
        "repository": result.observation.get("repository"),
        "is_private": result.observation.get("is_private"),
        "default_branch": result.observation.get("default_branch"),
        "observation_source": result.observation.get("source"),
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
        "PRIVATE_REPOSITORY_CONFIRMED"
        if report["decision"] == VisibilityDecision.PRIVATE_REPOSITORY_CONFIRMED.value
        else "REPOSITORY_VISIBILITY_BLOCKED"
    )
