"""Fixture-only Sync/Alert replay harness.

The harness models local state transitions without touching SQLite, the network,
HIS/EMR, a scheduler, provider APIs, or the production runtime. It is intended
for software rehearsal and evidence generation only.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
import hashlib
import json
import re
from typing import Any, Iterable


class ReplayOperation(StrEnum):
    SYNC_ATTEMPT = "SYNC_ATTEMPT"
    ACKNOWLEDGMENT_REPLAY = "ACKNOWLEDGMENT_REPLAY"
    DEAD_LETTER_REPLAY = "DEAD_LETTER_REPLAY"
    SNAPSHOT_REFRESH = "SNAPSHOT_REFRESH"


class ReplayState(StrEnum):
    NOT_STARTED = "NOT_STARTED"
    RETAINED_FOR_RETRY = "RETAINED_FOR_RETRY"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    DEAD_LETTER = "DEAD_LETTER"
    PARTIAL_WRITE_DETECTED = "PARTIAL_WRITE_DETECTED"
    STALE_SNAPSHOT = "STALE_SNAPSHOT"
    RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"


class RecoveryDecision(StrEnum):
    RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"
    OPERATOR_CONFIRMATION_REQUIRED = "OPERATOR_CONFIRMATION_REQUIRED"
    SOFTWARE_REPLAY_ELIGIBLE = "SOFTWARE_REPLAY_ELIGIBLE"
    SOFTWARE_RESUME_ELIGIBLE = "SOFTWARE_RESUME_ELIGIBLE"


class RemediationCode(StrEnum):
    SYNC_RETAINED_FOR_RETRY = "SYNC_RETAINED_FOR_RETRY"
    SYNC_DEAD_LETTER = "SYNC_DEAD_LETTER"
    DEAD_LETTER_REPLAY_CONFIRMATION_REQUIRED = "DEAD_LETTER_REPLAY_CONFIRMATION_REQUIRED"
    DEAD_LETTER_REPLAY_ELIGIBLE = "DEAD_LETTER_REPLAY_ELIGIBLE"
    IDEMPOTENT_ACK_REPLAY = "IDEMPOTENT_ACK_REPLAY"
    ACKNOWLEDGMENT_COMMITTED = "ACKNOWLEDGMENT_COMMITTED"
    ACK_BUNDLE_ID_MISMATCH = "ACK_BUNDLE_ID_MISMATCH"
    PARTIAL_SYNC_WRITE_DETECTED = "PARTIAL_SYNC_WRITE_DETECTED"
    STALE_SNAPSHOT_REFRESH_REQUIRED = "STALE_SNAPSHOT_REFRESH_REQUIRED"
    FUTURE_SNAPSHOT_REVISION = "FUTURE_SNAPSHOT_REVISION"
    SNAPSHOT_CURRENT = "SNAPSHOT_CURRENT"
    INVALID_FIXTURE = "INVALID_FIXTURE"
    AUTHORIZATION_BOUNDARY_LOCKED = "AUTHORIZATION_BOUNDARY_LOCKED"


class ReplayFixtureError(ValueError):
    """Raised when a fixture violates the replay contract."""


@dataclass(frozen=True, slots=True)
class AuthorizationBoundary:
    external_authority: str = "NONE"
    clinical_validation_authorized: bool = False
    production_authorized: bool = False
    runtime_authority: str = "NONE"


@dataclass(frozen=True, slots=True)
class SyncFixture:
    bundle_ref: str
    attempt_count: int = 0
    retry_limit: int = 3
    status_code: int | None = None
    acknowledged: bool = False
    acknowledged_bundle_ref: str | None = None
    persisted_synced: bool = False
    acknowledgment_recorded: bool = False
    purged_aggregate_count: int = 0
    dead_lettered: bool = False


@dataclass(frozen=True, slots=True)
class SnapshotFixture:
    snapshot_ref: str
    client_revision: int | None
    authoritative_revision: int


@dataclass(frozen=True, slots=True)
class ReplayFixture:
    operation: ReplayOperation
    sync: SyncFixture | None = None
    snapshot: SnapshotFixture | None = None
    operator_confirmation_present: bool = False
    authorization: AuthorizationBoundary = field(default_factory=AuthorizationBoundary)


@dataclass(frozen=True, slots=True)
class ReplayDecision:
    scenario_id: str
    operation: str
    state: str
    resume_permitted: bool
    recovery_decision: str
    remediation_code: str
    duplicate_safe: bool
    purge_permitted: bool
    purge_executed: bool
    replay_permitted: bool
    replay_executed: bool
    refresh_required: bool
    mutation_performed: bool
    reason: str
    opaque_refs: dict[str, str] = field(default_factory=dict)
    authorization_boundary_locked: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_RAW_MARKERS = (
    re.compile(r"(?:^|[-_ ])(?:hn|an|mrn)(?:[-_ :]|$)", re.IGNORECASE),
    re.compile(r"patient[_ -]?(?:id|token|name|identity)", re.IGNORECASE),
    re.compile(r"(?:^|[-_ ])(?:name|address|phone|dob)(?:[-_ :]|$)", re.IGNORECASE),
)


def _validate_opaque_ref(value: str | None, field_name: str) -> None:
    if value is None or not isinstance(value, str) or not value.strip() or len(value) > 256:
        raise ReplayFixtureError(f"{field_name}_invalid")
    if any(marker.search(value) for marker in _RAW_MARKERS):
        raise ReplayFixtureError(f"{field_name}_must_be_opaque")


def _opaque_ref(value: str, namespace: str) -> str:
    return f"{namespace}:{hashlib.sha256(value.encode('utf-8')).hexdigest()[:20]}"


def _locked(boundary: AuthorizationBoundary) -> bool:
    return (
        boundary.external_authority == "NONE"
        and boundary.clinical_validation_authorized is False
        and boundary.production_authorized is False
        and boundary.runtime_authority == "NONE"
    )


def _validate_fixture(fixture: ReplayFixture) -> None:
    if not isinstance(fixture.operation, ReplayOperation):
        raise ReplayFixtureError("operation_invalid")
    if fixture.sync is not None:
        _validate_opaque_ref(fixture.sync.bundle_ref, "bundle_ref")
        _validate_opaque_ref(fixture.sync.acknowledged_bundle_ref, "acknowledged_bundle_ref") if fixture.sync.acknowledged_bundle_ref else None
        if fixture.sync.attempt_count < 0 or fixture.sync.retry_limit < 0:
            raise ReplayFixtureError("retry_bounds_invalid")
        if fixture.sync.status_code is not None and not 100 <= fixture.sync.status_code <= 599:
            raise ReplayFixtureError("status_code_invalid")
        if fixture.sync.purged_aggregate_count < 0:
            raise ReplayFixtureError("purge_count_invalid")
    if fixture.snapshot is not None:
        _validate_opaque_ref(fixture.snapshot.snapshot_ref, "snapshot_ref")
        if fixture.snapshot.authoritative_revision < 0:
            raise ReplayFixtureError("authoritative_revision_invalid")
        if fixture.snapshot.client_revision is not None and fixture.snapshot.client_revision < 0:
            raise ReplayFixtureError("client_revision_invalid")


def _refs(fixture: ReplayFixture) -> dict[str, str]:
    values: dict[str, str] = {}
    if fixture.sync is not None:
        values["bundle_ref"] = _opaque_ref(fixture.sync.bundle_ref, "bundle")
    if fixture.snapshot is not None:
        values["snapshot_ref"] = _opaque_ref(fixture.snapshot.snapshot_ref, "snapshot")
    return values


def _invalid_decision(fixture: ReplayFixture, reason: str) -> ReplayDecision:
    return ReplayDecision(
        scenario_id="invalid_fixture",
        operation=str(getattr(fixture.operation, "value", fixture.operation)),
        state=ReplayState.RECONCILIATION_REQUIRED.value,
        resume_permitted=False,
        recovery_decision=RecoveryDecision.RECONCILIATION_REQUIRED.value,
        remediation_code=RemediationCode.INVALID_FIXTURE.value,
        duplicate_safe=False,
        purge_permitted=False,
        purge_executed=False,
        replay_permitted=False,
        replay_executed=False,
        refresh_required=False,
        mutation_performed=False,
        reason=reason,
        opaque_refs={},
        authorization_boundary_locked=True,
    )


def _decision(
    fixture: ReplayFixture,
    scenario_id: str,
    state: ReplayState,
    resume_permitted: bool,
    recovery_decision: RecoveryDecision,
    remediation_code: RemediationCode,
    reason: str,
    *,
    duplicate_safe: bool = False,
    purge_permitted: bool = False,
    replay_permitted: bool = False,
    refresh_required: bool = False,
    authorization_boundary_locked: bool | None = None,
) -> ReplayDecision:
    return ReplayDecision(
        scenario_id=scenario_id,
        operation=fixture.operation.value,
        state=state.value,
        resume_permitted=resume_permitted,
        recovery_decision=recovery_decision.value,
        remediation_code=remediation_code.value,
        duplicate_safe=duplicate_safe,
        purge_permitted=purge_permitted,
        purge_executed=False,
        replay_permitted=replay_permitted,
        replay_executed=False,
        refresh_required=refresh_required,
        mutation_performed=False,
        reason=reason,
        opaque_refs=_refs(fixture),
        authorization_boundary_locked=(
            _locked(fixture.authorization)
            if authorization_boundary_locked is None
            else authorization_boundary_locked
        ),
    )


def evaluate_replay(fixture: ReplayFixture) -> ReplayDecision:
    """Evaluate a fixture without executing sync, purge, replay, or refresh."""
    try:
        _validate_fixture(fixture)
    except ReplayFixtureError as exc:
        return _invalid_decision(fixture, str(exc))

    if not _locked(fixture.authorization):
        return _decision(
            fixture,
            "authorization_boundary_locked",
            ReplayState.RECONCILIATION_REQUIRED,
            False,
            RecoveryDecision.RECONCILIATION_REQUIRED,
            RemediationCode.AUTHORIZATION_BOUNDARY_LOCKED,
            "Authorization mutation is outside the fixture-only rehearsal boundary.",
            authorization_boundary_locked=False,
        )

    if fixture.operation is ReplayOperation.SNAPSHOT_REFRESH:
        snapshot = fixture.snapshot
        if snapshot is None or snapshot.client_revision is None:
            return _decision(
                fixture,
                "snapshot_revision_missing",
                ReplayState.RECONCILIATION_REQUIRED,
                False,
                RecoveryDecision.RECONCILIATION_REQUIRED,
                RemediationCode.STALE_SNAPSHOT_REFRESH_REQUIRED,
                "A snapshot refresh requires a bounded client revision and authoritative revision.",
                refresh_required=True,
            )
        if snapshot.client_revision < snapshot.authoritative_revision:
            return _decision(
                fixture,
                "stale_snapshot_requires_refresh",
                ReplayState.STALE_SNAPSHOT,
                False,
                RecoveryDecision.RECONCILIATION_REQUIRED,
                RemediationCode.STALE_SNAPSHOT_REFRESH_REQUIRED,
                "Client cursor is stale; refresh from the authoritative Fixed Hub snapshot before mutation.",
                refresh_required=True,
            )
        if snapshot.client_revision > snapshot.authoritative_revision:
            return _decision(
                fixture,
                "future_snapshot_revision_rejected",
                ReplayState.RECONCILIATION_REQUIRED,
                False,
                RecoveryDecision.RECONCILIATION_REQUIRED,
                RemediationCode.FUTURE_SNAPSHOT_REVISION,
                "Client cursor is ahead of the authoritative revision and cannot be trusted.",
                refresh_required=True,
            )
        return _decision(
            fixture,
            "snapshot_revision_current",
            ReplayState.NOT_STARTED,
            True,
            RecoveryDecision.SOFTWARE_RESUME_ELIGIBLE,
            RemediationCode.SNAPSHOT_CURRENT,
            "Client cursor matches the authoritative revision; no refresh mutation is needed.",
        )

    sync = fixture.sync
    if sync is None:
        return _invalid_decision(fixture, "sync_fixture_required")

    if sync.purged_aggregate_count > 0 and not sync.persisted_synced:
        return _decision(
            fixture,
            "partial_sync_write_detected",
            ReplayState.PARTIAL_WRITE_DETECTED,
            False,
            RecoveryDecision.RECONCILIATION_REQUIRED,
            RemediationCode.PARTIAL_SYNC_WRITE_DETECTED,
            "Local aggregate purge is visible without a committed synced marker; block replay and reconcile.",
        )
    if sync.persisted_synced and not sync.acknowledgment_recorded:
        return _decision(
            fixture,
            "partial_acknowledgment_write_detected",
            ReplayState.PARTIAL_WRITE_DETECTED,
            False,
            RecoveryDecision.RECONCILIATION_REQUIRED,
            RemediationCode.PARTIAL_SYNC_WRITE_DETECTED,
            "Synced state is visible without the acknowledgment record; block replay and reconcile.",
        )

    if fixture.operation is ReplayOperation.SYNC_ATTEMPT:
        if sync.acknowledged and sync.status_code == 200 and sync.acknowledgment_recorded:
            return _decision(
                fixture,
                "acknowledgment_committed",
                ReplayState.ACKNOWLEDGED,
                True,
                RecoveryDecision.SOFTWARE_RESUME_ELIGIBLE,
                RemediationCode.ACKNOWLEDGMENT_COMMITTED,
                "Structured acknowledgment and local committed marker agree; no purge is executed by the harness.",
                purge_permitted=True,
            )
        if sync.dead_lettered or sync.attempt_count >= sync.retry_limit:
            return _decision(
                fixture,
                "retry_limit_to_dead_letter",
                ReplayState.DEAD_LETTER,
                False,
                RecoveryDecision.RECONCILIATION_REQUIRED,
                RemediationCode.SYNC_DEAD_LETTER,
                "Bounded retry budget is exhausted; classify the bundle as dead-letter.",
            )
        return _decision(
            fixture,
            "sync_retained_for_retry",
            ReplayState.RETAINED_FOR_RETRY,
            False,
            RecoveryDecision.OPERATOR_CONFIRMATION_REQUIRED,
            RemediationCode.SYNC_RETAINED_FOR_RETRY,
            "Remote acknowledgment is absent or non-success; retain local data for bounded retry.",
        )

    if fixture.operation is ReplayOperation.ACKNOWLEDGMENT_REPLAY:
        if sync.acknowledged and sync.persisted_synced and sync.acknowledgment_recorded:
            return _decision(
                fixture,
                "duplicate_acknowledgment_replay",
                ReplayState.ACKNOWLEDGED,
                True,
                RecoveryDecision.SOFTWARE_RESUME_ELIGIBLE,
                RemediationCode.IDEMPOTENT_ACK_REPLAY,
                "Acknowledgment is already committed; replay is idempotent and does not permit a second purge.",
                duplicate_safe=True,
            )
        if sync.acknowledged_bundle_ref != sync.bundle_ref:
            return _decision(
                fixture,
                "acknowledgment_bundle_identity_mismatch",
                ReplayState.RECONCILIATION_REQUIRED,
                False,
                RecoveryDecision.RECONCILIATION_REQUIRED,
                RemediationCode.ACK_BUNDLE_ID_MISMATCH,
                "Acknowledgment identity does not match the local bundle; reject before state mutation.",
            )
        return _decision(
            fixture,
            "acknowledgment_replay_requires_commit",
            ReplayState.RECONCILIATION_REQUIRED,
            False,
            RecoveryDecision.RECONCILIATION_REQUIRED,
            RemediationCode.PARTIAL_SYNC_WRITE_DETECTED,
            "Replay lacks a complete committed acknowledgment state; reconcile before retry.",
        )

    if sync.dead_lettered or sync.attempt_count >= sync.retry_limit:
        if not fixture.operator_confirmation_present:
            return _decision(
                fixture,
                "dead_letter_replay_confirmation_required",
                ReplayState.DEAD_LETTER,
                False,
                RecoveryDecision.OPERATOR_CONFIRMATION_REQUIRED,
                RemediationCode.DEAD_LETTER_REPLAY_CONFIRMATION_REQUIRED,
                "Dead-letter replay requires explicit operator confirmation; execution remains disabled.",
            )
        return _decision(
            fixture,
            "dead_letter_replay_software_eligible",
            ReplayState.DEAD_LETTER,
            True,
            RecoveryDecision.SOFTWARE_REPLAY_ELIGIBLE,
            RemediationCode.DEAD_LETTER_REPLAY_ELIGIBLE,
            "Software rehearsal records replay eligibility only; no external replay or runtime mutation is executed.",
            replay_permitted=True,
        )
    return _decision(
        fixture,
        "dead_letter_replay_not_applicable",
        ReplayState.RECONCILIATION_REQUIRED,
        False,
        RecoveryDecision.RECONCILIATION_REQUIRED,
        RemediationCode.SYNC_DEAD_LETTER,
        "Dead-letter replay requires an exhausted or explicitly dead-lettered bundle.",
    )


def _scenario_fixtures() -> Iterable[ReplayFixture]:
    yield ReplayFixture(
        operation=ReplayOperation.SYNC_ATTEMPT,
        sync=SyncFixture(bundle_ref="bundle-opaque-retry-001", attempt_count=1, retry_limit=3, status_code=503),
    )
    yield ReplayFixture(
        operation=ReplayOperation.SYNC_ATTEMPT,
        sync=SyncFixture(bundle_ref="bundle-opaque-dead-001", attempt_count=3, retry_limit=3, status_code=503),
    )
    yield ReplayFixture(
        operation=ReplayOperation.DEAD_LETTER_REPLAY,
        sync=SyncFixture(bundle_ref="bundle-opaque-dead-002", attempt_count=3, retry_limit=3, dead_lettered=True),
    )
    yield ReplayFixture(
        operation=ReplayOperation.DEAD_LETTER_REPLAY,
        sync=SyncFixture(bundle_ref="bundle-opaque-dead-003", attempt_count=3, retry_limit=3, dead_lettered=True),
        operator_confirmation_present=True,
    )
    yield ReplayFixture(
        operation=ReplayOperation.SYNC_ATTEMPT,
        sync=SyncFixture(
            bundle_ref="bundle-opaque-ack-001",
            attempt_count=1,
            status_code=200,
            acknowledged=True,
            acknowledged_bundle_ref="bundle-opaque-ack-001",
            persisted_synced=True,
            acknowledgment_recorded=True,
        ),
    )
    yield ReplayFixture(
        operation=ReplayOperation.ACKNOWLEDGMENT_REPLAY,
        sync=SyncFixture(
            bundle_ref="bundle-opaque-ack-002",
            status_code=200,
            acknowledged=True,
            acknowledged_bundle_ref="bundle-opaque-ack-002",
            persisted_synced=True,
            acknowledgment_recorded=True,
            purged_aggregate_count=4,
        ),
    )
    yield ReplayFixture(
        operation=ReplayOperation.ACKNOWLEDGMENT_REPLAY,
        sync=SyncFixture(
            bundle_ref="bundle-opaque-mismatch-001",
            status_code=200,
            acknowledged_bundle_ref="bundle-opaque-other-001",
        ),
    )
    yield ReplayFixture(
        operation=ReplayOperation.ACKNOWLEDGMENT_REPLAY,
        sync=SyncFixture(bundle_ref="bundle-opaque-partial-001", purged_aggregate_count=4),
    )
    yield ReplayFixture(
        operation=ReplayOperation.SNAPSHOT_REFRESH,
        snapshot=SnapshotFixture(snapshot_ref="snapshot-opaque-stale-001", client_revision=11, authoritative_revision=12),
    )
    yield ReplayFixture(
        operation=ReplayOperation.SNAPSHOT_REFRESH,
        snapshot=SnapshotFixture(snapshot_ref="snapshot-opaque-current-001", client_revision=12, authoritative_revision=12),
    )


def build_replay_matrix() -> tuple[ReplayDecision, ...]:
    return tuple(evaluate_replay(fixture) for fixture in _scenario_fixtures())


def matrix_payload() -> dict[str, Any]:
    rows = [decision.to_dict() for decision in build_replay_matrix()]
    return {
        "contract": "SYNC_ALERT_REPLAY_HARNESS_V1",
        "mode": "FIXTURE_ONLY_SOFTWARE_SIMULATION",
        "read_only": True,
        "execution_performed": False,
        "external_transmission_performed": False,
        "authorization_boundary": asdict(AuthorizationBoundary()),
        "rows": rows,
        "row_count": len(rows),
    }


def matrix_json() -> str:
    return json.dumps(matrix_payload(), sort_keys=True, indent=2)


if __name__ == "__main__":
    print(matrix_json())
