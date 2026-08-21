"""Focused/adversarial tests for the fixture-only sync/alert replay harness."""

from sync_alert_replay_harness import (
    AuthorizationBoundary,
    ReplayFixture,
    ReplayOperation,
    ReplayState,
    RecoveryDecision,
    RemediationCode,
    SnapshotFixture,
    SyncFixture,
    build_replay_matrix,
    evaluate_replay,
)


def test_retryable_sync_is_retained_without_resume():
    result = evaluate_replay(
        ReplayFixture(
            operation=ReplayOperation.SYNC_ATTEMPT,
            sync=SyncFixture(bundle_ref="bundle-opaque-retry-test", attempt_count=1, retry_limit=3, status_code=503),
        )
    )
    assert result.state == ReplayState.RETAINED_FOR_RETRY
    assert result.resume_permitted is False
    assert result.remediation_code == RemediationCode.SYNC_RETAINED_FOR_RETRY
    assert result.mutation_performed is False


def test_retry_limit_classifies_sync_as_dead_letter():
    result = evaluate_replay(
        ReplayFixture(
            operation=ReplayOperation.SYNC_ATTEMPT,
            sync=SyncFixture(bundle_ref="bundle-opaque-dead-test", attempt_count=3, retry_limit=3, status_code=503),
        )
    )
    assert result.state == ReplayState.DEAD_LETTER
    assert result.resume_permitted is False
    assert result.remediation_code == RemediationCode.SYNC_DEAD_LETTER


def test_dead_letter_replay_requires_confirmation_then_becomes_software_eligible():
    fixture = ReplayFixture(
        operation=ReplayOperation.DEAD_LETTER_REPLAY,
        sync=SyncFixture(bundle_ref="bundle-opaque-replay-test", attempt_count=3, retry_limit=3, dead_lettered=True),
    )
    blocked = evaluate_replay(fixture)
    assert blocked.recovery_decision == RecoveryDecision.OPERATOR_CONFIRMATION_REQUIRED
    assert blocked.replay_permitted is False
    eligible = evaluate_replay(
        ReplayFixture(
            operation=fixture.operation,
            sync=fixture.sync,
            operator_confirmation_present=True,
        )
    )
    assert eligible.recovery_decision == RecoveryDecision.SOFTWARE_REPLAY_ELIGIBLE
    assert eligible.replay_permitted is True
    assert eligible.replay_executed is False
    assert eligible.mutation_performed is False


def test_duplicate_ack_replay_is_idempotent_and_never_purges_again():
    result = evaluate_replay(
        ReplayFixture(
            operation=ReplayOperation.ACKNOWLEDGMENT_REPLAY,
            sync=SyncFixture(
                bundle_ref="bundle-opaque-ack-test",
                status_code=200,
                acknowledged=True,
                acknowledged_bundle_ref="bundle-opaque-ack-test",
                persisted_synced=True,
                acknowledgment_recorded=True,
                purged_aggregate_count=4,
            ),
        )
    )
    assert result.duplicate_safe is True
    assert result.resume_permitted is True
    assert result.remediation_code == RemediationCode.IDEMPOTENT_ACK_REPLAY
    assert result.purge_permitted is False
    assert result.purge_executed is False


def test_ack_bundle_mismatch_is_rejected_before_state_mutation():
    result = evaluate_replay(
        ReplayFixture(
            operation=ReplayOperation.ACKNOWLEDGMENT_REPLAY,
            sync=SyncFixture(
                bundle_ref="bundle-opaque-local-test",
                status_code=200,
                acknowledged_bundle_ref="bundle-opaque-other-test",
            ),
        )
    )
    assert result.resume_permitted is False
    assert result.remediation_code == RemediationCode.ACK_BUNDLE_ID_MISMATCH
    assert result.mutation_performed is False


def test_partial_purge_without_synced_marker_blocks_replay():
    result = evaluate_replay(
        ReplayFixture(
            operation=ReplayOperation.ACKNOWLEDGMENT_REPLAY,
            sync=SyncFixture(bundle_ref="bundle-opaque-partial-test", purged_aggregate_count=2),
        )
    )
    assert result.state == ReplayState.PARTIAL_WRITE_DETECTED
    assert result.resume_permitted is False
    assert result.remediation_code == RemediationCode.PARTIAL_SYNC_WRITE_DETECTED


def test_stale_snapshot_requires_authoritative_refresh():
    result = evaluate_replay(
        ReplayFixture(
            operation=ReplayOperation.SNAPSHOT_REFRESH,
            snapshot=SnapshotFixture(snapshot_ref="snapshot-opaque-stale-test", client_revision=4, authoritative_revision=5),
        )
    )
    assert result.state == ReplayState.STALE_SNAPSHOT
    assert result.refresh_required is True
    assert result.resume_permitted is False
    assert result.remediation_code == RemediationCode.STALE_SNAPSHOT_REFRESH_REQUIRED


def test_future_snapshot_revision_is_fail_closed():
    result = evaluate_replay(
        ReplayFixture(
            operation=ReplayOperation.SNAPSHOT_REFRESH,
            snapshot=SnapshotFixture(snapshot_ref="snapshot-opaque-future-test", client_revision=6, authoritative_revision=5),
        )
    )
    assert result.resume_permitted is False
    assert result.remediation_code == RemediationCode.FUTURE_SNAPSHOT_REVISION


def test_current_snapshot_has_no_refresh_mutation():
    result = evaluate_replay(
        ReplayFixture(
            operation=ReplayOperation.SNAPSHOT_REFRESH,
            snapshot=SnapshotFixture(snapshot_ref="snapshot-opaque-current-test", client_revision=5, authoritative_revision=5),
        )
    )
    assert result.resume_permitted is True
    assert result.refresh_required is False
    assert result.remediation_code == RemediationCode.SNAPSHOT_CURRENT
    assert result.mutation_performed is False


def test_authorization_boundary_mutation_fails_closed():
    result = evaluate_replay(
        ReplayFixture(
            operation=ReplayOperation.DEAD_LETTER_REPLAY,
            sync=SyncFixture(bundle_ref="bundle-opaque-auth-test", attempt_count=3, retry_limit=3, dead_lettered=True),
            authorization=AuthorizationBoundary(production_authorized=True),
        )
    )
    assert result.resume_permitted is False
    assert result.recovery_decision == RecoveryDecision.RECONCILIATION_REQUIRED
    assert result.remediation_code == RemediationCode.AUTHORIZATION_BOUNDARY_LOCKED
    assert result.authorization_boundary_locked is False


def test_raw_identity_like_fixture_is_rejected_and_not_returned():
    result = evaluate_replay(
        ReplayFixture(
            operation=ReplayOperation.SNAPSHOT_REFRESH,
            snapshot=SnapshotFixture(snapshot_ref="HN-2026-8901", client_revision=1, authoritative_revision=2),
        )
    )
    assert result.resume_permitted is False
    assert result.remediation_code == RemediationCode.INVALID_FIXTURE
    assert result.opaque_refs == {}


def test_matrix_rows_are_complete_and_read_only():
    rows = build_replay_matrix()
    assert len(rows) == 10
    for row in rows:
        assert row.scenario_id
        assert isinstance(row.resume_permitted, bool)
        assert row.mutation_performed is False
        assert row.purge_executed is False
        assert row.replay_executed is False
        assert row.authorization_boundary_locked is True


def run() -> None:
    tests = [
        value for name, value in globals().items()
        if name.startswith("test_") and callable(value)
    ]
    for test in tests:
        test()
    print(f"[Replay] focused/adversarial tests: {len(tests)} PASSED")
    print("SYNC_ALERT_REPLAY_HARNESS_TESTS_PASSED")


if __name__ == "__main__":
    run()
