from __future__ import annotations

from document_registry import DocumentRegistry, RegistryValidationError
from rebuildable_index import IndexBuildError, IndexStaleError, RebuildableIndexAdapter


def make_registry() -> DocumentRegistry:
    registry = DocumentRegistry()
    registry.register(
        doc_id="ops-roaming-v1",
        title="Roaming Tablet Operations Contract",
        version="1.0",
        owner="ward-operations",
        source_ref="synthetic://ops-roaming-v1",
        scope="operational",
        languages=["en"],
        text="A roaming tablet may acknowledge an alert through the authenticated Fixed Hub command API. RESET_CONFIRM is not allowed from the initial pilot tablet.",
        state="APPROVED",
        lifecycle_reason="initial approved fixture",
        lifecycle_actor_role="fixture_registry_operator",
    )
    registry.register(
        doc_id="ops-bilingual-v1",
        title="Bilingual Ward Operations Note",
        version="1.0",
        owner="ward-operations",
        source_ref="synthetic://ops-bilingual-v1",
        scope="operational",
        languages=["en", "th"],
        text="A roaming tablet cannot confirm RESET_CONFIRM directly. แท็บเล็ต roaming ห้ามยืนยัน RESET_CONFIRM โดยตรง และต้องผ่าน authenticated Fixed Hub command API",
        state="APPROVED",
        lifecycle_reason="initial approved fixture",
        lifecycle_actor_role="fixture_registry_operator",
    )
    registry.register(
        doc_id="clinical-shadow-v1",
        title="Clinical Shadow Mode Protocol",
        version="1.0",
        owner="clinical-governance",
        source_ref="synthetic://clinical-shadow-v1",
        scope="clinical-governance",
        languages=["en"],
        text="Triage signals are decision-support outputs. Clinical validation and human review remain pending.",
        state="APPROVED",
        lifecycle_reason="initial approved fixture",
        lifecycle_actor_role="fixture_registry_operator",
    )
    registry.register(
        doc_id="draft-ops-v1",
        title="Draft Operations Note",
        version="1.0",
        owner="ward-operations",
        source_ref="synthetic://draft-ops-v1",
        scope="operational",
        languages=["en"],
        text="Draft content is not approved for retrieval.",
        state="DRAFT",
    )
    return registry


class FailingIndex(RebuildableIndexAdapter):
    fail_on: str | None = None

    def _chunk_record(self, record):
        if self.fail_on == record.doc_id:
            raise IndexBuildError("injected rebuild failure")
        return super()._chunk_record(record)


def run() -> None:
    registry = make_registry()
    try:
        registry.register(
            doc_id="pii-doc-v1",
            title="Restricted Identity Fixture",
            version="1.0",
            owner="security",
            source_ref="synthetic://pii-doc-v1",
            scope="operational",
            languages=["en"],
            text="Synthetic patient name and HN-DEMO must never enter the index.",
            state="APPROVED",
        )
    except RegistryValidationError:
        print("[Registry] PII-bearing approved document rejected: PASSED")
    else:
        raise AssertionError("PII document was admitted")

    registry.approve("draft-ops-v1", "1.0", "reviewed for test", "fixture_registry_operator")
    assert registry.get("draft-ops-v1", "1.0").eligible is True
    print("[Registry] Draft requires explicit approval before eligibility: PASSED")

    index = RebuildableIndexAdapter(chunk_chars=800, min_score=2)
    first_manifest = index.rebuild(registry)
    assert first_manifest["chunk_count"] == 4
    print("[Index] Initial rebuild contains only eligible registry records: PASSED")

    thai_hits = index.query("แท็บเล็ต roaming ยืนยัน RESET_CONFIRM ได้ไหม", registry, scope="operational")
    assert thai_hits and thai_hits[0].doc_id == "ops-bilingual-v1"
    assert thai_hits[0].language == "en+th"
    print("[Index] Bilingual Thai/English query returns provenance-bearing hit: PASSED")

    clinical_hits = index.query("triage clinical validation", registry, scope="operational")
    assert not clinical_hits
    print("[Index] Scope isolation blocks clinical-governance content from operational query: PASSED")

    second_manifest = index.rebuild(registry)
    assert second_manifest == first_manifest
    print("[Index] Same registry/config produces deterministic manifest: PASSED")

    registry.deprecate("ops-bilingual-v1", "1.0", "superseded in fixture", "fixture_registry_operator")
    try:
        index.query("RESET_CONFIRM roaming", registry, scope="operational")
    except IndexStaleError:
        print("[Index] Registry mutation blocks stale index query: PASSED")
    else:
        raise AssertionError("stale index was queried after registry mutation")

    index.rebuild(registry)
    post_deprecate_hits = index.query("แท็บเล็ต roaming RESET_CONFIRM", registry, scope="operational")
    assert all(hit.doc_id != "ops-bilingual-v1" for hit in post_deprecate_hits)
    print("[Index] Deprecated document disappears after rebuild: PASSED")

    registry.revoke("ops-roaming-v1", "1.0", "fixture revocation", "fixture_registry_operator")
    index.rebuild(registry)
    assert not index.query("roaming RESET_CONFIRM", registry, scope="operational")
    print("[Index] Revoked document disappears after rebuild: PASSED")

    stable = RebuildableIndexAdapter(chunk_chars=800, min_score=2)
    stable.rebuild(make_registry())
    before = stable.snapshot_manifest()
    failing = FailingIndex(chunk_chars=800, min_score=2)
    failing.rebuild(make_registry())
    baseline = failing.snapshot_manifest()
    failing.fail_on = "ops-bilingual-v1"
    try:
        failing.rebuild(make_registry())
    except IndexBuildError:
        assert failing.snapshot_manifest() == baseline
        print("[Index] Failed rebuild leaves active index unchanged: PASSED")
    else:
        raise AssertionError("injected rebuild failure did not fail")
    assert before["index_hash"] == baseline["index_hash"]

    snapshot = registry.snapshot()
    restored = DocumentRegistry.from_snapshot(snapshot)
    assert restored.manifest_hash() == registry.manifest_hash()
    assert [record.doc_id for record in restored.records()] == [record.doc_id for record in registry.records()]
    print("[Registry] Deterministic snapshot export/import preserves manifest hash: PASSED")

    tampered_snapshot = dict(snapshot)
    tampered_snapshot["manifest_hash"] = "0" * 64
    try:
        DocumentRegistry.from_snapshot(tampered_snapshot)
    except RegistryValidationError:
        print("[Registry] Tampered snapshot is rejected before import: PASSED")
    else:
        raise AssertionError("tampered registry snapshot was imported")

    transition_registry = DocumentRegistry()
    transition_registry.register(
        doc_id="transition-doc-v1",
        title="Transition Fixture",
        version="1.0",
        owner="security",
        source_ref="synthetic://transition-doc-v1",
        scope="operational",
        languages=["en"],
        text="Lifecycle transition fixture.",
        state="DRAFT",
    )
    try:
        transition_registry.deprecate("transition-doc-v1", "1.0", "invalid", "fixture_registry_operator")
    except RegistryValidationError:
        print("[Registry] Invalid DRAFT to DEPRECATED transition is rejected: PASSED")
    else:
        raise AssertionError("invalid lifecycle transition accepted")

    print("APPROVED_REGISTRY_REBUILDABLE_INDEX_TESTS_PASSED")


if __name__ == "__main__":
    run()
