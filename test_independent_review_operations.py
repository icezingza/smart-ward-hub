from __future__ import annotations

from independent_review_operations import (
    ReviewFinding,
    ReviewOperationError,
    open_review_session,
)
from simulate_gv10_submission import positive_cases


TIMESTAMP = "2026-08-20T10:00:00+00:00"


def expect_error(action, expected: str) -> None:
    try:
        action()
    except ReviewOperationError as exc:
        assert str(exc) == expected, (str(exc), expected)
    else:
        raise AssertionError(f"expected {expected}")


def make_finding(*, evidence_id: str = "EV-GV10-P1001-001", gate_id: str = "GV-02", **overrides) -> ReviewFinding:
    values = {
        "finding_id": "FIND-GV10-0001",
        "gate_id": gate_id,
        "severity": "HIGH",
        "outcome": "REQUIRES_CLARIFICATION",
        "summary": "ต้องยืนยัน retention decision กับ privacy reviewer",
        "evidence_ids": (evidence_id,),
        "issued_at_utc": TIMESTAMP,
        "issued_by_role": "independent_reviewer",
    }
    values.update(overrides)
    return ReviewFinding(**values)


def run() -> None:
    session = open_review_session(
        session_id="REV-GV10-0001",
        dossier_id="smart-ward-gv10-review-v1",
        opened_at_utc=TIMESTAMP,
    )
    assert session.status == "OPEN"
    assert session.summary()["review_outcome"] == "OPEN"
    print("[P1-008] Review session open lifecycle: PASSED")

    first, second = positive_cases()[0], positive_cases()[1]
    session.accept_evidence(first)
    session.accept_evidence(second)
    assert session.summary()["accepted_evidence_count"] == 2
    print("[P1-008] Evidence acceptance and duplicate-protected registry: PASSED")

    expect_error(lambda: session.accept_evidence(first), "duplicate_accepted_evidence")
    print("[P1-008] Duplicate evidence is rejected: PASSED")

    finding = make_finding()
    session.issue_finding(finding)
    assert session.summary()["finding_count"] == 1
    assert session.summary()["finding_severity_counts"]["HIGH"] == 1
    print("[P1-008] Finding severity classification and traceability: PASSED")

    expect_error(
        lambda: session.issue_finding(make_finding(finding_id="FIND-GV10-0002", evidence_id="EV-GV10-P1005-001")),
        "finding_gate_evidence_mismatch",
    )
    expect_error(
        lambda: session.issue_finding(make_finding(finding_id="FIND-GV10-0003", evidence_id="EV-GV10-NOT-ACCEPTED-001")),
        "finding_references_unaccepted_evidence",
    )
    print("[P1-008] Finding-to-gate and finding-to-accepted-evidence boundaries: PASSED")

    expect_error(lambda: session.authorize_clinical_validation(), "clinical_authorization_requires_external_governance")
    expect_error(lambda: session.authorize_production(), "production_authorization_requires_external_governance")
    boundary = session.authorization_boundary()
    assert boundary["clinical_validation_authorized"] is False
    assert boundary["production_authorized"] is False
    assert boundary["real_world_authorization"] is False
    assert boundary["pilot_gate_status"] == "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION"
    print("[P1-008] No-authorization boundary remains locked: PASSED")

    closed = session.close(closed_at_utc=TIMESTAMP)
    assert closed["status"] == "CLOSED"
    assert closed["review_outcome"] == "CLOSED_WITH_FINDINGS"
    expect_error(lambda: session.accept_evidence(second), "review_session_closed")
    expect_error(lambda: session.issue_finding(make_finding(finding_id="FIND-GV10-0004")), "review_session_closed")
    print("[P1-008] Review close lifecycle and post-close mutation lock: PASSED")

    expect_error(
        lambda: open_review_session(
            session_id="REV-GV10-NEG-001",
            dossier_id="smart-ward-gv10-review-v1",
            reviewer_role="",
            opened_at_utc=TIMESTAMP,
        ),
        "reviewer_role_required",
    )
    empty = open_review_session(
        session_id="REV-GV10-EMPTY-001",
        dossier_id="smart-ward-gv10-review-v1",
        opened_at_utc=TIMESTAMP,
    )
    expect_error(lambda: empty.close(closed_at_utc=TIMESTAMP), "cannot_close_without_accepted_evidence")
    print("[P1-008] Empty/invalid review sessions fail closed: PASSED")

    pii_session = open_review_session(
        session_id="REV-GV10-PII-001",
        dossier_id="smart-ward-gv10-review-v1",
        opened_at_utc=TIMESTAMP,
    )
    pii_session.accept_evidence(first)
    expect_error(
        lambda: pii_session.issue_finding(make_finding(finding_id="FIND-GV10-NEG-001", summary="HN-2026-1234 appears in summary")),
        "raw_identity_in_finding_summary",
    )
    print("[P1-008] Raw identity in finding is rejected: PASSED")
    print("P1_008_INDEPENDENT_REVIEW_TESTS_PASSED")


if __name__ == "__main__":
    run()
