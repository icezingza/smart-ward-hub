from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone

from external_decision_lifecycle import (
    BLOCKED_SIMULATION,
    DECISION_EXPIRED,
    DECISION_REVOKED,
    DecisionLifecycle,
    DecisionLifecycleError,
    PENDING_EXTERNAL_VERIFICATION,
    RECEIVED_FOR_SIMULATION,
    REQUIRES_CLARIFICATION,
    RESUBMISSION_REQUIRED,
    STALE_RESPONSE_REJECTED,
)
from test_external_decision_record import received_record


NOW = datetime(2026, 8, 21, 10, 30, tzinfo=timezone.utc)


def expect_error(callback, label: str) -> None:
    try:
        callback()
    except DecisionLifecycleError:
        print(f"[Decision Lifecycle] {label}: PASSED")
        return
    raise AssertionError(f"{label}: unsafe lifecycle action was accepted")


def poll_response(lifecycle: DecisionLifecycle, *, revision: int = 1, status: str = "PENDING_EXTERNAL_VERIFICATION", observed: str = "2026-08-21T10:30:00Z", event_hash: str = "2" * 64) -> dict:
    return {
        "decision_id": lifecycle.decision_id,
        "source_revision": revision,
        "source_event_hash": event_hash,
        "source_status": status,
        "observed_at_utc": observed,
        "clock_source_ref": "clock:test-fixture",
    }


def new_lifecycle(expires: str = "2026-08-21T11:00:00Z") -> DecisionLifecycle:
    record = received_record()
    record["expires_at"] = expires
    return DecisionLifecycle(record, now=NOW)


def run() -> None:
    lifecycle = new_lifecycle()
    assert lifecycle.state == PENDING_EXTERNAL_VERIFICATION
    assert lifecycle.audit_chain_valid() is True
    assert lifecycle.status(now=NOW)["authorization_promoted"] is False
    print("[Decision Lifecycle] initialization and audit chain: PASSED")

    before = lifecycle.revision
    poll_result = lifecycle.poll(poll_response(lifecycle), now=NOW)
    assert poll_result["result"] == "POLL_ACCEPTED_UNVERIFIED"
    assert lifecycle.revision == before
    assert lifecycle.state == PENDING_EXTERNAL_VERIFICATION
    assert poll_result["trusted"] is False
    print("[Decision Lifecycle] poll is read-only and unverified: PASSED")

    stale = lifecycle.poll(poll_response(lifecycle, revision=0, observed="2026-08-21T09:00:00Z"), now=NOW, known_revision=1)
    assert stale["result"] == STALE_RESPONSE_REJECTED
    assert lifecycle.revision == before
    print("[Decision Lifecycle] stale poll is rejected without mutation: PASSED")

    future = lifecycle.poll(poll_response(lifecycle, observed="2026-08-21T10:32:00Z"), now=NOW)
    assert future["result"] == STALE_RESPONSE_REJECTED
    print("[Decision Lifecycle] future-dated poll is rejected: PASSED")

    clarification = lifecycle.apply_external_update(
        poll_response(lifecycle, revision=1, status="REQUIRES_CLARIFICATION"),
        now=NOW,
        reason_ref="reason:clarification",
    )
    assert clarification["state"] == REQUIRES_CLARIFICATION
    assert clarification["authorization_promoted"] is False
    print("[Decision Lifecycle] external clarification transition: PASSED")

    lifecycle = new_lifecycle()
    revoked = lifecycle.revoke(now=NOW, reason_ref="reason:revoked", actor_role="external_authority")
    assert revoked["state"] == DECISION_REVOKED
    assert revoked["authorization_promoted"] is False
    expect_error(lambda: lifecycle.revoke(now=NOW, reason_ref="reason:replay", actor_role="external_authority"), "terminal revoke replay")
    expect_error(lambda: new_lifecycle().revoke(now=NOW, reason_ref="reason:bad", actor_role="local_evaluator"), "local revoke authority")
    print("[Decision Lifecycle] revocation is terminal and role-bound: PASSED")

    lifecycle = new_lifecycle(expires="2026-08-21T10:30:00Z")
    expired = lifecycle.expire(now=NOW)
    assert expired["state"] == DECISION_EXPIRED
    assert expired["expired"] is True
    print("[Decision Lifecycle] now-at-expiry transitions to DECISION_EXPIRED: PASSED")

    resubmission = lifecycle.request_resubmission(now=NOW + timedelta(minutes=1), reason_ref="reason:new-submission")
    assert resubmission["state"] == RESUBMISSION_REQUIRED
    print("[Decision Lifecycle] expired decision requires resubmission: PASSED")

    received = lifecycle.receive_for_simulation(now=NOW + timedelta(minutes=2), reason_ref="reason:resubmitted")
    assert received["state"] == RECEIVED_FOR_SIMULATION
    pending = lifecycle.begin_pending_review(now=NOW + timedelta(minutes=3), reason_ref="reason:review")
    assert pending["state"] == PENDING_EXTERNAL_VERIFICATION
    print("[Decision Lifecycle] resubmission path returns to pending review: PASSED")

    blocked = new_lifecycle().block(now=NOW, reason_ref="reason:integrity")
    assert blocked["state"] == BLOCKED_SIMULATION
    reopened = lifecycle = DecisionLifecycle(received_record(), now=NOW)
    blocked = reopened.block(now=NOW, reason_ref="reason:integrity")
    reopened_result = reopened.reopen(now=NOW + timedelta(minutes=1), reason_ref="reason:operator-review", actor_role="stop_authority")
    assert reopened_result["state"] == "REOPENED_WITH_REASON"
    expect_error(lambda: reopened.reopen(now=NOW, reason_ref="reason:bad-role", actor_role="local_evaluator"), "reopen role separation")
    print("[Decision Lifecycle] blocked/reopen separation: PASSED")

    lifecycle = new_lifecycle()
    remote = lifecycle.apply_external_update(
        poll_response(lifecycle, revision=1, status="REVOKED"),
        now=NOW,
        reason_ref="reason:external-revocation",
    )
    assert remote["state"] == DECISION_REVOKED
    assert remote["external_execution_authorized"] is False
    assert remote["clinical_validation_authorized"] is False
    print("[Decision Lifecycle] remote revocation invalidates local pending state: PASSED")

    lifecycle = new_lifecycle()
    previous = lifecycle.revision
    expect_error(lambda: lifecycle.apply_external_update(poll_response(lifecycle, revision=1), now=NOW, reason_ref="unsafe", actor_role="external_authority"), "unsafe reason reference")
    assert lifecycle.revision == previous
    expect_error(lambda: lifecycle.apply_external_update(poll_response(lifecycle, revision=1), now=NOW, reason_ref="reason:bad-role", actor_role="local_evaluator"), "local external-update authority")

    snapshot = lifecycle.snapshot()
    snapshot["events"][0]["to_state"] = "AUTHORIZED_BY_EXTERNAL_OWNER"
    assert lifecycle.state == PENDING_EXTERNAL_VERIFICATION
    assert lifecycle.audit_chain_valid() is True
    print("[Decision Lifecycle] returned snapshot mutation does not alter private state: PASSED")

    expect_error(lambda: DecisionLifecycle(received_record(), now=datetime(2026, 8, 21, 10, 30)), "naive evaluator clock")
    expect_error(lambda: DecisionLifecycle(received_record(), now=NOW, stale_ttl_seconds=0), "invalid stale TTL")
    print("DECISION_LIFECYCLE_TESTS_PASSED")


if __name__ == "__main__":
    run()
