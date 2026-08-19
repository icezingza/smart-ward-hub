from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal


ReviewDecisionStatus = Literal[
    "BLOCKED_INCOMPLETE_EVIDENCE",
    "BLOCKED_PROVIDER_WINDOW",
    "BLOCKED_RUNTIME_ADAPTER",
    "REQUIRES_HUMAN_REVIEW",
    "ACCEPTED_FOR_EXTERNAL_REVIEW",
]


class ReviewDecisionError(ValueError):
    pass


@dataclass(frozen=True)
class RepeatedSampleProtocol:
    protocol_version: str = "p2-004-repeated-sample-v1"
    minimum_samples: int = 2
    expected_cases_per_sample: int = 8

    def validate(self) -> "RepeatedSampleProtocol":
        if not self.protocol_version.strip():
            raise ReviewDecisionError("protocol_version_required")
        if self.minimum_samples < 2:
            raise ReviewDecisionError("minimum_samples_must_be_at_least_two")
        if self.expected_cases_per_sample < 1:
            raise ReviewDecisionError("expected_cases_per_sample_must_be_positive")
        return self


def decide_review_status(summary: dict[str, Any], protocol: RepeatedSampleProtocol | None = None) -> dict[str, Any]:
    protocol = (protocol or RepeatedSampleProtocol()).validate()
    required = {
        "sample_count",
        "total_case_results",
        "provider_limited_cases",
        "runtime_or_adapter_failures",
        "quality_rejections",
        "quality_denominator",
        "quality_pass_rate",
        "model_id",
        "model_revision",
        "corpus_revision",
        "adapter_version",
        "retrieval_source",
        "registry_manifest_hash",
        "index_hash",
    }
    missing = sorted(required - set(summary))
    if missing:
        raise ReviewDecisionError(f"summary_fields_missing:{','.join(missing)}")

    sample_count = summary["sample_count"]
    total_case_results = summary["total_case_results"]
    if not isinstance(sample_count, int) or sample_count < 0:
        raise ReviewDecisionError("sample_count_invalid")
    if not isinstance(total_case_results, int) or total_case_results < 0:
        raise ReviewDecisionError("total_case_results_invalid")
    if sample_count < protocol.minimum_samples:
        status: ReviewDecisionStatus = "BLOCKED_INCOMPLETE_EVIDENCE"
        reason = "minimum compatible sample count has not been met"
    elif summary["provider_limited_cases"]:
        status = "BLOCKED_PROVIDER_WINDOW"
        reason = "provider-limited cases remain in the repeated sample set"
    elif summary["runtime_or_adapter_failures"]:
        status = "BLOCKED_RUNTIME_ADAPTER"
        reason = "runtime or adapter failures remain in the repeated sample set"
    elif summary["quality_rejections"]:
        status = "REQUIRES_HUMAN_REVIEW"
        reason = "quality or contract rejection requires human review"
    elif total_case_results != sample_count * protocol.expected_cases_per_sample:
        status = "BLOCKED_INCOMPLETE_EVIDENCE"
        reason = "repeated sample set does not contain the expected case count"
    else:
        status = "ACCEPTED_FOR_EXTERNAL_REVIEW"
        reason = "compatible repeated samples completed without provider/runtime/quality blockers"

    return {
        "protocol_version": protocol.protocol_version,
        "status": status,
        "reason": reason,
        "sample_count": sample_count,
        "minimum_samples": protocol.minimum_samples,
        "expected_cases_per_sample": protocol.expected_cases_per_sample,
        "model_id": summary["model_id"],
        "model_revision": summary["model_revision"],
        "corpus_revision": summary["corpus_revision"],
        "adapter_version": summary["adapter_version"],
        "retrieval_source": summary["retrieval_source"],
        "registry_manifest_hash": summary["registry_manifest_hash"],
        "index_hash": summary["index_hash"],
        "quality_denominator": summary["quality_denominator"],
        "quality_pass_rate": summary["quality_pass_rate"],
        "provider_limited_cases": summary["provider_limited_cases"],
        "runtime_or_adapter_failures": summary["runtime_or_adapter_failures"],
        "quality_rejections": summary["quality_rejections"],
        "clinical_validation_authorized": False,
        "production_authorized": False,
        "runtime_authority": "NONE",
    }


__all__ = ["RepeatedSampleProtocol", "ReviewDecisionError", "decide_review_status"]
