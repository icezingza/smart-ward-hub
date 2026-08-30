"""Fail-closed public-exposure quarantine audit for the repository.

The audit consumes the local release-freeze manifest and visibility observation.
It does not contact GitHub, submit evidence, or change repository settings.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping

from canonical_file_hash import canonicalize_bytes
from repository_visibility_governance import (
    EXPECTED_REPOSITORY,
    LOCKED_BOUNDARY,
    OBSERVATION_PATH,
    VisibilityDecision,
    evaluate_visibility,
)


ROOT = Path(__file__).resolve().parent
FREEZE_PATH = Path("evals/micro_rag/evidence/release-candidate-freeze-20260820.json")
SECRET_PATTERNS = (
    ("PRIVATE_KEY_MARKER", re.compile(rb"BEGIN (?:RSA|EC|OPENSSH|PRIVATE) KEY")),
    ("AWS_ACCESS_KEY_MARKER", re.compile(rb"AKIA[0-9A-Z]{16}")),
    ("GITHUB_TOKEN_MARKER", re.compile(rb"ghp_[A-Za-z0-9]{20,}")),
    ("GITHUB_PAT_MARKER", re.compile(rb"github_pat_[A-Za-z0-9_]{20,}")),
    ("OPENAI_KEY_MARKER", re.compile(rb"sk-[A-Za-z0-9]{20,}")),
)
IDENTIFIER_PATTERNS = (
    ("RAW_HN_PATTERN", re.compile(rb"\bHN-[0-9]{4}-[0-9]{3,}\b")),
    ("RAW_AN_PATTERN", re.compile(rb"\bAN-[0-9]{4}-[0-9]{3,}\b")),
)
SYNTHETIC_IDENTIFIER_PATH_PREFIXES = (
    "test_",
    "simulate_",
    "presentation_deck/",
    "p1_presentation_deck/",
    "gv10_presentation_deck/",
    "controlled_pilot_presentation_deck/",
    "wave1_presentation_deck/",
)


class ExposureDecision(StrEnum):
    PUBLIC_EXPOSURE_QUARANTINED = "PUBLIC_EXPOSURE_QUARANTINED"
    PUBLIC_EXPOSURE_CLEAR = "PUBLIC_EXPOSURE_CLEAR"


class ExposureCode(StrEnum):
    FREEZE_MANIFEST_MISSING = "FREEZE_MANIFEST_MISSING"
    FREEZE_NOT_PASS = "FREEZE_NOT_PASS"
    FREEZE_FILE_UNREADABLE = "FREEZE_FILE_UNREADABLE"
    FREEZE_HASH_MISMATCH = "FREEZE_HASH_MISMATCH"
    SECRET_MARKER_FOUND = "SECRET_MARKER_FOUND"
    IDENTIFIER_PATTERN_FOUND = "IDENTIFIER_PATTERN_FOUND"
    PUBLIC_REPOSITORY_EXPOSURE_QUARANTINED = "PUBLIC_REPOSITORY_EXPOSURE_QUARANTINED"
    VISIBILITY_OBSERVATION_INVALID = "VISIBILITY_OBSERVATION_INVALID"
    AUTHORIZATION_BOUNDARY_MUTATED = "AUTHORIZATION_BOUNDARY_MUTATED"
    EXECUTION_BOUNDARY_MUTATED = "EXECUTION_BOUNDARY_MUTATED"


@dataclass(frozen=True, slots=True)
class ExposureResult:
    decision: str
    remediation_codes: tuple[str, ...]
    checks: dict[str, bool]
    findings: tuple[dict[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "remediation_codes": list(self.remediation_codes),
            "checks": dict(self.checks),
            "findings": [dict(item) for item in self.findings],
        }


def _add(codes: list[str], code: ExposureCode) -> None:
    if code.value not in codes:
        codes.append(code.value)


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _freeze_entries(freeze: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    files = freeze.get("files")
    if not isinstance(files, list):
        return []
    return [entry for entry in files if isinstance(entry, Mapping) and isinstance(entry.get("path"), str)]


def _match_labels(raw: bytes, patterns: tuple[tuple[str, re.Pattern[bytes]], ...]) -> tuple[str, ...]:
    return tuple(label for label, pattern in patterns if pattern.search(raw))


def _is_synthetic_identifier_path(relative: str) -> bool:
    return relative.startswith(SYNTHETIC_IDENTIFIER_PATH_PREFIXES)


def evaluate_exposure(
    *,
    freeze: Mapping[str, Any] | None,
    visibility: Mapping[str, Any] | None,
    files: Mapping[str, bytes | None],
) -> ExposureResult:
    """Scan frozen file bytes and fail closed on exposure or boundary uncertainty."""
    freeze = dict(freeze or {})
    visibility = dict(visibility or {})
    codes: list[str] = []
    findings: list[dict[str, Any]] = []
    entries = _freeze_entries(freeze)
    checks = {
        "freeze_manifest_present": bool(freeze),
        "freeze_pass": freeze.get("freeze_status") == "PASS",
        "frozen_files_readable": True,
        "frozen_hashes_match": True,
        "secret_markers_absent": True,
        "identifier_patterns_absent": True,
        "synthetic_identifier_fixtures_classified": True,
        "private_repository_confirmed": visibility.get("decision") == VisibilityDecision.PRIVATE_REPOSITORY_CONFIRMED,
        "visibility_observation_valid": visibility.get("repository") == EXPECTED_REPOSITORY
        and visibility.get("observation_source") in {"GH_REPO_VIEW", "OPERATOR_CONFIRMED"},
        "authorization_boundary_locked": visibility.get("authorization_boundary") == LOCKED_BOUNDARY,
        "execution_boundary_locked": visibility.get("external_submission_allowed") is False
        and visibility.get("authorization_promoted") is False
        and visibility.get("runtime_mutation_performed") is False
        and visibility.get("external_transmission_performed") is False,
    }
    if not checks["freeze_manifest_present"]:
        _add(codes, ExposureCode.FREEZE_MANIFEST_MISSING)
    if not checks["freeze_pass"]:
        _add(codes, ExposureCode.FREEZE_NOT_PASS)
    if not checks["private_repository_confirmed"]:
        _add(codes, ExposureCode.PUBLIC_REPOSITORY_EXPOSURE_QUARANTINED)
    if not checks["visibility_observation_valid"]:
        _add(codes, ExposureCode.VISIBILITY_OBSERVATION_INVALID)
    if not checks["authorization_boundary_locked"]:
        _add(codes, ExposureCode.AUTHORIZATION_BOUNDARY_MUTATED)
    if not checks["execution_boundary_locked"]:
        _add(codes, ExposureCode.EXECUTION_BOUNDARY_MUTATED)

    for entry in entries:
        relative = entry["path"]
        raw = files.get(relative)
        if raw is None:
            checks["frozen_files_readable"] = False
            _add(codes, ExposureCode.FREEZE_FILE_UNREADABLE)
            findings.append({"path": relative, "kind": "UNREADABLE"})
            continue
        digest = hashlib.sha256(canonicalize_bytes(Path(relative), raw)).hexdigest()
        if entry.get("sha256") != digest:
            checks["frozen_hashes_match"] = False
            _add(codes, ExposureCode.FREEZE_HASH_MISMATCH)
            findings.append({"path": relative, "kind": "HASH_MISMATCH"})
        secret_labels = _match_labels(raw, SECRET_PATTERNS)
        if secret_labels:
            checks["secret_markers_absent"] = False
            _add(codes, ExposureCode.SECRET_MARKER_FOUND)
            findings.append({"path": relative, "kind": "SECRET_MARKER", "markers": list(secret_labels)})
        identifier_labels = _match_labels(raw, IDENTIFIER_PATTERNS)
        if identifier_labels:
            if _is_synthetic_identifier_path(relative):
                findings.append(
                    {
                        "path": relative,
                        "kind": "SYNTHETIC_IDENTIFIER_FIXTURE",
                        "markers": list(identifier_labels),
                    }
                )
            else:
                checks["identifier_patterns_absent"] = False
                checks["synthetic_identifier_fixtures_classified"] = False
                _add(codes, ExposureCode.IDENTIFIER_PATTERN_FOUND)
                findings.append({"path": relative, "kind": "IDENTIFIER_PATTERN", "markers": list(identifier_labels)})

    decision = ExposureDecision.PUBLIC_EXPOSURE_CLEAR.value if not codes else ExposureDecision.PUBLIC_EXPOSURE_QUARANTINED.value
    return ExposureResult(
        decision=decision,
        remediation_codes=tuple(codes),
        checks=checks,
        findings=tuple(findings),
    )


def check_repository(root: Path = ROOT) -> dict[str, Any]:
    """Scan freeze-listed bytes and return a redacted local quarantine decision."""
    root = root.expanduser().resolve()
    freeze = _load_json(root / FREEZE_PATH)
    visibility = _load_json(root / OBSERVATION_PATH)
    visibility_result = evaluate_visibility(visibility)
    visibility_report = {
        "decision": visibility_result.decision,
        "repository": visibility_result.observation.get("repository"),
        "observation_source": visibility_result.observation.get("source"),
        "authorization_boundary": visibility_result.observation.get("authorization_boundary"),
        "external_submission_allowed": visibility_result.observation.get("external_submission_allowed"),
        "authorization_promoted": visibility_result.observation.get("authorization_promoted"),
        "runtime_mutation_performed": visibility_result.observation.get("runtime_mutation_performed"),
        "external_transmission_performed": visibility_result.observation.get("external_transmission_performed"),
    }
    files: dict[str, bytes | None] = {}
    for entry in _freeze_entries(freeze or {}):
        relative = entry["path"]
        try:
            files[relative] = (root / relative).read_bytes()
        except OSError:
            files[relative] = None
    result = evaluate_exposure(freeze=freeze, visibility=visibility_report, files=files)
    return {
        "evidence_type": "PUBLIC_EXPOSURE_QUARANTINE",
        "schema_version": "smart-ward-public-exposure-quarantine-v1",
        "decision": result.decision,
        "remediation_codes": list(result.remediation_codes),
        "checks": result.checks,
        "finding_count": len(result.findings),
        "findings": list(result.findings),
        "freeze_source_revision": (freeze or {}).get("source_revision"),
        "origin_main_revision": (freeze or {}).get("origin_main_revision"),
        "visibility_decision": visibility_report["decision"],
        "repository": visibility_report["repository"],
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
        "PUBLIC_EXPOSURE_CLEAR"
        if report["decision"] == ExposureDecision.PUBLIC_EXPOSURE_CLEAR.value
        else "PUBLIC_EXPOSURE_QUARANTINED"
    )
