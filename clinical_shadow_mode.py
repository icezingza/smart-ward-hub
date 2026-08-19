from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import re
from typing import Any


OPAQUE_TOKEN = re.compile(r"[A-Za-z0-9._~-]{16,128}")
RAW_ID = re.compile(r"^(HN|AN)([-_:]|$)", re.IGNORECASE)
SAFE_SIGNAL_TYPES = {"suspected fall", "vital anomaly signal", "device/perimeter warning"}
DISALLOWED_DIAGNOSTIC_TERMS = {"diagnosis", "heart attack", "stroke", "sepsis", "treatment order", "medication order"}
CLASSIFICATIONS = {"TRUE_POSITIVE", "FALSE_POSITIVE", "MISSED_EVENT", "INDETERMINATE", "DEVICE_DATA_FAULT"}


class ShadowModeError(ValueError):
    pass


@dataclass(frozen=True)
class ShadowModePolicy:
    clinical_owner: str
    technical_owner: str
    privacy_security_reviewer: str
    ward_manager: str
    incident_contact: str
    backup_restore_evidence: bool
    device_inventory: bool
    training_note: bool
    data_retention_decision: bool
    rollback_plan: bool
    approval_id: str | None = None
    notifications_enabled: bool = False
    notification_approval_id: str | None = None

    def validate(self) -> list[str]:
        issues: list[str] = []
        for field_name in ("clinical_owner", "technical_owner", "privacy_security_reviewer", "ward_manager", "incident_contact"):
            if not getattr(self, field_name).strip():
                issues.append(f"missing_{field_name}")
        for field_name in ("backup_restore_evidence", "device_inventory", "training_note", "data_retention_decision", "rollback_plan"):
            if not getattr(self, field_name):
                issues.append(f"missing_{field_name}")
        if not self.approval_id or not self.approval_id.strip():
            issues.append("clinical_governance_approval_required")
        if self.notifications_enabled and not self.notification_approval_id:
            issues.append("notification_approval_required")
        return issues


@dataclass(frozen=True)
class ShadowSignal:
    alert_id: str
    signal_type: str
    patient_token: str
    device_id: str
    bed_no: str
    event_time: datetime
    received_at: datetime
    context: str = ""

    def validate(self) -> None:
        if not self.alert_id.strip() or not self.device_id.strip() or not self.bed_no.strip():
            raise ShadowModeError("signal_identity_fields_required")
        if not OPAQUE_TOKEN.fullmatch(self.patient_token) or RAW_ID.match(self.patient_token):
            raise ShadowModeError("opaque_patient_token_required")
        normalized = self.signal_type.strip().lower()
        if normalized not in SAFE_SIGNAL_TYPES:
            if any(term in normalized for term in DISALLOWED_DIAGNOSTIC_TERMS):
                raise ShadowModeError("diagnostic_or_treatment_label_forbidden")
            raise ShadowModeError("unsupported_shadow_signal_type")
        if self.received_at < self.event_time:
            raise ShadowModeError("received_time_before_event_time")

    def to_record(self) -> dict[str, Any]:
        self.validate()
        record = asdict(self)
        record["event_time"] = self.event_time.astimezone(timezone.utc).isoformat()
        record["received_at"] = self.received_at.astimezone(timezone.utc).isoformat()
        record["evidence_class"] = "SHADOW_SIGNAL_NOT_CLINICAL_DECISION"
        return record


@dataclass(frozen=True)
class ShadowReview:
    alert_id: str
    classification: str
    reviewed_at: datetime
    reviewer_id: str
    reason: str
    acknowledged_at: datetime | None = None
    resolved_at: datetime | None = None

    def validate(self) -> None:
        if self.classification not in CLASSIFICATIONS:
            raise ShadowModeError("invalid_review_classification")
        if not self.reviewer_id.strip() or not self.reason.strip():
            raise ShadowModeError("reviewer_and_reason_required")
        if self.acknowledged_at and self.acknowledged_at < self.reviewed_at:
            raise ShadowModeError("acknowledged_time_invalid")
        if self.resolved_at and self.resolved_at < self.reviewed_at:
            raise ShadowModeError("resolved_time_invalid")


class ShadowModeController:
    def __init__(self) -> None:
        self.state = "DISABLED"
        self.policy: ShadowModePolicy | None = None
        self.stop_event: dict[str, str] | None = None
        self.signals: dict[str, ShadowSignal] = {}
        self.reviews: dict[str, ShadowReview] = {}

    def activate(self, policy: ShadowModePolicy) -> None:
        issues = policy.validate()
        if issues:
            raise ShadowModeError("policy_not_approved:" + ",".join(issues))
        if policy.notifications_enabled:
            raise ShadowModeError("shadow_mode_notifications_require_separate_approved_change")
        self.policy = policy
        self.state = "ACTIVE"
        self.stop_event = None

    def stop(self, *, incident_id: str, reason: str) -> None:
        if not incident_id.strip() or not reason.strip():
            raise ShadowModeError("stop_incident_and_reason_required")
        self.state = "STOPPED"
        self.stop_event = {"incident_id": incident_id, "reason": reason}

    def resume(self, *, approval_id: str) -> None:
        if self.state != "STOPPED":
            raise ShadowModeError("shadow_mode_not_stopped")
        if not approval_id.strip():
            raise ShadowModeError("resume_approval_required")
        self.state = "ACTIVE"
        self.stop_event = None

    def record_signal(self, signal: ShadowSignal) -> dict[str, Any]:
        if self.state != "ACTIVE":
            raise ShadowModeError("shadow_mode_not_active")
        signal.validate()
        if signal.alert_id in self.signals:
            raise ShadowModeError("duplicate_shadow_alert_id")
        self.signals[signal.alert_id] = signal
        return signal.to_record()

    def record_review(self, review: ShadowReview) -> None:
        if self.state not in {"ACTIVE", "STOPPED"}:
            raise ShadowModeError("shadow_mode_not_started")
        review.validate()
        if review.alert_id not in self.signals:
            raise ShadowModeError("review_signal_not_found")
        self.reviews[review.alert_id] = review

    def metrics(self, *, now: datetime | None = None) -> dict[str, Any]:
        current = now or datetime.now(timezone.utc)
        signal_count = len(self.signals)
        reviewed = [review for review in self.reviews.values()]
        true_positive = sum(review.classification == "TRUE_POSITIVE" for review in reviewed)
        false_positive = sum(review.classification == "FALSE_POSITIVE" for review in reviewed)
        missed = sum(review.classification == "MISSED_EVENT" for review in reviewed)
        freshness_seconds = [
            max(0.0, (signal.received_at - signal.event_time).total_seconds())
            for signal in self.signals.values()
        ]
        ack_seconds = [
            max(0.0, (review.acknowledged_at - self.signals[review.alert_id].received_at).total_seconds())
            for review in reviewed
            if review.acknowledged_at is not None
        ]
        resolve_seconds = [
            max(0.0, (review.resolved_at - self.signals[review.alert_id].received_at).total_seconds())
            for review in reviewed
            if review.resolved_at is not None
        ]
        return {
            "state": self.state,
            "signal_count": signal_count,
            "reviewed_count": len(reviewed),
            "true_positive_count": true_positive,
            "false_positive_count": false_positive,
            "missed_event_count": missed,
            "indeterminate_count": sum(review.classification == "INDETERMINATE" for review in reviewed),
            "device_data_fault_count": sum(review.classification == "DEVICE_DATA_FAULT" for review in reviewed),
            "review_coverage": (len(reviewed) / signal_count) if signal_count else 0.0,
            "confirmed_event_rate": (true_positive / len(reviewed)) if reviewed else None,
            "false_positive_review_rate": (false_positive / len(reviewed)) if reviewed else None,
            "mean_data_freshness_seconds": (sum(freshness_seconds) / len(freshness_seconds)) if freshness_seconds else None,
            "mean_acknowledge_seconds": (sum(ack_seconds) / len(ack_seconds)) if ack_seconds else None,
            "mean_resolve_seconds": (sum(resolve_seconds) / len(resolve_seconds)) if resolve_seconds else None,
            "measured_at_utc": current.astimezone(timezone.utc).isoformat(),
            "evidence_class": "SHADOW_REVIEW_METRICS_NOT_CLINICAL_ACCURACY",
        }
