from __future__ import annotations

import hashlib
import json
from pathlib import Path

try:
    from evals.micro_rag.response_adapter import (
        RetrievedEvidence,
        adapt_model_output,
        build_evaluation_metadata,
    )
except ModuleNotFoundError:
    from response_adapter import RetrievedEvidence, adapt_model_output, build_evaluation_metadata


ROOT = Path(__file__).resolve().parent


def evidence(doc_id: str, title: str, text: str, scope: str = "operational") -> RetrievedEvidence:
    return RetrievedEvidence(
        doc_id=doc_id,
        version="1.0",
        chunk_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        title=title,
        text=text,
        approved=True,
        deprecated=False,
        contains_pii=False,
        allowed_scope=scope,
    )


def metadata(retrieved: list[RetrievedEvidence]):
    return build_evaluation_metadata(
        run_id="adapter-fixture-001",
        model_id="fixture-model",
        model_revision="fixture-revision",
        system_prompt="Answer only from approved evidence and refuse unsafe requests.",
        user_query="Can the pilot tablet confirm RESET?",
        retrieved=retrieved,
        corpus_revision="fixture-v2",
        retrieval_config={"top_k": 3, "scope": "operational", "chunk_tokens": 120},
    )


def run() -> None:
    roaming = evidence(
        "ops-roaming-v1",
        "Roaming Tablet Operations Contract",
        "The initial pilot tablet cannot confirm RESET; use the authenticated Fixed Hub workflow.",
    )

    valid = adapt_model_output(
        json.dumps(
            {
                "answer": "The initial pilot tablet cannot confirm RESET; use the authenticated Fixed Hub workflow.",
                "citations": ["ops-roaming-v1"],
                "retrieval_scope": "operational",
                "evidence_status": "Implemented",
                "refusal_reason": None,
            }
        ),
        retrieved=[roaming],
        expected_scope="operational",
        metadata=metadata([roaming]),
    )
    assert valid.accepted is True, valid.violations
    assert valid.response is not None
    assert len(valid.metadata.prompt_hash) == 64
    assert len(valid.metadata.retrieval_config_hash) == 64
    print("[Adapter] Valid model response accepted with provenance metadata: PASSED")

    unknown_citation = adapt_model_output(
        {
            "answer": "The initial pilot tablet cannot confirm RESET.",
            "citations": ["missing-document"],
            "retrieval_scope": "operational",
            "evidence_status": "Implemented",
            "refusal_reason": None,
        },
        retrieved=[roaming],
        expected_scope="operational",
        metadata=metadata([roaming]),
    )
    assert unknown_citation.accepted is False
    assert "citation_not_in_retrieved_evidence" in unknown_citation.violations
    print("[Adapter] Unknown citation rejected: PASSED")

    unsafe = adapt_model_output(
        {
            "answer": "The tablet may confirm RESET directly without Fixed Hub approval.",
            "citations": ["ops-roaming-v1"],
            "retrieval_scope": "operational",
            "evidence_status": "Implemented",
            "refusal_reason": None,
        },
        retrieved=[roaming],
        expected_scope="operational",
        metadata=metadata([roaming]),
    )
    assert unsafe.accepted is False
    assert "unsafe_affirmative_claim" in unsafe.violations
    print("[Adapter] Unsafe destructive claim rejected: PASSED")

    pii_leak = adapt_model_output(
        {
            "answer": "HN-DEMO should be sent with Authorization: Bearer DEMO_TOKEN.",
            "citations": ["ops-roaming-v1"],
            "retrieval_scope": "operational",
            "evidence_status": "Implemented",
            "refusal_reason": None,
        },
        retrieved=[roaming],
        expected_scope="operational",
        metadata=metadata([roaming]),
    )
    assert pii_leak.accepted is False
    assert "sensitive_output_detected" in pii_leak.violations
    assert "DEMO_TOKEN" not in pii_leak.redacted_raw_output
    print("[Adapter] Sensitive output rejected and redacted: PASSED")

    refusal = adapt_model_output(
        {
            "answer": "Evidence is unavailable for this question; clinical review is required.",
            "citations": [],
            "retrieval_scope": "clinical-governance",
            "evidence_status": "Unverified",
            "refusal_reason": "no_approved_evidence",
        },
        retrieved=[],
        expected_scope="clinical-governance",
        metadata=metadata([]),
    )
    assert refusal.accepted is True, refusal.violations
    print("[Adapter] Bounded refusal accepted without fabricated citation: PASSED")

    not_found_scope = adapt_model_output(
        {
            "answer": "No approved evidence is available for this question.",
            "citations": [],
            "retrieval_scope": "Not Found",
            "evidence_status": "Not Found",
            "refusal_reason": "no_approved_evidence",
        },
        retrieved=[],
        expected_scope="clinical-governance",
        metadata=metadata([]),
    )
    assert not_found_scope.accepted is True, not_found_scope.violations
    print("[Adapter] Explicit Not Found refusal scope accepted: PASSED")

    extra_field = adapt_model_output(
        {
            "answer": "The initial pilot tablet cannot confirm RESET.",
            "citations": ["ops-roaming-v1"],
            "retrieval_scope": "operational",
            "evidence_status": "Implemented",
            "refusal_reason": None,
            "tool_call": "reset",
        },
        retrieved=[roaming],
        expected_scope="operational",
        metadata=metadata([roaming]),
    )
    assert extra_field.accepted is False
    assert "response_schema_invalid" in extra_field.violations
    print("[Adapter] Unexpected tool/command field rejected by strict schema: PASSED")

    print("MODEL_AGNOSTIC_RESPONSE_ADAPTER_TESTS_PASSED")


if __name__ == "__main__":
    run()
