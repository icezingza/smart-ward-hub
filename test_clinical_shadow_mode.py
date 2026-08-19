from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json

from clinical_shadow_mode import ShadowModeController, ShadowModeError, ShadowModePolicy, ShadowReview, ShadowSignal


NOW = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
RAW_HN = "HN-2026-123456"
TOKEN = "ptok-shadow-review-0001"


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
        "approval_id": "CLIN-APPROVAL-001",
        "notifications_enabled": False,
    }
    values.update(overrides)
    return ShadowModePolicy(**values)


def signal(alert_id: str, *, offset: int = 0, signal_type: str = "vital anomaly signal") -> ShadowSignal:
    event_time = NOW + timedelta(seconds=offset)
    return ShadowSignal(
        alert_id=alert_id,
        signal_type=signal_type,
        patient_token=TOKEN,
        device_id="MAC-SHADOW-01",
        bed_no="W04-B12",
        event_time=event_time,
        received_at=event_time + timedelta(seconds=5),
        context="heuristic context only",
    )


def run() -> None:
    controller = ShadowModeController()
    incomplete = policy(rollback_plan=False)
    expect_error(lambda: controller.activate(incomplete), "policy_not_approved:missing_rollback_plan")
    print("[P1-005] Incomplete governance policy blocks activation: PASSED")

    controller.activate(policy())
    assert controller.state == "ACTIVE"
    print("[P1-005] Approved shadow-mode activation with notifications disabled: PASSED")

    record = controller.record_signal(signal("shadow-alert-001"))
    assert record["evidence_class"] == "SHADOW_SIGNAL_NOT_CLINICAL_DECISION"
    assert RAW_HN not in json.dumps(record)
    expect_error(
        lambda: controller.record_signal(signal("shadow-alert-diagnosis", signal_type="diagnosis: sepsis")),
        "diagnostic_or_treatment_label_forbidden",
    )
    expect_error(
        lambda: controller.record_signal(signal("shadow-alert-raw-hn")) if False else ShadowSignal(
            alert_id="shadow-alert-raw-hn",
            signal_type="vital anomaly signal",
            patient_token=RAW_HN,
            device_id="MAC-SHADOW-01",
            bed_no="W04-B12",
            event_time=NOW,
            received_at=NOW + timedelta(seconds=1),
        ).validate(),
        "opaque_patient_token_required",
    )
    print("[P1-005] Safe signal labels and Zero-PII token boundary: PASSED")

    controller.record_review(
        ShadowReview(
            alert_id="shadow-alert-001",
            classification="TRUE_POSITIVE",
            reviewed_at=NOW + timedelta(minutes=1),
            reviewer_id="reviewer-001",
            reason="independent observation matched signal",
            acknowledged_at=NOW + timedelta(minutes=1, seconds=20),
            resolved_at=NOW + timedelta(minutes=3),
        )
    )
    controller.record_signal(signal("shadow-alert-002", offset=10))
    controller.record_review(
        ShadowReview(
            alert_id="shadow-alert-002",
            classification="FALSE_POSITIVE",
            reviewed_at=NOW + timedelta(minutes=2),
            reviewer_id="reviewer-001",
            reason="no corroborating event",
        )
    )
    metrics = controller.metrics(now=NOW + timedelta(hours=1))
    assert metrics["signal_count"] == 2
    assert metrics["reviewed_count"] == 2
    assert metrics["true_positive_count"] == 1
    assert metrics["false_positive_count"] == 1
    assert metrics["review_coverage"] == 1.0
    assert metrics["evidence_class"] == "SHADOW_REVIEW_METRICS_NOT_CLINICAL_ACCURACY"
    print("[P1-005] Shadow review classifications and non-accuracy metrics: PASSED")

    controller.stop(incident_id="INC-SHADOW-001", reason="simulated critical privacy boundary stop")
    assert controller.state == "STOPPED"
    expect_error(lambda: controller.record_signal(signal("shadow-alert-after-stop")), "shadow_mode_not_active")
    expect_error(lambda: controller.resume(approval_id="   "), "resume_approval_required")
    controller.resume(approval_id="RESUME-APPROVAL-001")
    assert controller.state == "ACTIVE"
    print("[P1-005] Stop condition blocks intake until explicit resume approval: PASSED")
    print("CLINICAL_SHADOW_MODE_CONTRACT_TESTS_PASSED")


if __name__ == "__main__":
    run()
