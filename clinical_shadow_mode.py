from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import re
from typing import Any


OPAQUE_TOKEN = re.compile(r"[A-Za-z0-9._~-]{16,128}")
REFERENCE_TOKEN = re.compile(r"[A-Za-z0-9._~-]{3,128}")
RAW_ID = re.compile(r"\b(?:HN|AN|MRN|NATIONAL_ID)\s*[-_:]?\s*[A-Z0-9-]+\b", re.IGNORECASE)
SECRET_MARKER = re.compile(r"(?:BEGIN (?:RSA|EC|OPENSSH|DSA|PRIVATE) KEY|Bearer\s+\S+|(?:password|secret|token|private_key|seed)\s*[:=]\s*\S+)", re.IGNORECASE)
MAX_CONTEXT_LENGTH = 512
SAFE_SIGNAL_TYPES = {"suspected fall", "vital anomaly signal", "device/perimeter warning"}
DISALLOWED_DIAGNOSTIC_TERMS = {"diagnosis", "heart attack", "stroke", "sepsis", "treatment order", "medication order"}
CLASSIFICATIONS = {"TRUE_POSITIVE", "FALSE_POSITIVE", "MISSED_EVENT", "INDETERMINATE", "DEVICE_DATA_FAULT"}


def _safe_reference(value: Any, field: str) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return f"missing_{field}"
    if not REFERENCE_TOKEN.fullmatch(value.strip()):
        return f"invalid_{field}"
    if RAW_ID.search(value) or SECRET_MARKER.search(value) or "@" in value:
        return f"unsafe_{field}"
    return None


def _safe_free_text(value: Any, field: str, *, max_length: int | None = None) -> str | None:
    if not isinstance(value, str):
        return f"invalid_{field}"
    if max_length is not None and len(value) > max_length:
        return f"{field}_too_large"
    if RAW_ID.search(value) or SECRET_MARKER.search(value) or "@" in value:
        return f"unsafe_{field}"
    return None


def _timezone_aware(value: Any, field: str) -> str | None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        return f"{field}_must_be_timezone_aware"
    return None


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
            issue = _safe_reference(getattr(self, field_name), field_name)
            if issue:
                issues.append(issue)
        for field_name in ("backup_restore_evidence", "device_inventory", "training_note", "data_retention_decision", "rollback_plan", "notifications_enabled"):
            if not isinstance(getattr(self, field_name), bool):
                issues.append(f"{field_name}_must_be_boolean")
            elif field_name != "notifications_enabled" and not getattr(self, field_name):
                issues.append(f"missing_{field_name}")
        approval_issue = _safe_reference(self.approval_id, "approval_id")
        if approval_issue:
            issues.append("clinical_governance_approval_required" if approval_issue.startswith("missing_") else approval_issue)
        if self.notifications_enabled and _safe_reference(self.notification_approval_id, "notification_approval_id") is not None:
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
        if not isinstance(self.alert_id, str) or not isinstance(self.device_id, str) or not isinstance(self.bed_no, str) or not self.alert_id.strip() or not self.device_id.strip() or not self.bed_no.strip():
            raise ShadowModeError("signal_identity_fields_required")
        if not isinstance(self.patient_token, str) or not OPAQUE_TOKEN.fullmatch(self.patient_token) or RAW_ID.search(self.patient_token):
            raise ShadowModeError("opaque_patient_token_required")
        if not isinstance(self.context, str):
            raise ShadowModeError("shadow_context_invalid")
        if len(self.context) > MAX_CONTEXT_LENGTH:
            raise ShadowModeError("shadow_context_too_large")
        for value in (self.alert_id, self.device_id, self.bed_no, self.context):
            if RAW_ID.search(value) or SECRET_MARKER.search(value) or "@" in value:
                raise ShadowModeError("raw_identity_marker_forbidden")
        for field_name, value in (("event_time", self.event_time), ("received_at", self.received_at)):
            issue = _timezone_aware(value, field_name)
            if issue:
                raise ShadowModeError(issue)
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
        if _safe_reference(self.alert_id, "alert_id") or _safe_reference(self.reviewer_id, "reviewer_id"):
            raise ShadowModeError("reviewer_and_reason_required")
        reason_issue = _safe_free_text(self.reason, "review_reason", max_length=1024)
        if reason_issue:
            raise ShadowModeError("review_reason_invalid")
        for field_name, value in (("reviewed_at", self.reviewed_at), ("acknowledged_at", self.acknowledged_at), ("resolved_at", self.resolved_at)):
            if value is not None:
                issue = _timezone_aware(value, field_name)
                if issue:
                    raise ShadowModeError(issue)
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
        if self.state != "DISABLED":
            raise ShadowModeError("shadow_mode_activation_requires_disabled_state")
        issues = policy.validate()
        if issues:
            raise ShadowModeError("policy_not_approved:" + ",".join(issues))
        if policy.notifications_enabled:
            raise ShadowModeError("shadow_mode_notifications_require_separate_approved_change")
        self.policy = policy
        self.state = "ACTIVE"
        self.stop_event = None

    def stop(self, *, incident_id: str, reason: str) -> None:
        if self.state != "ACTIVE" or self.policy is None:
            raise ShadowModeError("shadow_mode_not_active")
        if _safe_reference(incident_id, "incident_id") or _safe_free_text(reason, "stop_reason", max_length=1024):
            raise ShadowModeError("stop_incident_and_reason_required")
        self.state = "STOPPED"
        self.stop_event = {"incident_id": incident_id, "reason": reason}

    def resume(self, *, approval_id: str) -> None:
        if self.state != "STOPPED":
            raise ShadowModeError("shadow_mode_not_stopped")
        if _safe_reference(approval_id, "resume_approval_id"):
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
        signal = self.signals.get(review.alert_id)
        if signal is None:
            raise ShadowModeError("review_signal_not_found")
        if review.reviewed_at < signal.received_at:
            raise ShadowModeError("reviewed_time_before_received")
        if review.acknowledged_at and review.acknowledged_at < signal.received_at:
            raise ShadowModeError("acknowledged_time_before_received")
        if review.resolved_at and review.resolved_at < signal.received_at:
            raise ShadowModeError("resolved_time_before_received")
        if review.alert_id in self.reviews:
            raise ShadowModeError("duplicate_shadow_review")
        self.reviews[review.alert_id] = review

    def metrics(self, *, now: datetime | None = None) -> dict[str, Any]:
        current = now or datetime.now(timezone.utc)
        issue = _timezone_aware(current, "metrics_time")
        if issue:
            raise ShadowModeError(issue)
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
            "unreviewed_signal_count": max(0, signal_count - len(reviewed)),
            "confirmed_event_rate_over_reviewed": (true_positive / len(reviewed)) if reviewed else None,
            "false_positive_review_rate_over_reviewed": (false_positive / len(reviewed)) if reviewed else None,
            "mean_data_freshness_seconds": (sum(freshness_seconds) / len(freshness_seconds)) if freshness_seconds else None,
            "mean_acknowledge_seconds": (sum(ack_seconds) / len(ack_seconds)) if ack_seconds else None,
            "mean_resolve_seconds": (sum(resolve_seconds) / len(resolve_seconds)) if resolve_seconds else None,
            "measured_at_utc": current.astimezone(timezone.utc).isoformat(),
            "evidence_class": "SHADOW_REVIEW_METRICS_NOT_CLINICAL_ACCURACY",
        }
