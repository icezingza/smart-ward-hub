from __future__ import annotations

from pathlib import Path

from run_gemini_evaluation import build_registry_index, build_cases_from_index, load_documents


ROOT = Path(__file__).resolve().parent


def run() -> None:
    registry, index = build_registry_index(load_documents())
    assert len(registry.eligible_records()) == 4
    snapshot = index.snapshot_manifest()
    assert snapshot["index_version"] == "rebuildable-index-v2"
    assert snapshot["registry_manifest_hash"] == registry.manifest_hash()
    assert snapshot["index_hash"]
    second_registry, second_index = build_registry_index(load_documents())
    assert second_registry.manifest_hash() == registry.manifest_hash()
    assert second_index.snapshot_manifest()["index_hash"] == snapshot["index_hash"]
    print("[P2-004] Runner builds registry-backed deterministic index across repeated samples: PASSED")

    cases = build_cases_from_index(registry, index)
    assert len(cases) == 8
    for case in cases:
        for evidence in case["retrieved"]:
            assert evidence.approved is True
            assert evidence.deprecated is False
            assert evidence.contains_pii is False
            assert evidence.allowed_scope == case["scope"]
    print("[P2-004] All evaluated retrieval evidence is eligible and scope-bound: PASSED")

    bilingual = next(case for case in cases if case["case_id"] == "bilingual_thai_english_policy")
    assert bilingual["retrieved"]
    assert any(item.doc_id == "ops-ward-bilingual-v1" for item in bilingual["retrieved"])
    print("[P2-004] Bilingual case retrieves through rebuilt index with provenance: PASSED")

    unknown = next(case for case in cases if case["case_id"] == "unknown_clinical")
    assert unknown["retrieved"] == []
    print("[P2-004] Unknown clinical case retrieves no weakly matched evidence: PASSED")

    print("REGISTRY_BACKED_MICRO_RAG_EVALUATION_TESTS_PASSED")


if __name__ == "__main__":
    run()
