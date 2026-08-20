from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from external_authorization_api_simulator import (
    SimulatedExternalAuthorizationApi,
    SimulationApiError,
    load_wave0_package,
)


ROOT = Path(__file__).resolve().parent
PACKAGE = load_wave0_package(ROOT / "evals/micro_rag/evidence/wave0-governance-handoff-20260820.json")
PACKAGE_ID = PACKAGE.get("package_id") or PACKAGE["validation"]["package_id"]
BASE_REQUEST = {
    "submission_idempotency_key": "test-submit-v2-001",
    "package_id": PACKAGE_ID,
    "manifest_version": PACKAGE["freeze"]["manifest_version"],
    "manifest_sha256": PACKAGE["freeze"]["manifest_sha256"],
    "scope_id": PACKAGE["freeze"]["scope_id"],
    "window_id": PACKAGE["freeze"]["window_id"],
    "artifact_refs": ["repo://WAVE_0_GOVERNANCE_HANDOFF_REPORT.md"],
    "submitted_by_role": "evidence_custodian",
    "claim_boundary": "SOFTWARE_VERIFIED_AND_SIMULATION_ONLY; external authorization remains pending",
    "external_verification_required": True,
    "submitted_at": "2026-08-20T08:00:00+00:00",
    "contract_version": "external-auth-sim-v2",
    "request_correlation_id": "corr-test-v2-001",
}


class FixedClock:
    def __init__(self, value: datetime):
        self.value = value

    def __call__(self) -> datetime:
        return self.value


def api(clock: FixedClock | None = None, *, skew: timedelta | None = None) -> SimulatedExternalAuthorizationApi:
    return SimulatedExternalAuthorizationApi(PACKAGE, clock=clock or FixedClock(datetime(2026, 8, 20, 8, 0, tzinfo=timezone.utc)), allowed_clock_skew=skew)


def expect_code(action, code: str) -> None:
    try:
        action()
    except SimulationApiError as exc:
        assert exc.code == code, (exc.code, code)
    else:
        raise AssertionError(f"expected {code}")


def finding(finding_id: str = "test-finding-v2-001", severity: str = "HIGH") -> dict:
    return {
        "finding_id": finding_id,
        "severity": severity,
        "category": "MISSING_EXTERNAL_GOVERNANCE",
        "summary": "External appointment remains pending verification.",
        "evidence_refs": ["repo://WAVE_0_GOVERNANCE_HANDOFF_REPORT.md"],
        "required_action": "Provide external appointment and signed scope.",
        "reviewer_role": "independent_reviewer",
        "reviewer_identity_ref": "external-reviewer-ref-test",
        "external_verification_status": "PENDING_EXTERNAL_VERIFICATION",
    }


def main() -> int:
    fixed = FixedClock(datetime(2026, 8, 20, 8, 0, tzinfo=timezone.utc))
    service = api(fixed)
    received = service.submit(BASE_REQUEST)
    assert received["status"] == "RECEIVED_FOR_SIMULATION"
    assert received["simulation"] is True
    assert received["external_authority"] == "NONE"
    assert received["clinical_validation_authorized"] is False
    assert received["production_authorized"] is False
    assert received["runtime_authority"] == "NONE"

    snapshot = service.submissions[received["submission_id"]]
    snapshot["status"] = "AUTHORIZED_BY_EXTERNAL_OWNER"
    assert service.submissions[received["submission_id"]]["status"] == "RECEIVED_FOR_SIMULATION"

    repeated = service.submit(dict(BASE_REQUEST))
    assert repeated["submission_id"] == received["submission_id"]
    assert repeated["reconciled"] is True
    assert repeated["audit_event_id"] is None

    expect_code(lambda: service.start_review(received["submission_id"], "2026-08-20T08:01:00"), "REJECTED_TIMEZONE_REQUIRED")
    assert service.submissions[received["submission_id"]]["status"] == "RECEIVED_FOR_SIMULATION"
    assert service.audit()["event_count"] == 1

    review = service.start_review(received["submission_id"], "2026-08-20T08:01:00+00:00")
    assert review["status"] == "IN_SIMULATED_REVIEW"
    expect_code(lambda: service.issue_finding(received["submission_id"], finding(), "2026-08-20T08:02:00"), "REJECTED_TIMEZONE_REQUIRED")
    assert service.submissions[received["submission_id"]]["status"] == "IN_SIMULATED_REVIEW"
    finding_response = service.issue_finding(received["submission_id"], finding(), "2026-08-20T08:02:00+00:00")
    assert finding_response["status"] == "REQUIRES_CLARIFICATION"
    resolved = service.resolve_clarification(received["submission_id"], "2026-08-20T08:03:00+00:00")
    assert resolved["status"] == "IN_SIMULATED_REVIEW"
    pending = service.mark_decision_pending(received["submission_id"], "sim-decision-test-001", "2026-08-20T08:30:00+00:00", "2026-08-20T08:04:00+00:00")
    assert pending["status"] == "DECISION_PENDING_EXTERNAL_VERIFICATION"
    revision_before_expiry = pending["revision"]
    poll = service.poll(received["submission_id"], "2026-08-20T08:05:00+00:00", known_revision=revision_before_expiry, known_event_hash=pending["source_event_hash"])
    assert poll["status"] == "DECISION_PENDING_EXTERNAL_VERIFICATION"
    assert poll["revision"] == revision_before_expiry
    fixed.value = datetime(2026, 8, 20, 8, 31, tzinfo=timezone.utc)
    expired = service.poll(received["submission_id"], "2026-08-20T08:31:00+00:00")
    assert expired["status"] == "DECISION_EXPIRED"
    expect_code(lambda: service.mark_decision_pending(received["submission_id"], "sim-decision-test-002", "2026-08-20T09:00:00+00:00", "2026-08-20T08:32:00+00:00"), "REJECTED_INVALID_STATE")

    stale_service = api()
    stale = stale_service.submit({**BASE_REQUEST, "submission_idempotency_key": "stale-submit"})
    expect_code(lambda: stale_service.poll(stale["submission_id"], "2026-08-20T08:01:00+00:00", known_revision=1), "STALE_RESPONSE_REJECTED")
    expect_code(lambda: stale_service.poll(stale["submission_id"], "2026-08-20T08:01:00+00:00", known_revision=0, known_event_hash="0" * 64), "STALE_RESPONSE_REJECTED")
    expect_code(lambda: stale_service.poll("unknown-submission", "2026-08-20T08:01:00+00:00"), "REJECTED_UNKNOWN_SUBMISSION")

    revoke_service = api()
    revoked = revoke_service.submit({**BASE_REQUEST, "submission_idempotency_key": "revoke-submit"})
    revoke_service.start_review(revoked["submission_id"], "2026-08-20T08:01:00+00:00")
    revoke_service.mark_decision_pending(revoked["submission_id"], "sim-decision-revoke-001", "2026-08-20T09:00:00+00:00", "2026-08-20T08:02:00+00:00")
    revoked_response = revoke_service.revoke_decision(revoked["submission_id"], "sim-decision-revoke-001", "external review withdrawn", "2026-08-20T08:03:00+00:00")
    assert revoked_response["status"] == "DECISION_REVOKED"
    expect_code(lambda: revoke_service.revoke_decision(revoked["submission_id"], "sim-decision-revoke-001", "duplicate", "2026-08-20T08:04:00+00:00"), "REJECTED_INVALID_STATE")

    uncertain_service = api()
    uncertain_request = {**BASE_REQUEST, "submission_idempotency_key": "uncertain-submit"}
    try:
        uncertain_service.submit_with_delivery_fault(uncertain_request, "AFTER_COMMIT_BEFORE_RESPONSE")
    except SimulationApiError as exc:
        assert exc.code == "COMMIT_UNKNOWN"
        details = json_load(exc.message)
    else:
        raise AssertionError("expected COMMIT_UNKNOWN")
    reconciled = uncertain_service.reconcile_submission(uncertain_request["submission_idempotency_key"], details["request_hash"], "2026-08-20T08:01:00+00:00")
    assert reconciled["reconciled"] is True
    assert reconciled["submission_id"] == details["submission_id"]

    atomic_service = api()
    atomic = atomic_service.submit({**BASE_REQUEST, "submission_idempotency_key": "atomic-submit"})
    atomic_service.start_review(atomic["submission_id"], "2026-08-20T08:01:00+00:00")
    expect_code(lambda: atomic_service.issue_finding(atomic["submission_id"], finding("atomic-finding"), "2026-08-20T08:02:00"), "REJECTED_TIMEZONE_REQUIRED")
    assert atomic_service.submissions[atomic["submission_id"]]["finding_count"] == 0
    assert atomic_service.submissions[atomic["submission_id"]]["status"] == "IN_SIMULATED_REVIEW"

    tamper_service = api()
    tampered = tamper_service.submit({**BASE_REQUEST, "submission_idempotency_key": "tamper-submit"})
    tamper_service.inject_audit_tamper_for_test()
    assert tamper_service.audit()["chain_valid"] is False
    expect_code(lambda: tamper_service.start_review(tampered["submission_id"], "2026-08-20T08:01:00+00:00"), "AUDIT_INTEGRITY_FAILURE")
    expect_code(lambda: tamper_service.submit({**BASE_REQUEST, "submission_idempotency_key": "tamper-submit-2"}), "AUDIT_INTEGRITY_FAILURE")

    expect_code(lambda: service.submit({**BASE_REQUEST, "submission_idempotency_key": "bad-type", "artifact_refs": "not-a-list"}), "REJECTED_INVALID_ARTIFACT_REFS")
    expect_code(lambda: service.submit({**BASE_REQUEST, "submission_idempotency_key": "bad-field", "unexpected": "reject"}), "REJECTED_UNKNOWN_FIELD")
    expect_code(lambda: service.submit({**BASE_REQUEST, "submission_idempotency_key": "bad-hash", "manifest_sha256": "0" * 10}), "REJECTED_INVALID_MANIFEST_HASH")
    expect_code(lambda: service.submit({**BASE_REQUEST, "submission_idempotency_key": "bad-auth", "clinical_validation_authorized": True}), "REJECTED_AUTHORIZATION_ESCALATION")
    expect_code(lambda: service.submit({**BASE_REQUEST, "submission_idempotency_key": "bad-time", "submitted_at": "2026-08-20T08:00:00"}), "REJECTED_TIMEZONE_REQUIRED")
    expect_code(lambda: service.issue_finding(received["submission_id"], finding("bad-severity", "URGENT"), "2026-08-20T08:40:00+00:00"), "REJECTED_INVALID_STATE")

    skew_service = api(FixedClock(datetime(2026, 8, 20, 8, 0, tzinfo=timezone.utc)), skew=timedelta(minutes=5))
    expect_code(lambda: skew_service.submit({**BASE_REQUEST, "submission_idempotency_key": "skew-submit", "submitted_at": "2026-08-20T09:00:00+00:00"}), "CLOCK_SKEW_EXCEEDED")

    for event in service.audit()["events"]:
        assert event["simulation"] is True
        assert event["external_authority"] == "NONE"
    print("EXTERNAL_AUTHORIZATION_API_SIMULATOR_V2_TESTS_PASSED")
    return 0


def json_load(value: str) -> dict:
    import json

    return json.loads(value)


if __name__ == "__main__":
    raise SystemExit(main())
