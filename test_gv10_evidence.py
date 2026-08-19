from __future__ import annotations

from gv10_evidence import EvidenceEntry, GV10EvidenceError, build_gv10_template


SHA = "a" * 64


def expect_error(action, expected: str) -> None:
    try:
        action()
    except GV10EvidenceError as exc:
        assert str(exc) == expected, (str(exc), expected)
    else:
        raise AssertionError(f"expected {expected}")


def entry(**overrides) -> EvidenceEntry:
    values = {
        "evidence_id": "EV-GV10-P1001-001",
        "gate_id": "GV-01",
        "artifact_ref": "P1_006_CLINICAL_VALIDATION_READINESS_PLAN.md",
        "artifact_sha256": SHA,
        "evidence_class": "SOFTWARE_VERIFIED",
        "collected_at_utc": "2026-08-20T10:00:00+00:00",
        "prepared_by_role": "engineering_evidence_coordinator",
        "source_boundary": "repository_software_artifact",
        "redaction_status": "PASS",
        "chain_of_custody_ref": "COC-GV10-0001",
    }
    values.update(overrides)
    return EvidenceEntry(**values)


def run() -> None:
    dossier = build_gv10_template()
    dossier.add_entry(entry())
    result = dossier.review_readiness()
    assert result["entry_count"] == 1
    assert result["gate_ids_covered"] == ["GV-01"]
    assert result["ready_for_independent_review"] is True
    assert result["clinical_validation_authorized"] is False
    assert result["production_authorized"] is False
    print("[GV-10] Evidence dossier with hash, provenance, redaction and chain-of-custody passes: PASSED")

    expect_error(lambda: dossier.add_entry(entry(evidence_id="EV-GV10-P1001-001")), "duplicate_evidence_id")
    expect_error(lambda: dossier.add_entry(entry(artifact_sha256="not-a-sha")), "artifact_sha256_required")
    expect_error(lambda: dossier.add_entry(entry(redaction_status="PENDING")), "redaction_pass_required")
    expect_error(lambda: dossier.add_entry(entry(chain_of_custody_ref="HN-2026-1234")), "unsafe_chain_of_custody_ref")
    expect_error(lambda: dossier.add_entry(entry(evidence_class="clinical_validated")), "forbidden_evidence_class")
    expect_error(lambda: dossier.add_entry(entry(collected_at_utc="2026-08-20T10:00:00")), "collected_at_must_be_timezone_aware")
    print("[GV-10] Hash, redaction, raw-identity, forbidden-claim and timestamp failures are rejected: PASSED")

    dossier = build_gv10_template()
    expect_error(lambda: dossier.review_readiness(), "evidence_entries_required")
    print("[GV-10] Empty dossier cannot be submitted as independent-review input: PASSED")

    dossier = build_gv10_template()
    dossier.claim_boundary = "INDEPENDENT_REVIEW_INPUT"
    dossier.entries.append(entry())
    expect_error(lambda: dossier.review_readiness(), "dossier_claim_boundary_must_remain_unverified")
    print("[GV-10] Dossier cannot remove its UNVERIFIED claim boundary: PASSED")
    print("GV10_EVIDENCE_TESTS_PASSED")


if __name__ == "__main__":
    run()
