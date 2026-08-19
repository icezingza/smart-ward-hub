from __future__ import annotations

from datetime import datetime, timedelta, timezone

from clinical_shadow_mode import ShadowModeController, ShadowModeError, ShadowModePolicy, ShadowReview, ShadowSignal


NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
TOKEN = "ptok-shadow-negative-0001"


def expect_error(action, expected: str) -> None:
    try:
        action()
    except ShadowModeError as exc:
        assert str(exc) == expected, (str(exc), expected)
    else:
        raise AssertionError(f"expected {expected}")


def policy(**overrides) -> ShadowModePolicy:
    values = {
        "clinical_owner": "clinical-owner",
        "technical_owner": "technical-owner",
        "privacy_security_reviewer": "privacy-reviewer",
        "ward_manager": "ward-manager",
        "incident_contact": "incident-contact",
        "backup_restore_evidence": True,
        "device_inventory": True,
        "training_note": True,
        "data_retention_decision": True,
        "rollback_plan": True,
        "approval_id": "CLIN-APPROVAL-NEG-001",
        "notifications_enabled": False,
    }
    values.update(overrides)
    return ShadowModePolicy(**values)


def build_signal(alert_id: str, **overrides) -> ShadowSignal:
    values = {
        "alert_id": alert_id,
        "signal_type": "suspected fall",
        "patient_token": TOKEN,
        "device_id": "MAC-SHADOW-NEG-01",
        "bed_no": "W04-B12",
        "event_time": NOW,
        "received_at": NOW + timedelta(seconds=5),
        "context": "bounded non-PII context",
    }
    values.update(overrides)
    return ShadowSignal(**values)


def run() -> None:
    controller = ShadowModeController()
    expect_error(
        lambda: controller.activate(policy(notifications_enabled=True, notification_approval_id="NOTIFY-001")),
        "shadow_mode_notifications_require_separate_approved_change",
    )
    controller.activate(policy())
    print("[P1-005] Workflow-changing notifications remain blocked in shadow mode: PASSED")

    expect_error(lambda: build_signal("raw-context", context="observation for HN-2026-9876").validate(), "raw_identity_marker_forbidden")
    expect_error(lambda: build_signal("long-context", context="x" * 513).validate(), "shadow_context_too_large")
    expect_error(lambda: build_signal("bad-time", received_at=NOW - timedelta(seconds=1)).validate(), "received_time_before_event_time")
    expect_error(lambda: build_signal("unsupported", signal_type="patient diagnosis").validate(), "diagnostic_or_treatment_label_forbidden")
    expect_error(lambda: build_signal("unsupported-2", signal_type="blood pressure diagnosis").validate(), "diagnostic_or_treatment_label_forbidden")
    print("[P1-005] Raw-identity marker, context-size, time-order and diagnostic-label rejection: PASSED")

    controller.record_signal(build_signal("signal-001"))
    expect_error(lambda: controller.record_signal(build_signal("signal-001")), "duplicate_shadow_alert_id")
    print("[P1-005] Duplicate signal idempotency boundary: PASSED")

    expect_error(
        lambda: controller.record_review(
            ShadowReview(
                alert_id="signal-001",
                classification="TRUE_POSITIVE",
                reviewed_at=NOW + timedelta(seconds=1),
                reviewer_id="reviewer",
                reason="too early",
            )
        ),
        "reviewed_time_before_received",
    )
    valid_review = ShadowReview(
        alert_id="signal-001",
        classification="INDETERMINATE",
        reviewed_at=NOW + timedelta(seconds=10),
        reviewer_id="reviewer",
        reason="insufficient independent evidence",
    )
    controller.record_review(valid_review)
    expect_error(lambda: controller.record_review(valid_review), "duplicate_shadow_review")
    metrics = controller.metrics(now=NOW + timedelta(minutes=1))
    assert metrics["signal_count"] == 1
    assert metrics["reviewed_count"] == 1
    assert metrics["unreviewed_signal_count"] == 0
    assert metrics["confirmed_event_rate_over_reviewed"] == 0.0
    assert metrics["false_positive_review_rate_over_reviewed"] == 0.0
    print("[P1-005] Review timeline, duplicate review and denominator-labelled metrics: PASSED")
    print("CLINICAL_SHADOW_MODE_NEGATIVE_TESTS_PASSED")


if __name__ == "__main__":
    run()
