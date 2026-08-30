"""Focused/adversarial tests for the P2-004 evidence sufficiency gate."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile

from canonical_file_hash import canonical_sha256
from p2_004_evidence_sufficiency import (
    AGGREGATE_PATH,
    FREEZE_PATH,
    EXPECTED_BOUNDARY,
    evaluate_sufficiency,
)


ROOT = Path(__file__).resolve().parent


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_fixture(directory: Path, aggregate: dict, freeze: dict) -> tuple[Path, Path]:
    aggregate_path = directory / "aggregate.json"
    freeze_path = directory / "freeze.json"
    aggregate_path.write_text(json.dumps(aggregate, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    for entry in freeze["files"]:
        if entry["path"] == AGGREGATE_PATH.as_posix():
            entry["sha256"] = canonical_sha256(aggregate_path)
    freeze_path.write_text(json.dumps(freeze, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return aggregate_path, freeze_path


def _clean_complete_aggregate() -> dict:
    aggregate = _load(ROOT / AGGREGATE_PATH)
    aggregate.update(
        {
            "sample_count": 2,
            "min_samples": 2,
            "total_case_results": 16,
            "accepted_cases": 16,
            "quality_denominator": 16,
            "quality_pass_rate": 1.0,
            "provider_limited_cases": 0,
            "runtime_or_adapter_failures": 0,
            "quality_rejections": 0,
            "status": "REPEATED_EVALUATED_WITH_ADAPTER",
            "clinical_validity": "PENDING",
            "runtime_authority": "NONE",
        }
    )
    return aggregate


def test_current_provider_limited_insufficient_sample_is_blocked():
    report = evaluate_sufficiency()
    assert report["decision"] == "P2_004_EVIDENCE_SUFFICIENCY_BLOCKED"
    assert report["aggregate_status"] == "INSUFFICIENT_SAMPLES"
    assert report["checks"]["minimum_samples_met"] is False
    assert report["checks"]["quality_claim_suppressed_until_sufficient"] is True
    assert "MINIMUM_COMPATIBLE_SAMPLES_MISSING" in report["remediation_codes"]
    print("[P2-004 Sufficiency] Current one-sample/provider-limited evidence remains blocked: PASSED")


def test_complete_clean_repeated_set_is_ready_for_review_only():
    with tempfile.TemporaryDirectory() as directory:
        aggregate_path, freeze_path = _write_fixture(
            Path(directory),
            _clean_complete_aggregate(),
            _load(ROOT / FREEZE_PATH),
        )
        report = evaluate_sufficiency(aggregate_path=aggregate_path, freeze_path=freeze_path)
    assert report["decision"] == "P2_004_EVIDENCE_SUFFICIENCY_READY_FOR_REVIEW"
    assert report["external_review_eligible"] is True
    assert report["production_ready"] is False
    assert report["runtime_authority"] == "NONE"
    assert report["remediation_codes"] == []
    print("[P2-004 Sufficiency] Complete clean repeated set reaches review-ready without authorization: PASSED")


def test_provider_blocker_and_count_mismatch_fail_closed():
    with tempfile.TemporaryDirectory() as directory:
        aggregate = _clean_complete_aggregate()
        aggregate["provider_limited_cases"] = 1
        aggregate["status"] = "REPEATED_PROVIDER_LIMITED_REQUIRES_REVIEW"
        aggregate_path, freeze_path = _write_fixture(Path(directory), aggregate, _load(ROOT / FREEZE_PATH))
        report = evaluate_sufficiency(aggregate_path=aggregate_path, freeze_path=freeze_path)
    assert report["decision"] == "P2_004_EVIDENCE_SUFFICIENCY_BLOCKED"
    assert report["checks"]["no_provider_runtime_quality_blockers"] is False
    assert "EVALUATION_BLOCKER_PRESENT" in report["remediation_codes"]
    print("[P2-004 Sufficiency] Provider-limited evidence cannot pass quality gate: PASSED")


def test_status_claim_conflict_and_malformed_counts_fail_closed():
    with tempfile.TemporaryDirectory() as directory:
        aggregate = _clean_complete_aggregate()
        aggregate["sample_count"] = 1
        aggregate["total_case_results"] = 8
        aggregate["status"] = "REPEATED_EVALUATED_WITH_ADAPTER"
        aggregate["provider_limited_cases"] = "not-an-integer"
        aggregate_path, freeze_path = _write_fixture(Path(directory), aggregate, _load(ROOT / FREEZE_PATH))
        report = evaluate_sufficiency(aggregate_path=aggregate_path, freeze_path=freeze_path)
    assert report["decision"] == "P2_004_EVIDENCE_SUFFICIENCY_BLOCKED"
    assert report["checks"]["counts_bounded"] is False
    assert report["checks"]["status_matches_counts"] is False
    assert "AGGREGATE_COUNTS_INVALID" in report["remediation_codes"]
    print("[P2-004 Sufficiency] Malformed counts/status conflict fail closed: PASSED")


def test_provenance_and_redaction_mutations_fail_closed():
    with tempfile.TemporaryDirectory() as directory:
        aggregate = _clean_complete_aggregate()
        aggregate["index_hash"] = "invalid"
        aggregate["model_id"] = "patient_token"
        aggregate_path, freeze_path = _write_fixture(Path(directory), aggregate, _load(ROOT / FREEZE_PATH))
        report = evaluate_sufficiency(aggregate_path=aggregate_path, freeze_path=freeze_path)
    assert report["decision"] == "P2_004_EVIDENCE_SUFFICIENCY_BLOCKED"
    assert report["checks"]["provenance_hashes_valid"] is False
    assert report["checks"]["redaction_pass"] is False
    assert "RETRIEVAL_PROVENANCE_INVALID" in report["remediation_codes"]
    assert "AGGREGATE_REDACTION_FAILED" in report["remediation_codes"]
    print("[P2-004 Sufficiency] Provenance and raw-identity mutations fail closed: PASSED")


def test_freeze_hash_and_authorization_mutations_fail_closed():
    with tempfile.TemporaryDirectory() as directory:
        aggregate = _clean_complete_aggregate()
        freeze = _load(ROOT / FREEZE_PATH)
        freeze["authorization_boundary"] = {**EXPECTED_BOUNDARY, "production_authorized": True}
        aggregate_path, freeze_path = _write_fixture(Path(directory), aggregate, freeze)
        freeze_mutated = _load(freeze_path)
        for entry in freeze_mutated["files"]:
            if entry["path"] == AGGREGATE_PATH.as_posix():
                entry["sha256"] = "0" * 64
        freeze_path.write_text(json.dumps(freeze_mutated, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        report = evaluate_sufficiency(aggregate_path=aggregate_path, freeze_path=freeze_path)
    assert report["decision"] == "P2_004_EVIDENCE_SUFFICIENCY_BLOCKED"
    assert report["checks"]["freeze_pass"] is False
    assert report["checks"]["aggregate_hash_matches_freeze"] is False
    assert report["checks"]["authorization_boundary_locked"] is False
    assert "FREEZE_BOUNDARY_INVALID" in report["remediation_codes"]
    assert "AGGREGATE_FREEZE_HASH_MISMATCH" in report["remediation_codes"]
    assert "AUTHORIZATION_BOUNDARY_MUTATED" in report["remediation_codes"]
    print("[P2-004 Sufficiency] Freeze/hash/authorization mutations fail closed: PASSED")


def run() -> None:
    tests = [
        test_current_provider_limited_insufficient_sample_is_blocked,
        test_complete_clean_repeated_set_is_ready_for_review_only,
        test_provider_blocker_and_count_mismatch_fail_closed,
        test_status_claim_conflict_and_malformed_counts_fail_closed,
        test_provenance_and_redaction_mutations_fail_closed,
        test_freeze_hash_and_authorization_mutations_fail_closed,
    ]
    for test in tests:
        test()
    print(f"[P2-004 Sufficiency] focused/adversarial tests: {len(tests)} PASSED")
    print("P2_004_EVIDENCE_SUFFICIENCY_TESTS_PASSED")


if __name__ == "__main__":
    run()
