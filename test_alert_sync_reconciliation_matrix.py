"""Focused/adversarial tests for the alert/sync reconciliation matrix."""

from alert_sync_reconciliation_matrix import (
    AlertObservation,
    AuthorizationObservation,
    Operation,
    RecoveryDecision,
    RemediationCode,
    ReconciliationObservation,
    RoamingObservation,
    SyncObservation,
    build_reconciliation_matrix,
    evaluate_reconciliation,
)


def test_acknowledged_alert_allows_monitoring_resume_without_exposing_raw_ref():
    result = evaluate_reconciliation(
        ReconciliationObservation(
            operation=Operation.MONITORING_RESUME,
            alert=AlertObservation(
                alert_ref="alert-opaque-ack-001",
                session_ref="session-opaque-001",
                acknowledged=True,
            ),
        )
    )
    assert result.resume_permitted is True
    assert result.recovery_decision == RecoveryDecision.SOFTWARE_RESUME_ELIGIBLE
    assert result.remediation_code == RemediationCode.ACKNOWLEDGED_ALERT_MONITORING_RESUME
    assert "alert-opaque-ack-001" not in str(result.to_dict())
    assert "session-opaque-001" not in str(result.to_dict())
    assert result.authorization_boundary_locked is True


def test_unresolved_alert_blocks_reset_even_when_acknowledged():
    result = evaluate_reconciliation(
        ReconciliationObservation(
            operation=Operation.RESET,
            session_status="ACTIVE",
            alert=AlertObservation(
                alert_ref="alert-opaque-open-001",
                session_ref="session-opaque-002",
                acknowledged=True,
                resolved=False,
            ),
        )
    )
    assert result.resume_permitted is False
    assert result.recovery_decision == RecoveryDecision.RECONCILIATION_REQUIRED
    assert result.remediation_code == RemediationCode.UNRESOLVED_ALERT_BLOCKS_RESET


def test_incident_frozen_without_forensic_package_blocks_reset():
    result = evaluate_reconciliation(
        ReconciliationObservation(
            operation=Operation.RESET,
            session_status="INCIDENT_FROZEN",
            alert=AlertObservation(
                alert_ref="alert-opaque-red-001",
                session_ref="session-opaque-003",
                incident_frozen=True,
                forensic_package_present=False,
            ),
        )
    )
    assert result.resume_permitted is False
    assert result.remediation_code == RemediationCode.FORENSIC_PACKAGE_REQUIRED


def test_sync_acknowledgment_allows_bounded_software_resume():
    result = evaluate_reconciliation(
        ReconciliationObservation(
            operation=Operation.SYNC_RETRY,
            sync=SyncObservation(
                bundle_ref="bundle-opaque-ack-001",
                attempt_count=1,
                retry_limit=3,
                last_status_code=200,
                acknowledged=True,
            ),
        )
    )
    assert result.resume_permitted is True
    assert result.remediation_code == RemediationCode.SYNC_ACKNOWLEDGED


def test_sync_retry_limit_exceeded_becomes_dead_letter():
    result = evaluate_reconciliation(
        ReconciliationObservation(
            operation=Operation.SYNC_RETRY,
            sync=SyncObservation(
                bundle_ref="bundle-opaque-dead-001",
                attempt_count=3,
                retry_limit=3,
                last_status_code=503,
            ),
        )
    )
    assert result.resume_permitted is False
    assert result.recovery_decision == RecoveryDecision.RECONCILIATION_REQUIRED
    assert result.remediation_code == RemediationCode.SYNC_DEAD_LETTER


def test_stale_sync_revision_is_not_retried_as_transport_failure():
    result = evaluate_reconciliation(
        ReconciliationObservation(
            operation=Operation.SYNC_RETRY,
            sync=SyncObservation(
                bundle_ref="bundle-opaque-stale-001",
                attempt_count=1,
                retry_limit=3,
                last_status_code=409,
                stale_revision=True,
            ),
        )
    )
    assert result.resume_permitted is False
    assert result.remediation_code == RemediationCode.STALE_REVISION_409


def test_stale_roaming_command_is_rejected():
    result = evaluate_reconciliation(
        ReconciliationObservation(
            operation=Operation.ROAMING_COMMAND,
            roaming=RoamingObservation(
                command_ref="command-opaque-stale-001",
                expected_revision=7,
                current_revision=8,
            ),
        )
    )
    assert result.resume_permitted is False
    assert result.recovery_decision == RecoveryDecision.RECONCILIATION_REQUIRED
    assert result.remediation_code == RemediationCode.STALE_REVISION_409


def test_idempotent_committed_roaming_replay_is_safe_to_represent():
    result = evaluate_reconciliation(
        ReconciliationObservation(
            operation=Operation.ROAMING_COMMAND,
            roaming=RoamingObservation(
                command_ref="command-opaque-replay-001",
                expected_revision=8,
                current_revision=8,
                idempotency_replay=True,
                existing_status="COMMITTED",
            ),
        )
    )
    assert result.resume_permitted is True
    assert result.remediation_code == RemediationCode.IDEMPOTENT_REPLAY


def test_authorization_boundary_mutation_fails_closed():
    result = evaluate_reconciliation(
        ReconciliationObservation(
            operation=Operation.MONITORING_RESUME,
            alert=AlertObservation(acknowledged=True),
            authorization=AuthorizationObservation(production_authorized=True),
        )
    )
    assert result.resume_permitted is False
    assert result.recovery_decision == RecoveryDecision.RECONCILIATION_REQUIRED
    assert result.remediation_code == RemediationCode.AUTHORIZATION_BOUNDARY_LOCKED
    assert result.authorization_boundary_locked is False


def test_raw_identity_like_reference_is_rejected_and_redacted_fail_closed():
    result = evaluate_reconciliation(
        ReconciliationObservation(
            operation=Operation.MONITORING_RESUME,
            alert=AlertObservation(alert_ref="alert-opaque-001", session_ref="HN-2026-8901"),
        )
    )
    assert result.resume_permitted is False
    assert result.remediation_code == RemediationCode.INVALID_OBSERVATION
    assert result.opaque_refs == {}


def test_invalid_resolved_alert_cannot_be_treated_as_safe():
    result = evaluate_reconciliation(
        ReconciliationObservation(
            operation=Operation.MONITORING_RESUME,
            alert=AlertObservation(resolved=True, acknowledged=False),
        )
    )
    assert result.resume_permitted is False
    assert result.remediation_code == RemediationCode.INVALID_OBSERVATION


def test_matrix_is_deterministic_and_contains_required_decision_fields():
    rows = build_reconciliation_matrix()
    assert len(rows) == 8
    for row in rows:
        assert row.scenario_id
        assert isinstance(row.resume_permitted, bool)
        assert row.recovery_decision in {item.value for item in RecoveryDecision}
        assert row.remediation_code in {item.value for item in RemediationCode}
        assert row.authorization_boundary_locked is True


def run() -> None:
    tests = [
        value for name, value in globals().items()
        if name.startswith("test_") and callable(value)
    ]
    for test in tests:
        test()
    print(f"[AlertSync] focused/adversarial tests: {len(tests)} PASSED")
    print("ALERT_SYNC_RECONCILIATION_MATRIX_TESTS_PASSED")


if __name__ == "__main__":
    run()
