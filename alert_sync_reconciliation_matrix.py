"""Alert/sync reconciliation matrix for controlled, fail-closed rehearsal.

This module is intentionally pure and side-effect free. It does not access the
network, database, scheduler, provider, or authorization system. It evaluates
an already-collected, redacted observation and returns a decision contract.

The evaluator is a software-simulation control, not clinical validation and
must not be used as an authorization mechanism for production resume.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
import hashlib
import json
import re
from typing import Any, Iterable


class Operation(StrEnum):
    MONITORING_RESUME = "MONITORING_RESUME"
    RESET = "RESET"
    DISCHARGE = "DISCHARGE"
    SYNC_RETRY = "SYNC_RETRY"
    ROAMING_COMMAND = "ROAMING_COMMAND"


class RecoveryDecision(StrEnum):
    RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"
    OPERATOR_CONFIRMATION_REQUIRED = "OPERATOR_CONFIRMATION_REQUIRED"
    SOFTWARE_RESUME_ELIGIBLE = "SOFTWARE_RESUME_ELIGIBLE"


class RemediationCode(StrEnum):
    ACKNOWLEDGED_ALERT_MONITORING_RESUME = "ACKNOWLEDGED_ALERT_MONITORING_RESUME"
    NO_OPEN_ALERT = "NO_OPEN_ALERT"
    UNACKNOWLEDGED_ALERT_REQUIRES_OPERATOR = "UNACKNOWLEDGED_ALERT_REQUIRES_OPERATOR"
    UNRESOLVED_ALERT_BLOCKS_RESET = "UNRESOLVED_ALERT_BLOCKS_RESET"
    INCIDENT_FREEZE_REQUIRED = "INCIDENT_FREEZE_REQUIRED"
    FORENSIC_PACKAGE_REQUIRED = "FORENSIC_PACKAGE_REQUIRED"
    SYNC_ACKNOWLEDGED = "SYNC_ACKNOWLEDGED"
    SYNC_RETRY_PENDING = "SYNC_RETRY_PENDING"
    SYNC_DEAD_LETTER = "SYNC_DEAD_LETTER"
    STALE_REVISION_409 = "STALE_REVISION_409"
    ROAMING_COMMAND_ELIGIBLE = "ROAMING_COMMAND_ELIGIBLE"
    IDEMPOTENT_REPLAY = "IDEMPOTENT_REPLAY"
    INVALID_OBSERVATION = "INVALID_OBSERVATION"
    AUTHORIZATION_BOUNDARY_LOCKED = "AUTHORIZATION_BOUNDARY_LOCKED"


class MatrixValidationError(ValueError):
    """Raised when a reconciliation observation violates its data contract."""


@dataclass(frozen=True, slots=True)
class AlertObservation:
    alert_ref: str | None = None
    session_ref: str | None = None
    acknowledged: bool = False
    resolved: bool = False
    incident_frozen: bool = False
    forensic_package_present: bool = False


@dataclass(frozen=True, slots=True)
class SyncObservation:
    bundle_ref: str | None = None
    attempt_count: int = 0
    retry_limit: int = 3
    last_status_code: int | None = None
    acknowledged: bool = False
    stale_revision: bool = False
    dead_lettered: bool = False


@dataclass(frozen=True, slots=True)
class RoamingObservation:
    command_ref: str | None = None
    expected_revision: int | None = None
    current_revision: int | None = None
    idempotency_replay: bool = False
    existing_status: str | None = None


@dataclass(frozen=True, slots=True)
class AuthorizationObservation:
    external_authority: str = "NONE"
    clinical_validation_authorized: bool = False
    production_authorized: bool = False
    runtime_authority: str = "NONE"


@dataclass(frozen=True, slots=True)
class ReconciliationObservation:
    operation: Operation
    session_status: str = "ACTIVE"
    alert: AlertObservation = field(default_factory=AlertObservation)
    sync: SyncObservation = field(default_factory=SyncObservation)
    roaming: RoamingObservation = field(default_factory=RoamingObservation)
    authorization: AuthorizationObservation = field(default_factory=AuthorizationObservation)
    operator_confirmation_present: bool = False


@dataclass(frozen=True, slots=True)
class DecisionContract:
    scenario_id: str
    operation: str
    resume_permitted: bool
    recovery_decision: str
    remediation_code: str
    reason: str
    opaque_refs: dict[str, str] = field(default_factory=dict)
    authorization_boundary_locked: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_RAW_ID_PATTERNS = (
    re.compile(r"(?:^|[-_ ])(?:hn|an|mrn)(?:[-_ :]|$)", re.IGNORECASE),
    re.compile(r"patient[_ -]?(?:name|id|identity)", re.IGNORECASE),
    re.compile(r"(?:^|[-_ ])(?:name|address|phone|dob)(?:[-_ :]|$)", re.IGNORECASE),
)
_ALLOWED_SESSION_STATES = {"ACTIVE", "RESET_PENDING", "INCIDENT_FROZEN", "SESSION_CLOSED", "READY_FOR_CHARGE"}


def _validate_ref(value: str | None, field_name: str) -> None:
    if value is None:
        return
    if not isinstance(value, str) or not value.strip() or len(value) > 256:
        raise MatrixValidationError(f"{field_name}_invalid")
    if any(pattern.search(value) for pattern in _RAW_ID_PATTERNS):
        raise MatrixValidationError(f"{field_name}_must_be_opaque")


def _opaque_digest(value: str | None, namespace: str) -> str | None:
    if value is None:
        return None
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:20]
    return f"{namespace}:{digest}"


def _redacted_refs(observation: ReconciliationObservation) -> dict[str, str]:
    refs = {
        "alert_ref": _opaque_digest(observation.alert.alert_ref, "alert"),
        "session_ref": _opaque_digest(observation.alert.session_ref, "session"),
        "bundle_ref": _opaque_digest(observation.sync.bundle_ref, "bundle"),
        "command_ref": _opaque_digest(observation.roaming.command_ref, "command"),
    }
    return {key: value for key, value in refs.items() if value is not None}


def _validate_observation(observation: ReconciliationObservation) -> None:
    if not isinstance(observation.operation, Operation):
        raise MatrixValidationError("operation_invalid")
    if observation.session_status not in _ALLOWED_SESSION_STATES:
        raise MatrixValidationError("session_status_invalid")
    for value, field_name in (
        (observation.alert.alert_ref, "alert_ref"),
        (observation.alert.session_ref, "session_ref"),
        (observation.sync.bundle_ref, "bundle_ref"),
        (observation.roaming.command_ref, "command_ref"),
    ):
        _validate_ref(value, field_name)
    if observation.sync.attempt_count < 0:
        raise MatrixValidationError("attempt_count_invalid")
    if observation.sync.retry_limit < 0:
        raise MatrixValidationError("retry_limit_invalid")
    if observation.sync.last_status_code is not None and not 100 <= observation.sync.last_status_code <= 599:
        raise MatrixValidationError("status_code_invalid")
    for value, field_name in (
        (observation.roaming.expected_revision, "expected_revision"),
        (observation.roaming.current_revision, "current_revision"),
    ):
        if value is not None and value < 0:
            raise MatrixValidationError(f"{field_name}_invalid")
    if observation.alert.resolved and not observation.alert.acknowledged:
        raise MatrixValidationError("resolved_alert_must_be_acknowledged")


def _authorization_locked(auth: AuthorizationObservation) -> bool:
    return not (
        auth.external_authority != "NONE"
        or auth.clinical_validation_authorized
        or auth.production_authorized
        or auth.runtime_authority != "NONE"
    )


def _decision(
    observation: ReconciliationObservation,
    scenario_id: str,
    resume_permitted: bool,
    recovery_decision: RecoveryDecision,
    remediation_code: RemediationCode,
    reason: str,
) -> DecisionContract:
    # The matrix can report software eligibility only. It never mutates or
    # grants external/clinical/production/runtime authority.
    return DecisionContract(
        scenario_id=scenario_id,
        operation=observation.operation.value,
        resume_permitted=resume_permitted,
        recovery_decision=recovery_decision.value,
        remediation_code=remediation_code.value,
        reason=reason,
        opaque_refs=_redacted_refs(observation),
        authorization_boundary_locked=_authorization_locked(observation.authorization),
    )


def evaluate_reconciliation(observation: ReconciliationObservation) -> DecisionContract:
    """Evaluate one redacted observation using fail-closed precedence rules."""
    try:
        _validate_observation(observation)
    except MatrixValidationError as exc:
        return DecisionContract(
            scenario_id="invalid_observation",
            operation=str(getattr(observation.operation, "value", observation.operation)),
            resume_permitted=False,
            recovery_decision=RecoveryDecision.RECONCILIATION_REQUIRED.value,
            remediation_code=RemediationCode.INVALID_OBSERVATION.value,
            reason=str(exc),
            opaque_refs={},
            authorization_boundary_locked=True,
        )

    if not _authorization_locked(observation.authorization):
        return _decision(
            observation,
            "authorization_boundary_locked",
            False,
            RecoveryDecision.RECONCILIATION_REQUIRED,
            RemediationCode.AUTHORIZATION_BOUNDARY_LOCKED,
            "Authorization state is outside the locked rehearsal boundary; no resume may be inferred.",
        )

    alert = observation.alert
    sync = observation.sync
    roaming = observation.roaming

    if observation.operation in {Operation.RESET, Operation.DISCHARGE}:
        if (observation.session_status == "INCIDENT_FROZEN" or alert.incident_frozen) and not alert.forensic_package_present:
            return _decision(
                observation,
                "unresolved_incident_without_forensic_package",
                False,
                RecoveryDecision.RECONCILIATION_REQUIRED,
                RemediationCode.FORENSIC_PACKAGE_REQUIRED,
                "Incident-frozen session cannot reset or discharge without a forensic package.",
            )
        if not alert.resolved:
            return _decision(
                observation,
                "unresolved_alert_blocks_reset_or_discharge",
                False,
                RecoveryDecision.RECONCILIATION_REQUIRED,
                RemediationCode.UNRESOLVED_ALERT_BLOCKS_RESET,
                "An unresolved alert blocks destructive reset/discharge even when acknowledged.",
            )
        if not observation.operator_confirmation_present:
            return _decision(
                observation,
                "resolved_alert_requires_operator_confirmation",
                False,
                RecoveryDecision.OPERATOR_CONFIRMATION_REQUIRED,
                RemediationCode.ACKNOWLEDGED_ALERT_MONITORING_RESUME,
                "Resolved workflow still requires explicit operator confirmation before reset/discharge.",
            )
        return _decision(
            observation,
            "reset_or_discharge_reconciled",
            True,
            RecoveryDecision.SOFTWARE_RESUME_ELIGIBLE,
            RemediationCode.NO_OPEN_ALERT,
            "Software rehearsal permits the next controlled step after explicit confirmation.",
        )

    if observation.operation is Operation.MONITORING_RESUME:
        if (observation.session_status == "INCIDENT_FROZEN" or alert.incident_frozen) and not alert.forensic_package_present:
            return _decision(
                observation,
                "incident_resume_blocked_without_forensic_package",
                False,
                RecoveryDecision.RECONCILIATION_REQUIRED,
                RemediationCode.INCIDENT_FREEZE_REQUIRED,
                "Monitoring resume remains blocked until incident evidence is present.",
            )
        if alert.resolved:
            return _decision(
                observation,
                "resolved_alert_monitoring_resume",
                True,
                RecoveryDecision.SOFTWARE_RESUME_ELIGIBLE,
                RemediationCode.NO_OPEN_ALERT,
                "No unresolved alert remains for the session.",
            )
        if alert.acknowledged:
            return _decision(
                observation,
                "acknowledged_alert_monitoring_resume",
                True,
                RecoveryDecision.SOFTWARE_RESUME_ELIGIBLE,
                RemediationCode.ACKNOWLEDGED_ALERT_MONITORING_RESUME,
                "Acknowledged alert may resume monitoring in the software rehearsal; clinical action remains external.",
            )
        return _decision(
            observation,
            "unacknowledged_alert_blocks_monitoring_resume",
            False,
            RecoveryDecision.OPERATOR_CONFIRMATION_REQUIRED,
            RemediationCode.UNACKNOWLEDGED_ALERT_REQUIRES_OPERATOR,
            "Unacknowledged alert requires operator action before monitoring resume.",
        )

    if observation.operation is Operation.SYNC_RETRY:
        if sync.stale_revision:
            return _decision(
                observation,
                "sync_stale_revision",
                False,
                RecoveryDecision.RECONCILIATION_REQUIRED,
                RemediationCode.STALE_REVISION_409,
                "Stale revision is a conflict, not a retryable transport failure; refresh authoritative state first.",
            )
        if sync.acknowledged and sync.last_status_code == 200:
            return _decision(
                observation,
                "sync_acknowledged_idempotent_or_first_success",
                True,
                RecoveryDecision.SOFTWARE_RESUME_ELIGIBLE,
                RemediationCode.SYNC_ACKNOWLEDGED,
                "Structured 200 acknowledgment is authoritative for the sync bundle.",
            )
        if sync.dead_lettered or sync.attempt_count >= sync.retry_limit:
            return _decision(
                observation,
                "sync_retry_limit_exceeded",
                False,
                RecoveryDecision.RECONCILIATION_REQUIRED,
                RemediationCode.SYNC_DEAD_LETTER,
                "Retry limit is exceeded; classify the bundle as dead-letter and require reconciliation.",
            )
        return _decision(
            observation,
            "sync_retry_pending",
            False,
            RecoveryDecision.OPERATOR_CONFIRMATION_REQUIRED,
            RemediationCode.SYNC_RETRY_PENDING,
            "Transport failure remains retryable within the bounded retry budget.",
        )

    if roaming.expected_revision is None or roaming.current_revision is None:
        return _decision(
            observation,
            "roaming_revision_missing",
            False,
            RecoveryDecision.RECONCILIATION_REQUIRED,
            RemediationCode.STALE_REVISION_409,
            "Roaming command requires both expected and authoritative revisions.",
        )
    if roaming.expected_revision != roaming.current_revision:
        return _decision(
            observation,
            "roaming_command_stale_revision",
            False,
            RecoveryDecision.RECONCILIATION_REQUIRED,
            RemediationCode.STALE_REVISION_409,
            "Roaming command must be rejected with a 409-style stale revision conflict.",
        )
    if roaming.idempotency_replay and roaming.existing_status == "COMMITTED":
        return _decision(
            observation,
            "roaming_command_idempotent_replay",
            True,
            RecoveryDecision.SOFTWARE_RESUME_ELIGIBLE,
            RemediationCode.IDEMPOTENT_REPLAY,
            "Authoritative committed result may be replayed without applying the command twice.",
        )
    return _decision(
        observation,
        "roaming_command_revision_current",
        True,
        RecoveryDecision.SOFTWARE_RESUME_ELIGIBLE,
        RemediationCode.ROAMING_COMMAND_ELIGIBLE,
        "Expected revision matches authoritative revision; command remains subject to endpoint authorization.",
    )


def build_reconciliation_matrix() -> tuple[DecisionContract, ...]:
    """Return deterministic representative scenarios for evidence and tests."""
    scenarios: Iterable[ReconciliationObservation] = (
        ReconciliationObservation(
            operation=Operation.MONITORING_RESUME,
            alert=AlertObservation(alert_ref="alert-ack-001", session_ref="session-001", acknowledged=True),
        ),
        ReconciliationObservation(
            operation=Operation.RESET,
            alert=AlertObservation(alert_ref="alert-open-001", session_ref="session-002", acknowledged=True),
        ),
        ReconciliationObservation(
            operation=Operation.RESET,
            session_status="INCIDENT_FROZEN",
            alert=AlertObservation(alert_ref="alert-red-001", session_ref="session-003", incident_frozen=True),
        ),
        ReconciliationObservation(
            operation=Operation.SYNC_RETRY,
            sync=SyncObservation(bundle_ref="bundle-ack-001", acknowledged=True, last_status_code=200),
        ),
        ReconciliationObservation(
            operation=Operation.SYNC_RETRY,
            sync=SyncObservation(bundle_ref="bundle-dead-001", attempt_count=3, retry_limit=3, last_status_code=503),
        ),
        ReconciliationObservation(
            operation=Operation.SYNC_RETRY,
            sync=SyncObservation(bundle_ref="bundle-stale-001", stale_revision=True, last_status_code=409),
        ),
        ReconciliationObservation(
            operation=Operation.ROAMING_COMMAND,
            roaming=RoamingObservation(command_ref="command-stale-001", expected_revision=4, current_revision=5),
        ),
        ReconciliationObservation(
            operation=Operation.ROAMING_COMMAND,
            roaming=RoamingObservation(command_ref="command-current-001", expected_revision=5, current_revision=5),
        ),
    )
    return tuple(evaluate_reconciliation(item) for item in scenarios)


def matrix_payload() -> dict[str, Any]:
    """Serialize the matrix without exposing raw identifiers."""
    rows = [row.to_dict() for row in build_reconciliation_matrix()]
    return {
        "contract": "ALERT_SYNC_RECONCILIATION_MATRIX_V1",
        "mode": "SOFTWARE_SIMULATION_ONLY",
        "authorization_boundary": {
            "external_authority": "NONE",
            "clinical_validation_authorized": False,
            "production_authorized": False,
            "runtime_authority": "NONE",
        },
        "rows": rows,
        "row_count": len(rows),
    }


def matrix_json() -> str:
    return json.dumps(matrix_payload(), sort_keys=True, indent=2)


if __name__ == "__main__":
    print(matrix_json())
