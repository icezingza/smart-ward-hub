"""Local-only sufficiency and provenance gate for Micro-RAG evaluation evidence."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parent
AGGREGATE_PATH = Path("evals/micro_rag/evidence/gemini-3-flash-v2-repeated-aggregate-20260820.json")
FREEZE_PATH = Path("evals/micro_rag/evidence/release-candidate-freeze-20260820.json")
EXPECTED_RETRIEVAL_SOURCE = "document-registry-v2/rebuildable-index-v2"
EXPECTED_CASES_PER_SAMPLE = 8
EXPECTED_SUFFICIENT_STATUS = "REPEATED_EVALUATED_WITH_ADAPTER"
EXPECTED_AGGREGATE_SUITE = "micro-rag-repeated-sample-aggregation-v1"
EXPECTED_FREEZE_GATE = {"blocked": 7, "evidence_submitted": 0, "open": 3, "passed": 0}
EXPECTED_BOUNDARY = {
    "external_authority": "NONE",
    "clinical_validation_authorized": False,
    "production_authorized": False,
    "runtime_authority": "NONE",
    "pilot_gate_status": "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION",
}
HEX40 = "0123456789abcdef"
HEX64 = "0123456789abcdef"
REQUIRED_AGGREGATE_FIELDS = {
    "suite",
    "sample_count",
    "min_samples",
    "total_case_results",
    "accepted_cases",
    "quality_denominator",
    "quality_pass_rate",
    "provider_limited_cases",
    "runtime_or_adapter_failures",
    "quality_rejections",
    "model_id",
    "model_revision",
    "corpus_revision",
    "adapter_version",
    "retrieval_source",
    "registry_manifest_hash",
    "index_hash",
    "index_version",
    "status",
    "clinical_validity",
    "runtime_authority",
}
FORBIDDEN_MARKERS = (
    "HN-",
    "AN-",
    "MRN",
    "patient_id",
    "patient_token",
    "patient_name",
    "private key",
    "bearer ",
    "password",
    "api_key",
)


class EvidenceSufficiencyError(ValueError):
    """Raised for unreadable or structurally invalid evidence inputs."""


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EvidenceSufficiencyError(f"evidence_json_unreadable:{path}") from exc
    if not isinstance(value, dict):
        raise EvidenceSufficiencyError("evidence_json_object_required")
    return value


def _is_hex(value: Any, length: int) -> bool:
    return isinstance(value, str) and len(value) == length and all(char in HEX40 for char in value.lower())


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _freeze_entry(freeze: Mapping[str, Any], path: str) -> Mapping[str, Any] | None:
    entries = freeze.get("files")
    if not isinstance(entries, list):
        return None
    for entry in entries:
        if isinstance(entry, dict) and entry.get("path") == path:
            return entry
    return None


def _freeze_passes(freeze: Mapping[str, Any]) -> bool:
    checks = freeze.get("checks")
    source = freeze.get("source_revision")
    origin = freeze.get("origin_main_revision")
    gate = freeze.get("external_gate_snapshot")
    return (
        isinstance(checks, dict)
        and all(checks.get(key) is True for key in (
            "head_matches_origin_main",
            "runtime_artifact_scan_pass",
            "secret_marker_scan_pass",
            "tracked_file_hashes_generated",
            "working_tree_clean_before_manifest",
        ))
        and _is_hex(source, 40)
        and (source == origin or checks.get("head_matches_origin_main") is True)
        and gate == EXPECTED_FREEZE_GATE

        and freeze.get("authorization_boundary") == EXPECTED_BOUNDARY
    )


def _expected_status(aggregate: Mapping[str, Any]) -> str | None:
    sample_count = aggregate.get("sample_count")
    minimum = aggregate.get("min_samples")
    total_cases = aggregate.get("total_case_results")
    blocker_counts = tuple(aggregate.get(field) for field in (
        "provider_limited_cases",
        "runtime_or_adapter_failures",
        "quality_rejections",
    ))
    if not all(isinstance(value, int) and value >= 0 for value in (sample_count, minimum, total_cases, *blocker_counts)):
        return None
    if minimum < 2:
        return None
    if sample_count < minimum or total_cases != sample_count * EXPECTED_CASES_PER_SAMPLE:
        return "INSUFFICIENT_SAMPLES"
    if aggregate.get("provider_limited_cases", 0) > 0:
        return "REPEATED_PROVIDER_LIMITED_REQUIRES_REVIEW"
    if aggregate.get("runtime_or_adapter_failures", 0) > 0:
        return "RUNTIME_OR_ADAPTER_REQUIRES_REVIEW"
    if aggregate.get("quality_rejections", 0) > 0:
        return "QUALITY_REQUIRES_REVIEW"
    return EXPECTED_SUFFICIENT_STATUS


def evaluate_sufficiency(
    *,
    aggregate_path: Path = ROOT / AGGREGATE_PATH,
    freeze_path: Path = ROOT / FREEZE_PATH,
) -> dict[str, Any]:
    aggregate = _load_json(aggregate_path)
    freeze = _load_json(freeze_path)
    checks: dict[str, bool] = {}
    remediation_codes: list[str] = []

    checks["aggregate_schema_complete"] = REQUIRED_AGGREGATE_FIELDS.issubset(aggregate)
    if not checks["aggregate_schema_complete"]:
        remediation_codes.append("AGGREGATE_SCHEMA_INCOMPLETE")
    checks["aggregate_suite_locked"] = aggregate.get("suite") == EXPECTED_AGGREGATE_SUITE
    if not checks["aggregate_suite_locked"]:
        remediation_codes.append("AGGREGATE_SUITE_MISMATCH")
    checks["freeze_pass"] = _freeze_passes(freeze)
    if not checks["freeze_pass"]:
        remediation_codes.append("FREEZE_BOUNDARY_INVALID")
    relative_aggregate = AGGREGATE_PATH.as_posix()
    entry = _freeze_entry(freeze, relative_aggregate)
    checks["aggregate_listed_in_freeze"] = entry is not None
    if not checks["aggregate_listed_in_freeze"]:
        remediation_codes.append("AGGREGATE_NOT_FREEZE_LISTED")
    checks["aggregate_hash_matches_freeze"] = (
        entry is not None
        and isinstance(entry.get("sha256"), str)
        and _is_hex(entry.get("sha256"), 64)
        and aggregate_path.is_file()
        and _sha256(aggregate_path) == entry.get("sha256")
    )
    if not checks["aggregate_hash_matches_freeze"]:
        remediation_codes.append("AGGREGATE_FREEZE_HASH_MISMATCH")

    counts_valid = all(
        isinstance(aggregate.get(field), int) and aggregate[field] >= 0
        for field in (
            "sample_count",
            "min_samples",
            "total_case_results",
            "accepted_cases",
            "quality_denominator",
            "provider_limited_cases",
            "runtime_or_adapter_failures",
            "quality_rejections",
        )
    ) and aggregate.get("min_samples", 0) >= 2
    checks["counts_bounded"] = counts_valid
    if not counts_valid:
        remediation_codes.append("AGGREGATE_COUNTS_INVALID")

    checks["provenance_hashes_valid"] = (
        _is_hex(aggregate.get("registry_manifest_hash"), 64)
        and _is_hex(aggregate.get("index_hash"), 64)
        and isinstance(aggregate.get("index_version"), str)
        and bool(aggregate.get("index_version"))
        and aggregate.get("retrieval_source") == EXPECTED_RETRIEVAL_SOURCE
    )
    if not checks["provenance_hashes_valid"]:
        remediation_codes.append("RETRIEVAL_PROVENANCE_INVALID")

    expected_status = _expected_status(aggregate)
    checks["status_matches_counts"] = expected_status is not None and aggregate.get("status") == expected_status
    if not checks["status_matches_counts"]:
        remediation_codes.append("AGGREGATE_STATUS_CONFLICT")
    checks["minimum_samples_met"] = (
        counts_valid and aggregate.get("sample_count", 0) >= aggregate.get("min_samples", 2)
    )
    if not checks["minimum_samples_met"]:
        remediation_codes.append("MINIMUM_COMPATIBLE_SAMPLES_MISSING")
    checks["case_count_complete"] = (
        counts_valid
        and aggregate.get("total_case_results") == aggregate.get("sample_count") * EXPECTED_CASES_PER_SAMPLE
    )
    if not checks["case_count_complete"]:
        remediation_codes.append("EXPECTED_CASE_COUNT_MISSING")
    checks["no_provider_runtime_quality_blockers"] = (
        aggregate.get("provider_limited_cases") == 0
        and aggregate.get("runtime_or_adapter_failures") == 0
        and aggregate.get("quality_rejections") == 0
    )
    if not checks["no_provider_runtime_quality_blockers"]:
        remediation_codes.append("EVALUATION_BLOCKER_PRESENT")
    checks["quality_claim_suppressed_until_sufficient"] = (
        aggregate.get("status") != EXPECTED_SUFFICIENT_STATUS or (
            checks["minimum_samples_met"]
            and checks["case_count_complete"]
            and checks["no_provider_runtime_quality_blockers"]
        )
    )
    if not checks["quality_claim_suppressed_until_sufficient"]:
        remediation_codes.append("QUALITY_CLAIM_GATE_INVALID")

    checks["aggregate_boundary_locked"] = (
        aggregate.get("clinical_validity") == "PENDING"
        and aggregate.get("runtime_authority") == "NONE"
    )
    if not checks["aggregate_boundary_locked"]:
        remediation_codes.append("AGGREGATE_BOUNDARY_MUTATED")
    checks["redaction_pass"] = not any(
        marker.lower() in json.dumps(aggregate, sort_keys=True, ensure_ascii=True).lower()
        for marker in FORBIDDEN_MARKERS
    )
    if not checks["redaction_pass"]:
        remediation_codes.append("AGGREGATE_REDACTION_FAILED")
    checks["authorization_boundary_locked"] = freeze.get("authorization_boundary") == EXPECTED_BOUNDARY
    if not checks["authorization_boundary_locked"]:
        remediation_codes.append("AUTHORIZATION_BOUNDARY_MUTATED")

    remediation_codes = sorted(set(remediation_codes))
    structural_ok = all(
        checks[key]
        for key in (
            "aggregate_schema_complete",
            "aggregate_suite_locked",
            "freeze_pass",
            "aggregate_listed_in_freeze",
            "aggregate_hash_matches_freeze",
            "counts_bounded",
            "provenance_hashes_valid",
            "status_matches_counts",
            "aggregate_boundary_locked",
            "redaction_pass",
            "authorization_boundary_locked",
        )
    )
    sufficient = structural_ok and checks["minimum_samples_met"] and checks["case_count_complete"] and checks["no_provider_runtime_quality_blockers"]
    decision = "P2_004_EVIDENCE_SUFFICIENCY_READY_FOR_REVIEW" if sufficient else "P2_004_EVIDENCE_SUFFICIENCY_BLOCKED"
    return {
        "schema_version": "p2-004-evidence-sufficiency-v1",
        "evidence_type": "P2_004_EVIDENCE_SUFFICIENCY",
        "decision": decision,
        "aggregate_path": relative_aggregate,
        "freeze_path": FREEZE_PATH.as_posix(),
        "expected_status": expected_status,
        "aggregate_status": aggregate.get("status"),
        "sample_count": aggregate.get("sample_count"),
        "minimum_samples": aggregate.get("min_samples"),
        "total_case_results": aggregate.get("total_case_results"),
        "quality_pass_rate": aggregate.get("quality_pass_rate"),
        "model_id": aggregate.get("model_id"),
        "model_revision": aggregate.get("model_revision"),
        "corpus_revision": aggregate.get("corpus_revision"),
        "adapter_version": aggregate.get("adapter_version"),
        "retrieval_source": aggregate.get("retrieval_source"),
        "registry_manifest_hash": aggregate.get("registry_manifest_hash"),
        "index_hash": aggregate.get("index_hash"),
        "index_version": aggregate.get("index_version"),
        "checks": checks,
        "remediation_codes": remediation_codes,
        "external_review_eligible": sufficient,
        "clinical_validation": "PENDING",
        "production_ready": False,
        "runtime_authority": "NONE",
        "external_authority": "NONE",
        "authorization_promoted": False,
        "external_submission_allowed": False,
        "external_transmission_performed": False,
        "runtime_mutation_performed": False,
        "claim_boundary": "CONTROLLED_PRODUCTION_PROTOTYPE",
        "hardware_evidence": "UNVERIFIED",
        "read_only": True,
    }


if __name__ == "__main__":
    print(json.dumps(evaluate_sufficiency(), ensure_ascii=True, indent=2, sort_keys=True))
