from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
from typing import Any

from external_decision_record import DecisionRecordValidationError, validate


LIFECYCLE_SCHEMA_VERSION = "external-decision-lifecycle-v1"
PENDING_EXTERNAL_VERIFICATION = "DECISION_PENDING_EXTERNAL_VERIFICATION"
REQUIRES_CLARIFICATION = "REQUIRES_CLARIFICATION"
DECISION_EXPIRED = "DECISION_EXPIRED"
DECISION_REVOKED = "DECISION_REVOKED"
BLOCKED_SIMULATION = "BLOCKED_SIMULATION"
RESUBMISSION_REQUIRED = "RESUBMISSION_REQUIRED"
REOPENED_WITH_REASON = "REOPENED_WITH_REASON"
RECEIVED_FOR_SIMULATION = "RECEIVED_FOR_SIMULATION"
STALE_RESPONSE_REJECTED = "STALE_RESPONSE_REJECTED"

AUTHORIZATION_BOUNDARY = {
    "external_authority": "NONE",
    "clinical_validation_authorized": False,
    "production_authorized": False,
    "runtime_authority": "NONE",
    "pilot_gate_status": "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION",
}

ALLOWED_EXTERNAL_UPDATE_STATUSES = {
    "PENDING_EXTERNAL_VERIFICATION",
    "REQUIRES_CLARIFICATION",
    "EXPIRED",
    "REVOKED",
    "SUPERSEDED",
    "BLOCKED",
}
TRANSITIONS = {
    PENDING_EXTERNAL_VERIFICATION: {REQUIRES_CLARIFICATION, DECISION_EXPIRED, DECISION_REVOKED, BLOCKED_SIMULATION},
    REQUIRES_CLARIFICATION: {PENDING_EXTERNAL_VERIFICATION, DECISION_EXPIRED, DECISION_REVOKED, BLOCKED_SIMULATION},
    DECISION_EXPIRED: {RESUBMISSION_REQUIRED, BLOCKED_SIMULATION},
    DECISION_REVOKED: {RESUBMISSION_REQUIRED, BLOCKED_SIMULATION},
    BLOCKED_SIMULATION: {REOPENED_WITH_REASON},
    REOPENED_WITH_REASON: {RECEIVED_FOR_SIMULATION, BLOCKED_SIMULATION},
    RECEIVED_FOR_SIMULATION: {PENDING_EXTERNAL_VERIFICATION, BLOCKED_SIMULATION},
    RESUBMISSION_REQUIRED: {RECEIVED_FOR_SIMULATION},
}


class DecisionLifecycleError(ValueError):
    pass


@dataclass(frozen=True)
class LifecycleEvent:
    schema_version: str
    event_id: str
    event_type: str
    decision_id: str
    from_state: str
    to_state: str
    source_revision: int
    occurred_at_utc: str
    actor_role: str
    reason_ref: str
    previous_event_hash: str
    event_hash: str



def _require(condition: bool, message: str) -> None:
    if not condition:
        raise DecisionLifecycleError(message)


def _utc(value: Any, field: str) -> datetime:
    _require(isinstance(value, str), f"{field} must be an ISO-8601 string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise DecisionLifecycleError(f"{field} must be a valid ISO-8601 timestamp") from exc
    _require(parsed.tzinfo is not None and parsed.utcoffset() is not None, f"{field} must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    _require(value.tzinfo is not None and value.utcoffset() is not None, "clock must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _hex(value: Any, field: str) -> str:
    _require(isinstance(value, str) and len(value) == 64, f"{field} must be a SHA-256 hex string")
    try:
        int(value, 16)
    except ValueError as exc:
        raise DecisionLifecycleError(f"{field} must be a SHA-256 hex string") from exc
    return value.lower()


def _opaque_reason(value: Any, field: str) -> str:
    _require(isinstance(value, str) and value.startswith("reason:"), f"{field} must be an opaque reason reference")
    _require(0 < len(value.split(":", 1)[1]) <= 180, f"{field} must contain a bounded reason reference")
    _require("@" not in value and "Bearer" not in value and "-----BEGIN" not in value, f"{field} contains unsafe material")
    return value


def _event_hash(event: dict[str, Any]) -> str:
    encoded = json.dumps(event, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class DecisionLifecycle:
    """Local evaluator only; it can never promote clinical, production, or external authority."""

    def __init__(self, decision_record: dict[str, Any], *, now: datetime, stale_ttl_seconds: int = 300) -> None:
        try:
            validate(decision_record)
        except DecisionRecordValidationError as exc:
            raise DecisionLifecycleError(str(exc)) from exc
        _require(now.tzinfo is not None and now.utcoffset() is not None, "now must be timezone-aware")
        _require(isinstance(stale_ttl_seconds, int) and 1 <= stale_ttl_seconds <= 86_400, "stale_ttl_seconds out of bounds")
        self._record = deepcopy(decision_record)
        self._decision_id = decision_record["decision_id"]
        self._stale_ttl_seconds = stale_ttl_seconds
        self._revision = 0
        self._remote_revision = 0
        self._remote_event_hash = None
        self._events: list[LifecycleEvent] = []
        expires_at = _utc(decision_record["expires_at"], "expires_at")
        initial_state = DECISION_EXPIRED if now.astimezone(timezone.utc) >= expires_at else PENDING_EXTERNAL_VERIFICATION
        self._state = initial_state
        self._append_event(
            event_type="INITIALIZED",
            to_state=initial_state,
            occurred_at=now,
            actor_role="local_evaluator",
            reason_ref="reason:initialization",
        )

    @property
    def state(self) -> str:
        return self._state

    @property
    def revision(self) -> int:
        return self._revision

    @property
    def decision_id(self) -> str:
        return self._decision_id

    def _append_event(self, *, event_type: str, to_state: str, occurred_at: datetime, actor_role: str, reason_ref: str) -> None:
        known_states = set(TRANSITIONS) | {DECISION_EXPIRED}
        _require(to_state in known_states, "unknown lifecycle state")
        if self._events:
            _require(to_state in TRANSITIONS[self._state], f"invalid transition {self._state} -> {to_state}")
        _require(occurred_at.tzinfo is not None and occurred_at.utcoffset() is not None, "event clock must be timezone-aware")
        _opaque_reason(reason_ref, "reason_ref")
        previous_hash = self._events[-1].event_hash if self._events else "0" * 64
        next_revision = self._revision + 1
        body = {
            "schema_version": LIFECYCLE_SCHEMA_VERSION,
            "event_id": f"event:{self._decision_id.split(':', 1)[1]}-{next_revision}",
            "event_type": event_type,
            "decision_id": self._decision_id,
            "from_state": self._state if self._events else "NONE",
            "to_state": to_state,
            "source_revision": next_revision,
            "occurred_at_utc": _iso(occurred_at),
            "actor_role": actor_role,
            "reason_ref": reason_ref,
            "previous_event_hash": previous_hash,
        }
        digest = _event_hash(body)
        self._events.append(LifecycleEvent(event_hash=digest, **body))
        self._revision = next_revision
        self._state = to_state

    def _expires_at(self) -> datetime:
        return _utc(self._record["expires_at"], "expires_at")

    def expire(self, *, now: datetime) -> dict[str, Any]:
        _require(now.tzinfo is not None and now.utcoffset() is not None, "now must be timezone-aware")
        if now.astimezone(timezone.utc) < self._expires_at():
            return self.status(now=now)
        if self._state == PENDING_EXTERNAL_VERIFICATION:
            self._append_event(event_type="EXPIRED", to_state=DECISION_EXPIRED, occurred_at=now, actor_role="local_evaluator", reason_ref="reason:expiry")
        elif self._state == REQUIRES_CLARIFICATION:
            self._append_event(event_type="EXPIRED", to_state=DECISION_EXPIRED, occurred_at=now, actor_role="local_evaluator", reason_ref="reason:expiry")
        return self.status(now=now)

    def revoke(self, *, now: datetime, reason_ref: str, actor_role: str, replacement_decision_ref: str | None = None) -> dict[str, Any]:
        _require(actor_role in {"external_authority", "independent_reviewer"}, "revocation actor must be an external authority role")
        _opaque_reason(reason_ref, "reason_ref")
        if replacement_decision_ref is not None:
            _require(replacement_decision_ref.startswith("decision:"), "replacement_decision_ref must be a decision reference")
        _require(self._state in {PENDING_EXTERNAL_VERIFICATION, REQUIRES_CLARIFICATION}, "decision cannot be revoked from current state")
        self._append_event(event_type="REVOKED" if replacement_decision_ref is None else "SUPERSEDED", to_state=DECISION_REVOKED, occurred_at=now, actor_role=actor_role, reason_ref=reason_ref)
        return self.status(now=now)

    def block(self, *, now: datetime, reason_ref: str) -> dict[str, Any]:
        _opaque_reason(reason_ref, "reason_ref")
        _require(self._state in {PENDING_EXTERNAL_VERIFICATION, REQUIRES_CLARIFICATION}, "decision cannot be blocked from current state")
        self._append_event(event_type="BLOCKED", to_state=BLOCKED_SIMULATION, occurred_at=now, actor_role="local_evaluator", reason_ref=reason_ref)
        return self.status(now=now)

    def request_resubmission(self, *, now: datetime, reason_ref: str) -> dict[str, Any]:
        _opaque_reason(reason_ref, "reason_ref")
        _require(self._state in {DECISION_EXPIRED, DECISION_REVOKED}, "resubmission requires expired or revoked decision")
        self._append_event(event_type="RESUBMISSION_REQUIRED", to_state=RESUBMISSION_REQUIRED, occurred_at=now, actor_role="local_evaluator", reason_ref=reason_ref)
        return self.status(now=now)

    def reopen(self, *, now: datetime, reason_ref: str, actor_role: str) -> dict[str, Any]:
        _require(actor_role in {"stop_authority", "recovery_approver"}, "reopen requires stop/recovery authority")
        _opaque_reason(reason_ref, "reason_ref")
        _require(self._state == BLOCKED_SIMULATION, "only blocked simulation may be reopened")
        self._append_event(event_type="REOPENED", to_state=REOPENED_WITH_REASON, occurred_at=now, actor_role=actor_role, reason_ref=reason_ref)
        return self.status(now=now)

    def receive_for_simulation(self, *, now: datetime, reason_ref: str) -> dict[str, Any]:
        _opaque_reason(reason_ref, "reason_ref")
        _require(self._state in {REOPENED_WITH_REASON, RESUBMISSION_REQUIRED}, "only reopened or resubmission-required state may return to simulation")
        self._append_event(event_type="RECEIVED_FOR_SIMULATION", to_state=RECEIVED_FOR_SIMULATION, occurred_at=now, actor_role="local_evaluator", reason_ref=reason_ref)
        return self.status(now=now)

    def begin_pending_review(self, *, now: datetime, reason_ref: str) -> dict[str, Any]:
        _opaque_reason(reason_ref, "reason_ref")
        _require(self._state == RECEIVED_FOR_SIMULATION, "only received simulation may enter pending verification")
        self._append_event(event_type="PENDING_EXTERNAL_VERIFICATION", to_state=PENDING_EXTERNAL_VERIFICATION, occurred_at=now, actor_role="local_evaluator", reason_ref=reason_ref)
        return self.status(now=now)

    def poll(self, response: dict[str, Any], *, now: datetime, known_revision: int | None = None, known_event_hash: str | None = None) -> dict[str, Any]:
        """Read-only poll evaluator. It never mutates local lifecycle state."""
        expected = {"decision_id", "source_revision", "source_event_hash", "source_status", "observed_at_utc", "clock_source_ref"}
        _require(isinstance(response, dict) and set(response) == expected, "poll response fields mismatch")
        _require(response["decision_id"] == self._decision_id, "poll decision_id mismatch")
        _require(isinstance(response["source_revision"], int) and response["source_revision"] >= 0, "source_revision invalid")
        source_hash = _hex(response["source_event_hash"], "source_event_hash")
        _require(response["source_status"] in ALLOWED_EXTERNAL_UPDATE_STATUSES, "source_status invalid")
        observed = _utc(response["observed_at_utc"], "observed_at_utc")
        _require(response["clock_source_ref"].startswith("clock:"), "clock_source_ref must be typed")
        _require(now.tzinfo is not None and now.utcoffset() is not None, "now must be timezone-aware")
        age = (now.astimezone(timezone.utc) - observed).total_seconds()
        if age < -60 or age > self._stale_ttl_seconds:
            return self._poll_result(STALE_RESPONSE_REJECTED, source_hash, response["source_revision"], "stale_or_future_response")
        if known_revision is not None:
            _require(isinstance(known_revision, int) and known_revision >= 0, "known_revision invalid")
            if response["source_revision"] < known_revision:
                return self._poll_result(STALE_RESPONSE_REJECTED, source_hash, response["source_revision"], "lower_revision")
        if known_event_hash is not None:
            _require(_hex(known_event_hash, "known_event_hash") == source_hash, "event hash mismatch")
        if response["source_revision"] < self._remote_revision:
            return self._poll_result(STALE_RESPONSE_REJECTED, source_hash, response["source_revision"], "lower_than_seen_revision")
        return self._poll_result("POLL_ACCEPTED_UNVERIFIED", source_hash, response["source_revision"], "read_only")

    def _poll_result(self, result: str, source_hash: str, source_revision: int, reason: str) -> dict[str, Any]:
        return {
            "result": result,
            "decision_id": self._decision_id,
            "source_revision": source_revision,
            "source_event_hash": source_hash,
            "local_state": self._state,
            "trusted": False,
            "external_decision_verified": False,
            "authorization_promoted": False,
            "reason": reason,
        }

    def apply_external_update(self, response: dict[str, Any], *, now: datetime, reason_ref: str, actor_role: str = "external_authority") -> dict[str, Any]:
        """Apply a separately verified-by-contract update; it still cannot authorize locally."""
        poll_result = self.poll(response, now=now, known_revision=self._remote_revision or None)
        if poll_result["result"] == STALE_RESPONSE_REJECTED:
            return poll_result
        _require(actor_role in {"external_authority", "independent_reviewer"}, "external update actor must be external")
        _opaque_reason(reason_ref, "reason_ref")
        status = response["source_status"]
        source_revision = response["source_revision"]
        _require(source_revision > self._remote_revision, "external update revision must increase")
        self._remote_revision = source_revision
        self._remote_event_hash = response["source_event_hash"]
        if status == "REQUIRES_CLARIFICATION":
            if self._state == PENDING_EXTERNAL_VERIFICATION:
                self._append_event(event_type="EXTERNAL_CLARIFICATION", to_state=REQUIRES_CLARIFICATION, occurred_at=now, actor_role=actor_role, reason_ref=reason_ref)
        elif status == "EXPIRED":
            if self._state in {PENDING_EXTERNAL_VERIFICATION, REQUIRES_CLARIFICATION}:
                self._append_event(event_type="EXTERNAL_EXPIRED", to_state=DECISION_EXPIRED, occurred_at=now, actor_role=actor_role, reason_ref=reason_ref)
        elif status in {"REVOKED", "SUPERSEDED"}:
            if self._state in {PENDING_EXTERNAL_VERIFICATION, REQUIRES_CLARIFICATION}:
                self._append_event(event_type="EXTERNAL_REVOKED" if status == "REVOKED" else "EXTERNAL_SUPERSEDED", to_state=DECISION_REVOKED, occurred_at=now, actor_role=actor_role, reason_ref=reason_ref)
        elif status == "BLOCKED":
            if self._state in {PENDING_EXTERNAL_VERIFICATION, REQUIRES_CLARIFICATION}:
                self._append_event(event_type="EXTERNAL_BLOCKED", to_state=BLOCKED_SIMULATION, occurred_at=now, actor_role=actor_role, reason_ref=reason_ref)
        return self.status(now=now)

    def status(self, *, now: datetime) -> dict[str, Any]:
        _require(now.tzinfo is not None and now.utcoffset() is not None, "now must be timezone-aware")
        return {
            "schema_version": LIFECYCLE_SCHEMA_VERSION,
            "decision_id": self._decision_id,
            "state": self._state,
            "decision_status": self._record["decision"],
            "revision": self._revision,
            "remote_revision": self._remote_revision,
            "remote_event_hash": self._remote_event_hash,
            "expires_at": self._record["expires_at"],
            "expired": now.astimezone(timezone.utc) >= self._expires_at(),
            "trusted": False,
            "external_decision_verified": False,
            "authorization_promoted": False,
            "external_execution_authorized": False,
            "production_authorized": False,
            "clinical_validation_authorized": False,
            "authorization_boundary": deepcopy(AUTHORIZATION_BOUNDARY),
        }

    def audit_chain_valid(self) -> bool:
        previous = "0" * 64
        for event in self._events:
            body = {
                "schema_version": LIFECYCLE_SCHEMA_VERSION,
                "event_id": event.event_id,
                "event_type": event.event_type,
                "decision_id": event.decision_id,
                "from_state": event.from_state,
                "to_state": event.to_state,
                "source_revision": event.source_revision,
                "occurred_at_utc": event.occurred_at_utc,
                "actor_role": event.actor_role,
                "reason_ref": event.reason_ref,
                "previous_event_hash": event.previous_event_hash,
            }
            if event.previous_event_hash != previous or _event_hash(body) != event.event_hash:
                return False
            previous = event.event_hash
        return True

    def snapshot(self) -> dict[str, Any]:
        return {
            "schema_version": LIFECYCLE_SCHEMA_VERSION,
            "record": deepcopy(self._record),
            "state": self._state,
            "revision": self._revision,
            "remote_revision": self._remote_revision,
            "remote_event_hash": self._remote_event_hash,
            "events": [event.__dict__.copy() for event in self._events],
            "authorization_boundary": deepcopy(AUTHORIZATION_BOUNDARY),
        }


__all__ = [
    "AUTHORIZATION_BOUNDARY",
    "BLOCKED_SIMULATION",
    "DECISION_EXPIRED",
    "DECISION_REVOKED",
    "DecisionLifecycle",
    "DecisionLifecycleError",
    "PENDING_EXTERNAL_VERIFICATION",
    "RECEIVED_FOR_SIMULATION",
    "REOPENED_WITH_REASON",
    "REQUIRES_CLARIFICATION",
    "RESUBMISSION_REQUIRED",
    "STALE_RESPONSE_REJECTED",
]
