from __future__ import annotations

from copy import deepcopy
from dataclasses import replace

from gv10_evidence import EvidenceEntry
from p1_008_independent_review_readiness import (
    IndependentReviewReadinessError,
    template,
    validate_manifest,
)
from simulate_gv10_submission import positive_cases
from independent_review_operations import ReviewFinding, ReviewOperationError, open_review_session


TIMESTAMP = "2026-08-20T10:00:00+00:00"


def expect_review_error(action, expected: str) -> None:
    try:
        action()
    except ReviewOperationError as exc:
        assert str(exc) == expected, (str(exc), expected)
    else:
        raise AssertionError(f"expected review error: {expected}")


def expect_readiness_error(action, fragment: str) -> None:
    try:
        action()
    except IndependentReviewReadinessError as exc:
        assert fragment in str(exc), (str(exc), fragment)
    else:
        raise AssertionError(f"expected readiness error containing: {fragment}")


def make_finding(**overrides) -> ReviewFinding:
    values = {
        "finding_id": "FIND-GV10-ADV-001",
        "gate_id": "GV-02",
        "severity": "HIGH",
        "outcome": "REQUIRES_CLARIFICATION",
        "summary": "ต้องทบทวน retention decision กับ privacy reviewer",
        "evidence_ids": ("EV-GV10-P1001-001",),
        "issued_at_utc": TIMESTAMP,
        "issued_by_role": "independent_reviewer",
    }
    values.update(overrides)
    return ReviewFinding(**values)


def build_session():
    session = open_review_session(
        session_id="REV-GV10-ADV-001",
        dossier_id="smart-ward-gv10-review-v1",
        opened_at_utc=TIMESTAMP,
    )
    first, second = positive_cases()[0], positive_cases()[1]
    session.accept_evidence(first)
    session.accept_evidence(second)
    return session, first, second


def run() -> None:
    # Session identity, type, timestamp and authorization-field confusion.
    expect_review_error(
        lambda: open_review_session(session_id=None, dossier_id="smart-ward-gv10-review-v1", opened_at_utc=TIMESTAMP),
        "unsafe_session_id",
    )
    expect_review_error(
        lambda: open_review_session(session_id="REV-GV10-ADV-002", dossier_id=123, opened_at_utc=TIMESTAMP),
        "unsafe_dossier_id",
    )
    expect_review_error(
        lambda: open_review_session(session_id="REV-GV10-ADV-003", dossier_id="smart-ward-gv10-review-v1", opened_at_utc="2026-08-20T10:00:00"),
        "opened_timestamp_must_be_timezone_aware",
    )
    expect_review_error(
        lambda: open_review_session(session_id="REV-GV10-ADV-004", dossier_id="smart-ward-gv10-review-v1", reviewer_role="reviewer@example.com", opened_at_utc=TIMESTAMP),
        "reviewer_role_required",
    )
    session, first, second = build_session()
    session.clinical_validation_authorized = True
    expect_review_error(session.validate, "clinical_authorization_forbidden")
    session.clinical_validation_authorized = False
    session.production_authorized = 1
    expect_review_error(session.validate, "production_authorization_forbidden")
    session.production_authorized = False
    session.real_world_authorization = True
    expect_review_error(session.validate, "real_world_authorization_forbidden")
    session.real_world_authorization = False
    session.pilot_gate_status = "AUTHORIZED"
    expect_review_error(session.validate, "pilot_gate_authorization_forbidden")
    session.pilot_gate_status = "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION"
    print("[P1-008 ADV] Session identity/type/timestamp/authorization mutations: PASSED")

    # Finding vocabulary, traceability, and unsafe content.
    expect_review_error(lambda: session.issue_finding(make_finding(finding_id="FIND-GV10-ADV-002", severity=None)), "invalid_finding_severity")
    expect_review_error(lambda: session.issue_finding(make_finding(finding_id="FIND-GV10-ADV-003", outcome=None)), "invalid_finding_outcome")
    expect_review_error(lambda: session.issue_finding(make_finding(finding_id="FIND-GV10-ADV-004", evidence_ids="EV-GV10-P1001-001")), "finding_evidence_trace_required")
    expect_review_error(lambda: session.issue_finding(make_finding(finding_id="FIND-GV10-ADV-005", evidence_ids=("EV-GV10-P1001-001", "EV-GV10-P1001-001"))), "duplicate_finding_evidence_id")
    expect_review_error(lambda: session.issue_finding(make_finding(finding_id="FIND-GV10-ADV-006", summary="contact reviewer@example.com")), "raw_contact_in_finding_summary")
    expect_review_error(lambda: session.issue_finding(make_finding(finding_id="FIND-GV10-ADV-007", summary="Bearer test-secret")), "secret_marker_in_finding_summary")
    expect_review_error(lambda: session.issue_finding(make_finding(finding_id="FIND-GV10-ADV-008", issued_by_role="HN-2026-1234")), "finding_issuer_role_required")
    print("[P1-008 ADV] Finding severity/outcome/traceability/content mutations: PASSED")

    # Evidence registry type/key/gate binding mutations.
    session.accepted_evidence["EV-GV10-ADV-KEY-001"] = first
    expect_review_error(session.validate, "accepted_evidence_key_mismatch")
    del session.accepted_evidence["EV-GV10-ADV-KEY-001"]
    session.accepted_evidence["EV-GV10-ADV-TYPE-001"] = "not-an-evidence-entry"
    expect_review_error(session.validate, "invalid_accepted_evidence_record")
    del session.accepted_evidence["EV-GV10-ADV-TYPE-001"]
    expect_review_error(lambda: session.issue_finding(make_finding(finding_id="FIND-GV10-ADV-009", gate_id="GV-09")), "finding_gate_evidence_mismatch")
    expect_review_error(lambda: session.issue_finding(make_finding(finding_id="FIND-GV10-ADV-010", evidence_ids=("EV-GV10-NOT-ACCEPTED-001",))), "finding_references_unaccepted_evidence")
    print("[P1-008 ADV] Evidence registry/key/type/gate mismatch mutations: PASSED")

    # Close then mutate through direct references; fingerprint must fail closed.
    close_session, _, close_second = build_session()
    close_session.issue_finding(make_finding(finding_id="FIND-GV10-ADV-CLOSE-001"))
    close_session.close(closed_at_utc=TIMESTAMP)
    close_session.accepted_evidence.pop(close_second.evidence_id)
    expect_review_error(close_session.summary, "closed_review_state_mutated")

    close_session_2, _, _ = build_session()
    close_session_2.close(closed_at_utc=TIMESTAMP)
    close_session_2.status = "OPEN"
    expect_review_error(close_session_2.summary, "closed_review_state_mutated")
    print("[P1-008 ADV] Post-close registry and lifecycle mutation lock: PASSED")

    # Authorization methods are never a software-controlled elevation path.
    auth_session, _, _ = build_session()
    expect_review_error(auth_session.authorize_clinical_validation, "clinical_authorization_requires_external_governance")
    expect_review_error(auth_session.authorize_production, "production_authorization_requires_external_governance")
    expect_review_error(auth_session.authorize_pilot, "pilot_authorization_requires_external_governance")
    print("[P1-008 ADV] Clinical/production/pilot elevation attempts: PASSED")

    # Readiness manifest positive template and non-template external evidence shape.
    manifest = template()
    assert validate_manifest(manifest, template_only=True)["valid"] is True
    completed_shape = deepcopy(manifest)
    completed_shape["review_session_ref"] = "review:REV-GV10-ADV-001"
    completed_shape["dossier_ref"] = "dossier:GV10-ADV-001"
    completed_shape["findings_export_ref"] = "export:FINDINGS-ADV-001"
    completed_shape["rollback_ref"] = "rollback:P1-008-ADV-001"
    for track in completed_shape["tracks"].values():
        track["external_evidence_refs"] = ["evidence:external-review-pending-001"]
    assert validate_manifest(completed_shape, template_only=False)["valid"] is True
    print("[P1-008 ADV] Readiness template and external evidence separation: PASSED")

    # Readiness claim/track/authorization tampering.
    mutations = [
        ("schema_version", "wrong-schema", "schema_version mismatch"),
        ("status", "PRODUCTION_READY", "status must remain software review ready"),
        ("software_evidence_only", False, "software_evidence_only must be true"),
        ("pilot_gate_status", "AUTHORIZED", "pilot gate must remain blocked"),
        ("claim_boundary", "PRODUCTION_READY", "claim boundary mismatch"),
    ]
    for field, value, fragment in mutations:
        mutated = deepcopy(manifest)
        mutated[field] = value
        expect_readiness_error(lambda mutated=mutated: validate_manifest(mutated, template_only=True), fragment)

    unknown = deepcopy(manifest)
    unknown["unexpected"] = "reject"
    expect_readiness_error(lambda: validate_manifest(unknown, template_only=True), "unknown fields")

    track_mutation = deepcopy(manifest)
    track_mutation["tracks"]["IR-003"]["software_status"] = "EXTERNAL_VERIFIED"
    expect_readiness_error(lambda: validate_manifest(track_mutation, template_only=True), "tracks.IR-003.software_status mismatch")

    identity_mutation = deepcopy(manifest)
    identity_mutation["tracks"]["IR-002"]["stop_condition"] = "HN-2026-1234 must stop"
    expect_readiness_error(lambda: validate_manifest(identity_mutation, template_only=True), "tracks.IR-002.stop_condition must not contain raw identity")

    external_mutation = deepcopy(completed_shape)
    external_mutation["tracks"]["IR-001"]["external_evidence_refs"] = ["evidence:HN-2026-1234"]
    expect_readiness_error(lambda: validate_manifest(external_mutation, template_only=False), "must not contain raw identity/contact")
    print("[P1-008 ADV] Readiness claim/track/authorization tamper resistance: PASSED")

    print("P1_008_INDEPENDENT_REVIEW_HARDENING_PASSED")


if __name__ == "__main__":
    run()
