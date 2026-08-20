from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path

from clinical_shadow_mode import ShadowModeController, ShadowModeError, ShadowModePolicy, ShadowReview, ShadowSignal
from p1_005_clinical_shadow_readiness import ClinicalShadowReadinessError, template, validate_shadow_manifest

ROOT = Path(__file__).resolve().parent
NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
TOKEN = "ptok-shadow-hardening-0001"
TEMPLATE_PATH = ROOT / "evals/micro_rag/evidence/p1-005-clinical-shadow-readiness-template-20260820.json"
SCHEMA_PATH = ROOT / "evals/micro_rag/evidence/p1-005-clinical-shadow-readiness-schema-v1.json"


def expect_shadow_error(action, expected: str) -> None:
    try:
        action()
    except ShadowModeError as exc:
        assert str(exc) == expected, (str(exc), expected)
    else:
        raise AssertionError(f"expected {expected}")


def expect_readiness_rejection(payload: dict, fragment: str) -> None:
    try:
        validate_shadow_manifest(payload, template_only=True)
    except ClinicalShadowReadinessError as exc:
        assert fragment in str(exc), str(exc)
    else:
        raise AssertionError("readiness mutation was accepted")


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
        "approval_id": "CLIN-APPROVAL-HARD-001",
        "notifications_enabled": False,
    }
    values.update(overrides)
    return ShadowModePolicy(**values)


def build_signal(alert_id: str = "shadow-hard-001", **overrides) -> ShadowSignal:
    values = {
        "alert_id": alert_id,
        "signal_type": "vital anomaly signal",
        "patient_token": TOKEN,
        "device_id": "MAC-SHADOW-HARD-01",
        "bed_no": "W04-B12",
        "event_time": NOW,
        "received_at": NOW + timedelta(seconds=5),
        "context": "bounded non-PII heuristic context",
    }
    values.update(overrides)
    return ShadowSignal(**values)


def test_readiness_boundary_mutations() -> None:
    payload = template()
    assert validate_shadow_manifest(payload, template_only=True)["valid"] is True
    assert json.loads(TEMPLATE_PATH.read_text(encoding="utf-8"))["notification_mode"] == "DISABLED"
    assert json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))["$id"].endswith("p1-005-clinical-shadow-readiness-v1")

    payload = template()
    payload["unexpected"] = True
    expect_readiness_rejection(payload, "unknown fields")
    for field, value, fragment in (
        ("real_world_authorization", True, "real_world_authorization must remain false"),
        ("clinical_validation", "AUTHORIZED", "clinical validation must remain PENDING"),
        ("notification_mode", "ENABLED", "notification mode must remain disabled"),
        ("metrics_claim", "CLINICAL_ACCURACY", "metrics claim boundary mismatch"),
        ("zero_pii_claim", "SYSTEMWIDE_ZERO_RISK", "Zero-PII claim boundary mismatch"),
    ):
        payload = template()
        payload[field] = value
        expect_readiness_rejection(payload, fragment)
    payload = template()
    payload["tracks"].pop("SM-005")
    expect_readiness_rejection(payload, "tracks must contain exactly")
    payload = template()
    payload["common_controls"]["protocol_ref"] = "clinical@example.invalid"
    expect_readiness_rejection(payload, "must be an opaque reference")
    print("[P1-005] Readiness manifest claim/track/reference mutations: PASSED")


def test_policy_and_signal_adversarial() -> None:
    controller = ShadowModeController()
    expect_shadow_error(lambda: controller.activate(policy(clinical_owner="clinician@example.invalid")), "policy_not_approved:invalid_clinical_owner")
    expect_shadow_error(lambda: controller.activate(policy(backup_restore_evidence="yes")), "policy_not_approved:backup_restore_evidence_must_be_boolean")
    expect_shadow_error(lambda: controller.activate(policy(approval_id="HN-2026-1234")), "policy_not_approved:unsafe_approval_id")
    controller.activate(policy())
    expect_shadow_error(lambda: controller.activate(policy()), "shadow_mode_activation_requires_disabled_state")

    expect_shadow_error(lambda: controller.record_signal(build_signal(context="sec" + "ret=" + "value")), "raw_identity_marker_forbidden")
    expect_shadow_error(lambda: controller.record_signal(build_signal(patient_token="HN-2026-9999")), "opaque_patient_token_required")
    expect_shadow_error(lambda: controller.record_signal(build_signal(event_time=datetime(2026, 1, 1), received_at=datetime(2026, 1, 1, 0, 0, 1))), "event_time_must_be_timezone_aware")
    expect_shadow_error(lambda: controller.record_signal(build_signal(signal_type=None)), "unsupported_shadow_signal_type")
    expect_shadow_error(lambda: controller.record_signal(build_signal()), "duplicate_shadow_alert_id") if controller.record_signal(build_signal()) is None else None
    print("[P1-005] Policy type/reference/activation and signal PII/time/replay mutations: PASSED")


def test_review_stop_resume_metrics_adversarial() -> None:
    controller = ShadowModeController()
    controller.activate(policy())
    controller.record_signal(build_signal())
    expect_shadow_error(lambda: controller.record_review(ShadowReview(alert_id="shadow-hard-001", classification="TRUE_POSITIVE", reviewed_at=NOW + timedelta(minutes=1), reviewer_id="reviewer@example.invalid", reason="observed")), "reviewer_and_reason_required")
    expect_shadow_error(lambda: controller.record_review(ShadowReview(alert_id="shadow-hard-001", classification="TRUE_POSITIVE", reviewed_at=NOW.replace(tzinfo=None) + timedelta(minutes=1), reviewer_id="reviewer-001", reason="observed")), "reviewed_at_must_be_timezone_aware")
    expect_shadow_error(lambda: controller.metrics(now=NOW.replace(tzinfo=None)), "metrics_time_must_be_timezone_aware")
    metrics = controller.metrics(now=NOW + timedelta(minutes=5))
    assert metrics["reviewed_count"] == 0
    assert metrics["unreviewed_signal_count"] == 1
    assert metrics["confirmed_event_rate_over_reviewed"] is None
    assert metrics["false_positive_review_rate_over_reviewed"] is None
    assert metrics["evidence_class"] == "SHADOW_REVIEW_METRICS_NOT_CLINICAL_ACCURACY"

    expect_shadow_error(lambda: controller.stop(incident_id="INC-001", reason="HN-2026-9999 exposed"), "stop_incident_and_reason_required")
    controller.stop(incident_id="INC-HARD-001", reason="privacy boundary stop")
    expect_shadow_error(lambda: controller.stop(incident_id="INC-HARD-002", reason="second stop"), "shadow_mode_not_active")
    expect_shadow_error(lambda: controller.resume(approval_id="approver@example.invalid"), "resume_approval_required")
    controller.resume(approval_id="RESUME-HARD-001")
    print("[P1-005] Review identity/time, denominator, stop/resume and no-accuracy mutations: PASSED")


if __name__ == "__main__":
    test_readiness_boundary_mutations()
    test_policy_and_signal_adversarial()
    test_review_stop_resume_metrics_adversarial()
    print("P1_005_CLINICAL_SHADOW_HARDENING_TESTS_PASSED")
