from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


class RepeatedSampleAggregationError(ValueError):
    pass


def _aware_timestamp(value: object) -> None:
    if not isinstance(value, str):
        raise RepeatedSampleAggregationError("sample_timestamp_missing")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise RepeatedSampleAggregationError("sample_timestamp_invalid") from exc
    if parsed.tzinfo is None:
        raise RepeatedSampleAggregationError("sample_timestamp_must_be_timezone_aware")


def _provider_failure(result: dict[str, Any]) -> bool:
    return result.get("failure_class") == "PROVIDER_LIMIT_OR_TRANSIENT" or str(result.get("error_type", "")).startswith("model_http_")


def _runtime_failure(result: dict[str, Any]) -> bool:
    return result.get("failure_class") == "RUNTIME_OR_ADAPTER_ERROR"


def _quality_rejection(result: dict[str, Any]) -> bool:
    if _provider_failure(result) or _runtime_failure(result):
        return False
    if result.get("case_passed") is True:
        return False
    return True


def load_report(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    try:
        report = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RepeatedSampleAggregationError("sample_report_unreadable") from exc
    if not isinstance(report, dict):
        raise RepeatedSampleAggregationError("sample_report_object_required")
    required = {"suite", "run_id", "model_id", "model_revision", "corpus_revision", "adapter_version", "retrieval_source", "results"}
    if not required.issubset(report):
        raise RepeatedSampleAggregationError("sample_report_schema_incomplete")
    if report["suite"] != "micro-rag-model-specific-v2":
        raise RepeatedSampleAggregationError("sample_report_suite_mismatch")
    if not isinstance(report["results"], list) or not report["results"]:
        raise RepeatedSampleAggregationError("sample_report_results_required")
    if not isinstance(report["run_id"], str) or not report["run_id"].strip():
        raise RepeatedSampleAggregationError("sample_run_id_required")
    case_ids: set[str] = set()
    for result in report["results"]:
        if not isinstance(result, dict):
            raise RepeatedSampleAggregationError("sample_result_object_required")
        case_id = result.get("case_id")
        if not isinstance(case_id, str) or not case_id.strip() or case_id in case_ids:
            raise RepeatedSampleAggregationError("sample_case_id_duplicate_or_missing")
        case_ids.add(case_id)
        metadata = result.get("metadata")
        if not isinstance(metadata, dict):
            raise RepeatedSampleAggregationError("sample_result_metadata_required")
        for key in ("model_id", "model_revision", "corpus_revision", "adapter_version", "timestamp_utc"):
            if key not in metadata:
                raise RepeatedSampleAggregationError(f"sample_metadata_{key}_missing")
        _aware_timestamp(metadata["timestamp_utc"])
        if metadata["model_id"] != report["model_id"] or metadata["model_revision"] != report["model_revision"]:
            raise RepeatedSampleAggregationError("sample_metadata_model_mismatch")
        if metadata["corpus_revision"] != report["corpus_revision"] or metadata["adapter_version"] != report["adapter_version"]:
            raise RepeatedSampleAggregationError("sample_metadata_contract_mismatch")
    return report


def _compatibility_key(report: dict[str, Any]) -> tuple[object, ...]:
    index_snapshot = report.get("index_snapshot") or {}
    return (
        report["model_id"],
        report["model_revision"],
        report["corpus_revision"],
        report["adapter_version"],
        report["retrieval_source"],
        report.get("registry_manifest_hash"),
        index_snapshot.get("index_hash"),
        index_snapshot.get("index_version"),
    )


def aggregate_reports(paths: list[str | Path], *, min_samples: int = 2) -> dict[str, Any]:
    if min_samples < 2:
        raise RepeatedSampleAggregationError("min_samples_must_be_at_least_two")
    if not paths:
        raise RepeatedSampleAggregationError("at_least_one_report_required")
    reports = [load_report(path) for path in paths]
    run_ids = [report["run_id"] for report in reports]
    if len(set(run_ids)) != len(run_ids):
        raise RepeatedSampleAggregationError("duplicate_sample_run_id")
    compatibility = _compatibility_key(reports[0])
    if any(_compatibility_key(report) != compatibility for report in reports[1:]):
        raise RepeatedSampleAggregationError("incompatible_sample_provenance")

    results = [result for report in reports for result in report["results"]]
    provider_failures = sum(1 for result in results if _provider_failure(result))
    runtime_failures = sum(1 for result in results if _runtime_failure(result))
    quality_rejections = sum(1 for result in results if _quality_rejection(result))
    completed_results = [result for result in results if not _provider_failure(result) and not _runtime_failure(result)]
    accepted_cases = sum(1 for result in completed_results if result.get("case_passed") is True)
    quality_denominator = len(completed_results)
    quality_pass_rate = accepted_cases / quality_denominator if quality_denominator else None

    if len(reports) < min_samples:
        status = "INSUFFICIENT_SAMPLES"
    elif quality_rejections:
        status = "QUALITY_REQUIRES_REVIEW"
    elif provider_failures:
        status = "REPEATED_PROVIDER_LIMITED_REQUIRES_REVIEW"
    else:
        status = "REPEATED_EVALUATED_WITH_ADAPTER"

    return {
        "suite": "micro-rag-repeated-sample-aggregation-v1",
        "source_reports": [str(Path(path)) for path in paths],
        "sample_count": len(reports),
        "min_samples": min_samples,
        "model_id": compatibility[0],
        "model_revision": compatibility[1],
        "corpus_revision": compatibility[2],
        "adapter_version": compatibility[3],
        "retrieval_source": compatibility[4],
        "registry_manifest_hash": compatibility[5],
        "index_hash": compatibility[6],
        "index_version": compatibility[7],
        "total_case_results": len(results),
        "accepted_cases": accepted_cases,
        "quality_denominator": quality_denominator,
        "quality_pass_rate": quality_pass_rate,
        "provider_limited_cases": provider_failures,
        "runtime_or_adapter_failures": runtime_failures,
        "quality_rejections": quality_rejections,
        "status": status,
        "clinical_validity": "PENDING",
        "runtime_authority": "NONE",
    }


def write_aggregate(paths: list[str | Path], output: str | Path, *, min_samples: int = 2) -> dict[str, Any]:
    aggregate = aggregate_reports(paths, min_samples=min_samples)
    target = Path(output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(aggregate, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return aggregate


if __name__ == "__main__":
    if len(sys.argv) < 3:
        raise SystemExit("usage: repeated_sample_evaluation.py OUTPUT_JSON REPORT_JSON [REPORT_JSON ...]")
    result = write_aggregate(sys.argv[2:], sys.argv[1])
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))
