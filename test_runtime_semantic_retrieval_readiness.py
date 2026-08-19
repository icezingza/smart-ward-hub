from __future__ import annotations

from evals.micro_rag.run_gemini_evaluation import build_registry_index, load_documents
from persistence_contract import default_software_policy
from runtime_semantic_retrieval_readiness import evaluate_runtime_readiness


def run() -> None:
    registry, index = build_registry_index(load_documents())
    policy = default_software_policy("index_snapshot")
    not_ready = evaluate_runtime_readiness(
        registry=registry,
        index=index,
        persistence_policy=policy,
        repeated_summary={"status": "INSUFFICIENT_SAMPLES"},
    )
    assert not_ready.status == "NOT_READY"
    assert not_ready.clinical_validation_authorized is False
    assert not_ready.production_authorized is False
    assert not_ready.runtime_authority == "NONE"
    assert any(check.check_id == "runtime_semantic_backend_configured" and not check.passed for check in not_ready.checks)
    assert any(check.check_id == "clinical_governance_boundary" and not check.passed for check in not_ready.checks)
    print("[Readiness] Missing repeated samples and runtime/external controls fail closed: PASSED")

    ready_for_review = evaluate_runtime_readiness(
        registry=registry,
        index=index,
        persistence_policy=policy,
        repeated_summary={"status": "REPEATED_EVALUATED_WITH_ADAPTER"},
        runtime_backend_configured=True,
        access_control_enforced=True,
        clinical_governance_review_complete=True,
        external_persistence_approved=True,
    )
    assert ready_for_review.status == "READY_FOR_EXTERNAL_GOVERNANCE_REVIEW"
    assert ready_for_review.clinical_validation_authorized is False
    assert ready_for_review.production_authorized is False
    assert ready_for_review.runtime_authority == "NONE"
    print("[Readiness] Complete preflight reaches review-ready status without authorization: PASSED")

    registry.deprecate("ops-ward-bilingual-v1", "1.0", "stale readiness fixture", "readiness-test-operator")
    stale = evaluate_runtime_readiness(
        registry=registry,
        index=index,
        persistence_policy=policy,
        repeated_summary={"status": "REPEATED_EVALUATED_WITH_ADAPTER"},
        runtime_backend_configured=True,
        access_control_enforced=True,
        clinical_governance_review_complete=True,
        external_persistence_approved=True,
    )
    assert stale.status == "NOT_READY"
    assert any(check.check_id == "registry_index_manifest_match" and not check.passed for check in stale.checks)
    print("[Readiness] Stale registry/index binding reopens readiness gate: PASSED")

    print("RUNTIME_SEMANTIC_RETRIEVAL_READINESS_TESTS_PASSED")


if __name__ == "__main__":
    run()
