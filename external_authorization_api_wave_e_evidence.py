"""Strict non-production evidence records and dossier state machine for Wave E.

This module is a coordination/evidence contract only. It cannot grant external,
clinical, production, or runtime authority.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
import re
from typing import Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
SIMULATION_CONTRACT_VERSION = "external-auth-sim-v2"
WAVE_E_TEST_CASE_IDS = tuple(f"T-{index:02d}" for index in range(1, 13))


class DossierState(str, Enum):
    EXTERNAL_VALIDATION_NOT_STARTED = "EXTERNAL_VALIDATION_NOT_STARTED"
    READY_FOR_EXTERNAL_OWNER_APPOINTMENT = "READY_FOR_EXTERNAL_OWNER_APPOINTMENT"
    READY_FOR_EXTERNAL_EXECUTION = "READY_FOR_EXTERNAL_EXECUTION"
    IN_EXECUTION = "IN_EXECUTION"
    BLOCKED = "BLOCKED"
    READY_FOR_INDEPENDENT_REVIEW = "READY_FOR_INDEPENDENT_REVIEW"
    CLOSED_NO_AUTHORIZATION = "CLOSED_NO_AUTHORIZATION"


DOSSIER_TRANSITIONS: dict[DossierState, set[DossierState]] = {
    DossierState.EXTERNAL_VALIDATION_NOT_STARTED: {
        DossierState.READY_FOR_EXTERNAL_OWNER_APPOINTMENT,
        DossierState.BLOCKED,
    },
    DossierState.READY_FOR_EXTERNAL_OWNER_APPOINTMENT: {
        DossierState.READY_FOR_EXTERNAL_EXECUTION,
        DossierState.BLOCKED,
    },
    DossierState.READY_FOR_EXTERNAL_EXECUTION: {
        DossierState.IN_EXECUTION,
        DossierState.BLOCKED,
    },
    DossierState.IN_EXECUTION: {
        DossierState.READY_FOR_INDEPENDENT_REVIEW,
        DossierState.BLOCKED,
    },
    DossierState.READY_FOR_INDEPENDENT_REVIEW: {
        DossierState.CLOSED_NO_AUTHORIZATION,
        DossierState.BLOCKED,
    },
    DossierState.BLOCKED: {
        DossierState.READY_FOR_EXTERNAL_OWNER_APPOINTMENT,
    },
    DossierState.CLOSED_NO_AUTHORIZATION: set(),
}


class EvidenceStatus(str, Enum):
    NOT_EXECUTED = "NOT_EXECUTED"
    EXECUTED_FAIL_CLOSED = "EXECUTED_FAIL_CLOSED"
    EXECUTED_BLOCKED = "EXECUTED_BLOCKED"
    EXECUTED_REQUIRES_CLARIFICATION = "EXECUTED_REQUIRES_CLARIFICATION"
    READY_FOR_INDEPENDENT_REVIEW = "READY_FOR_INDEPENDENT_REVIEW"


class FailureClass(str, Enum):
    NONE = "NONE"
    SAFE_NOT_SENT = "SAFE_NOT_SENT"
    COMMIT_UNKNOWN = "COMMIT_UNKNOWN"
    RESPONSE_UNTRUSTED = "RESPONSE_UNTRUSTED"
    IDENTITY_FAILURE = "IDENTITY_FAILURE"
    CUSTODY_FAILURE = "CUSTODY_FAILURE"
    CLOCK_UNTRUSTED = "CLOCK_UNTRUSTED"
    SCOPE_EXPIRED = "SCOPE_EXPIRED"
    REVOKED = "REVOKED"
    STALE_RESPONSE = "STALE_RESPONSE"
    INTEGRITY_FAILURE = "INTEGRITY_FAILURE"
    STOP_TRIGGERED = "STOP_TRIGGERED"
    OTHER = "OTHER"


class SignatureVerificationResult(str, Enum):
    NOT_APPLICABLE = "NOT_APPLICABLE"
    PASS = "PASS"
    FAIL = "FAIL"
    BLOCKED = "BLOCKED"


class TimeVerificationResult(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    BLOCKED = "BLOCKED"


class WaveEEvidenceRecord(BaseModel):
    """One test-case evidence record; never an authorization decision."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    schema_version: Literal["wave-e-evidence-v1"] = "wave-e-evidence-v1"
    contract_version: Literal["external-auth-sim-v2"] = SIMULATION_CONTRACT_VERSION
    test_run_id: str = Field(min_length=1, max_length=256)
    test_case_id: str = Field(pattern=r"^T-(0[1-9]|1[0-2])$")
    status: EvidenceStatus
    expected_result: str = Field(min_length=1, max_length=2048)
    actual_result: str = Field(min_length=1, max_length=2048)
    failure_class: FailureClass = FailureClass.NONE

    started_at_utc: datetime
    observed_at_utc: datetime
    completed_at_utc: datetime
    clock_source: str = Field(min_length=1, max_length=256)
    clock_skew_ms: int = Field(ge=0, le=86_400_000)
    time_verification_result: TimeVerificationResult

    endpoint_environment_id: str = Field(min_length=1, max_length=256)
    endpoint_identity_ref: str = Field(min_length=1, max_length=1024)
    tls_certificate_fingerprint: str = Field(min_length=1, max_length=256)
    identity_transport_ref: str = Field(min_length=1, max_length=1024)

    request_correlation_id: str = Field(min_length=1, max_length=256)
    idempotency_key_hash: str = Field(pattern=SHA256_RE.pattern)
    request_sha256: str = Field(pattern=SHA256_RE.pattern)
    response_sha256: str | None = Field(default=None, max_length=64)
    remote_receipt_id: str | None = Field(default=None, max_length=512)
    reconciliation_result: str = Field(min_length=1, max_length=1024)

    artifact_type: str = Field(min_length=1, max_length=128)
    artifact_sha256: str = Field(pattern=SHA256_RE.pattern)
    manifest_sha256: str = Field(pattern=SHA256_RE.pattern)
    artifact_size_bytes: int = Field(ge=0, le=10_000_000_000)
    artifact_record_count: int = Field(ge=0, le=10_000_000)

    signature_ref: str = Field(min_length=1, max_length=1024)
    key_id: str = Field(min_length=1, max_length=256)
    signature_algorithm: str = Field(min_length=1, max_length=128)
    signed_payload_hash: str | None = Field(default=None, max_length=64)
    signature_verification_result: SignatureVerificationResult
    independent_readback_ref: str = Field(min_length=1, max_length=1024)

    scope_id: str = Field(min_length=1, max_length=256)
    window_id: str = Field(min_length=1, max_length=256)
    expiry: datetime
    revocation_status: str = Field(min_length=1, max_length=256)

    stop_authority_ref: str = Field(min_length=1, max_length=1024)
    stop_trigger: str = Field(min_length=1, max_length=1024)
    stopped_at_utc: datetime | None = None
    stopped_by_role: str | None = Field(default=None, max_length=256)
    recovery_approved_by_role: str | None = Field(default=None, max_length=256)
    recovery_at_utc: datetime | None = None
    recovery_evidence_ref: str | None = Field(default=None, max_length=1024)

    topology: Literal["SINGLE_PROCESS", "MULTI_PROCESS", "MULTI_NODE", "UNKNOWN"]
    worker_count: int = Field(ge=0, le=10_000)
    limiter_backend: str = Field(min_length=1, max_length=256)
    quota_scope: str = Field(min_length=1, max_length=256)

    chain_of_custody_ref: str = Field(min_length=1, max_length=1024)
    prepared_by_role: str = Field(min_length=1, max_length=256)
    external_owner_role: str = Field(min_length=1, max_length=256)
    independent_verification_required: Literal[True] = True
    redaction: Literal["PASS"] = "PASS"
    raw_identity_present: Literal[False] = False

    external_authority: Literal["NONE"] = "NONE"
    clinical_validation_authorized: Literal[False] = False
    production_authorized: Literal[False] = False
    runtime_authority: Literal["NONE"] = "NONE"
    pilot_gate_status: Literal["BLOCKED_PENDING_EXTERNAL_AUTHORIZATION"] = "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION"
    claim_boundary: Literal["EXTERNAL_UNVERIFIED_PENDING_REVIEW"] = "EXTERNAL_UNVERIFIED_PENDING_REVIEW"

    _hash_fields: ClassVar[tuple[str, ...]] = (
        "idempotency_key_hash",
        "request_sha256",
        "artifact_sha256",
        "manifest_sha256",
    )

    @field_validator("started_at_utc", "observed_at_utc", "completed_at_utc", "expiry", "stopped_at_utc", "recovery_at_utc")
    @classmethod
    def require_timezone_aware(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must be timezone-aware")
        return value

    @field_validator("response_sha256", "signed_payload_hash")
    @classmethod
    def validate_optional_hash(cls, value: str | None) -> str | None:
        if value is not None and not SHA256_RE.fullmatch(value):
            raise ValueError("optional hash must be lowercase SHA-256")
        return value

    @model_validator(mode="after")
    def validate_cross_field_rules(self) -> "WaveEEvidenceRecord":
        if not (
            self.started_at_utc <= self.observed_at_utc <= self.completed_at_utc <= self.expiry
        ):
            raise ValueError("timestamps must be ordered and completed_at_utc must be before expiry")
        if self.time_verification_result is not TimeVerificationResult.PASS:
            if self.failure_class is not FailureClass.CLOCK_UNTRUSTED:
                raise ValueError("non-passing time verification requires CLOCK_UNTRUSTED failure")
            if self.status is EvidenceStatus.READY_FOR_INDEPENDENT_REVIEW:
                raise ValueError("untrusted time cannot be ready for independent review")
        if self.status is EvidenceStatus.READY_FOR_INDEPENDENT_REVIEW:
            if self.failure_class is not FailureClass.NONE:
                raise ValueError("review-ready evidence cannot carry an unresolved failure")
            if self.response_sha256 is None:
                raise ValueError("review-ready evidence requires response_sha256")
            if self.signature_verification_result is not SignatureVerificationResult.PASS:
                raise ValueError("review-ready evidence requires a verified signature")
            if not self.remote_receipt_id:
                raise ValueError("review-ready evidence requires remote_receipt_id")
            if self.independent_readback_ref.startswith("NOT_"):
                raise ValueError("review-ready evidence requires independent read-back")
        if self.signature_verification_result is SignatureVerificationResult.PASS:
            if self.signed_payload_hash is None or self.key_id.startswith("NOT_"):
                raise ValueError("passing signature verification requires key_id and signed payload hash")
        if self.failure_class is FailureClass.COMMIT_UNKNOWN and self.reconciliation_result.startswith("NOT_"):
            raise ValueError("COMMIT_UNKNOWN requires a reconciliation result")
        if self.status in {EvidenceStatus.EXECUTED_BLOCKED, EvidenceStatus.EXECUTED_FAIL_CLOSED} and self.failure_class is FailureClass.NONE:
            raise ValueError("blocked/fail-closed evidence requires a failure class")
        if self.stopped_at_utc is not None and not self.stopped_by_role:
            raise ValueError("stopped_at_utc requires stopped_by_role")
        if self.recovery_at_utc is not None:
            if not self.recovery_approved_by_role or not self.recovery_evidence_ref:
                raise ValueError("recovery requires approver role and evidence reference")
        if self.stopped_by_role and self.recovery_approved_by_role and self.stopped_by_role == self.recovery_approved_by_role:
            raise ValueError("stop authority and recovery approver must be distinct")
        if self.topology == "SINGLE_PROCESS" and self.worker_count not in {0, 1}:
            raise ValueError("single-process topology requires worker_count 0 or 1")
        return self


class WaveEEvidenceBundle(BaseModel):
    """Complete T-01..T-12 evidence set; review readiness only, never authority."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    schema_version: Literal["wave-e-evidence-bundle-v1"] = "wave-e-evidence-bundle-v1"
    contract_version: Literal["external-auth-sim-v2"] = SIMULATION_CONTRACT_VERSION
    test_run_id: str = Field(min_length=1, max_length=256)
    scope_id: str = Field(min_length=1, max_length=256)
    window_id: str = Field(min_length=1, max_length=256)
    dossier_state: Literal["READY_FOR_INDEPENDENT_REVIEW"] = "READY_FOR_INDEPENDENT_REVIEW"
    records: tuple[WaveEEvidenceRecord, ...] = Field(min_length=12, max_length=12)
    prepared_by_role: str = Field(min_length=1, max_length=256)
    evidence_custodian_role: str = Field(min_length=1, max_length=256)
    external_owner_role: str = Field(min_length=1, max_length=256)
    independent_verifier_role: str = Field(min_length=1, max_length=256)
    stop_authority_role: str = Field(min_length=1, max_length=256)
    recovery_approver_role: str = Field(min_length=1, max_length=256)
    independent_verification_required: Literal[True] = True
    redaction: Literal["PASS"] = "PASS"
    raw_identity_present: Literal[False] = False
    external_authority: Literal["NONE"] = "NONE"
    clinical_validation_authorized: Literal[False] = False
    production_authorized: Literal[False] = False
    runtime_authority: Literal["NONE"] = "NONE"
    pilot_gate_status: Literal["BLOCKED_PENDING_EXTERNAL_AUTHORIZATION"] = "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION"
    claim_boundary: Literal["EXTERNAL_UNVERIFIED_PENDING_REVIEW"] = "EXTERNAL_UNVERIFIED_PENDING_REVIEW"

    @model_validator(mode="after")
    def validate_bundle(self) -> "WaveEEvidenceBundle":
        case_ids = [record.test_case_id for record in self.records]
        if set(case_ids) != set(WAVE_E_TEST_CASE_IDS) or len(case_ids) != len(set(case_ids)):
            raise ValueError("bundle must contain exactly one record for each T-01 through T-12")
        if any(record.test_run_id != self.test_run_id for record in self.records):
            raise ValueError("all records must share test_run_id")
        if any(record.scope_id != self.scope_id or record.window_id != self.window_id for record in self.records):
            raise ValueError("all records must share scope_id and window_id")
        if any(record.contract_version != self.contract_version for record in self.records):
            raise ValueError("all records must share contract_version")
        if any(record.status is not EvidenceStatus.READY_FOR_INDEPENDENT_REVIEW for record in self.records):
            raise ValueError("review-ready bundle requires every record to be READY_FOR_INDEPENDENT_REVIEW")
        roles = {
            self.prepared_by_role,
            self.evidence_custodian_role,
            self.external_owner_role,
            self.independent_verifier_role,
            self.stop_authority_role,
            self.recovery_approver_role,
        }
        if len(roles) != 5:
            raise ValueError("custodian/preparer must be one role; owner, verifier, stop and recovery roles must be distinct")
        if self.prepared_by_role != self.evidence_custodian_role:
            raise ValueError("prepared_by_role must match evidence_custodian_role")
        for record in self.records:
            if record.stopped_by_role and record.stopped_by_role != self.stop_authority_role:
                raise ValueError("stopped_by_role must match stop_authority_role")
            if record.recovery_approved_by_role and record.recovery_approved_by_role != self.recovery_approver_role:
                raise ValueError("recovery_approved_by_role must match recovery_approver_role")
        return self

    def assert_no_authorization(self) -> None:
        if (
            self.external_authority != "NONE"
            or self.clinical_validation_authorized is not False
            or self.production_authorized is not False
            or self.runtime_authority != "NONE"
            or self.pilot_gate_status != "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION"
        ):
            raise ValueError("Wave E evidence bundle cannot carry authorization state")

    def model_dump_for_evidence(self) -> dict[str, Any]:
        self.assert_no_authorization()
        return self.model_dump(mode="json")


class DossierStateMachine(BaseModel):
    """Coordination state only; all authorization fields remain locked."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    state: DossierState = DossierState.EXTERNAL_VALIDATION_NOT_STARTED
    revision: int = Field(default=0, ge=0)
    last_transition_reason: str = "initial_state"
    last_transition_actor_role: str = "integration_owner"
    external_authority: Literal["NONE"] = "NONE"
    clinical_validation_authorized: Literal[False] = False
    production_authorized: Literal[False] = False
    runtime_authority: Literal["NONE"] = "NONE"
    pilot_gate_status: Literal["BLOCKED_PENDING_EXTERNAL_AUTHORIZATION"] = "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION"

    def transition(self, target: DossierState, *, actor_role: str, reason: str) -> "DossierStateMachine":
        if target not in DOSSIER_TRANSITIONS[self.state]:
            raise ValueError(f"invalid dossier transition: {self.state.value}->{target.value}")
        if not actor_role.strip() or not reason.strip():
            raise ValueError("actor_role and reason are required")
        if target is DossierState.BLOCKED and not reason.strip():
            raise ValueError("blocked transition requires reason")
        updated = self.model_copy(
            update={
                "state": target,
                "revision": self.revision + 1,
                "last_transition_reason": reason,
                "last_transition_actor_role": actor_role,
            }
        )
        updated.assert_no_authorization()
        return updated

    def assert_no_authorization(self) -> None:
        if (
            self.external_authority != "NONE"
            or self.clinical_validation_authorized is not False
            or self.production_authorized is not False
            or self.runtime_authority != "NONE"
            or self.pilot_gate_status != "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION"
        ):
            raise ValueError("Wave E dossier cannot carry authorization state")

    def model_dump_for_evidence(self) -> dict[str, Any]:
        self.assert_no_authorization()
        return self.model_dump(mode="json")
