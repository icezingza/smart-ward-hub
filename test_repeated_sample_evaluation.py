from __future__ import annotations

import json
import tempfile
from pathlib import Path

from repeated_sample_evaluation import RepeatedSampleAggregationError, aggregate_reports


def report(run_id: str, *, provider_failure: bool = False, quality_failure: bool = False, index_hash: str = "index-hash") -> dict:
    result = {
        "case_id": "answerable_roaming",
        "case_passed": not provider_failure and not quality_failure,
        "accepted": not provider_failure and not quality_failure,
        "violations": ["model_call_failed"] if provider_failure else [],
        "metadata": {
            "model_id": "fixture-model",
            "model_revision": "fixture-revision",
            "corpus_revision": "fixture-v2",
            "adapter_version": "response-adapter-v1",
            "timestamp_utc": "2026-08-20T00:00:00Z",
        },
    }
    if provider_failure:
        result["failure_class"] = "PROVIDER_LIMIT_OR_TRANSIENT"
        result["error_type"] = "model_http_429"
    report_payload = {
        "suite": "micro-rag-model-specific-v2",
        "run_id": run_id,
        "model_id": "fixture-model",
        "model_revision": "fixture-revision",
        "corpus_revision": "fixture-v2",
        "adapter_version": "response-adapter-v1",
        "retrieval_source": "document-registry-v2/rebuildable-index-v2",
        "registry_manifest_hash": "registry-hash",
        "index_snapshot": {"index_version": "rebuildable-index-v2", "index_hash": index_hash},
        "results": [result],
    }
    return report_payload


def write_reports(directory: Path, reports: list[dict]) -> list[Path]:
    paths: list[Path] = []
    for index, payload in enumerate(reports):
        path = directory / f"sample-{index}.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        paths.append(path)
    return paths


def run() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        directory = Path(temporary)
        insufficient_path = write_reports(directory, [report("only-one")])[0]
        insufficient = aggregate_reports([insufficient_path])
        assert insufficient["status"] == "INSUFFICIENT_SAMPLES"
        assert insufficient["quality_pass_rate"] == 1.0
        print("[Repeated] Minimum sample count is fail-closed: PASSED")

        complete_paths = write_reports(directory, [report("sample-a"), report("sample-b")])
        complete = aggregate_reports(complete_paths)
        assert complete["status"] == "REPEATED_EVALUATED_WITH_ADAPTER"
        assert complete["quality_denominator"] == 2
        assert complete["quality_pass_rate"] == 1.0
        print("[Repeated] Compatible repeated samples aggregate successfully: PASSED")

        provider_paths = write_reports(directory, [report("sample-c"), report("sample-d", provider_failure=True)])
        provider = aggregate_reports(provider_paths)
        assert provider["status"] == "REPEATED_PROVIDER_LIMITED_REQUIRES_REVIEW"
        assert provider["provider_limited_cases"] == 1
        assert provider["quality_denominator"] == 1
        assert provider["quality_pass_rate"] == 1.0
        print("[Repeated] Provider-limited cases are excluded from quality denominator: PASSED")

        quality_paths = write_reports(directory, [report("sample-e"), report("sample-f", quality_failure=True)])
        quality = aggregate_reports(quality_paths)
        assert quality["status"] == "QUALITY_REQUIRES_REVIEW"
        assert quality["quality_rejections"] == 1
        assert quality["quality_pass_rate"] == 0.5
        print("[Repeated] Quality rejection remains distinct from provider failure: PASSED")

        incompatible_paths = write_reports(directory, [report("sample-g"), report("sample-h", index_hash="different-index")])
        try:
            aggregate_reports(incompatible_paths)
        except RepeatedSampleAggregationError:
            print("[Repeated] Incompatible index provenance is rejected: PASSED")
        else:
            raise AssertionError("incompatible provenance was aggregated")

    print("REPEATED_SAMPLE_EVALUATION_TESTS_PASSED")


if __name__ == "__main__":
    run()
