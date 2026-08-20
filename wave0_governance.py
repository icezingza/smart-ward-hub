from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any


UTC = timezone.utc
RAW_IDENTITY_RE = re.compile(r"(?i)(?<![A-Z0-9])(?:HN|AN|MRN|NATIONAL[_ -]?ID)(?:[:#\s-]+)[A-Z0-9][A-Z0-9_-]{2,}(?![A-Z0-9])")
ROLE_SET = {
    "clinical_owner",
    "privacy_security_reviewer",
    "security_owner",
    "integration_owner",
    "reliability_owner",
    "forensic_owner",
    "ward_manager",
    "host_operator",
    "independent_reviewer",
    "stop_authority",
    "evidence_custodian",
}
REQUIRED_ROLES = {
    "clinical_owner",
    "independent_reviewer",
    "stop_authority",
    "evidence_custodian",
}


class GovernanceState(str, Enum):
    DRAFT = "DRAFT"
    PENDING_APPOINTMENTS = "PENDING_APPOINTMENTS"
    PENDING_SCOPE_SIGNATURE = "PENDING_SCOPE_SIGNATURE"
    PENDING_TEST_WINDOW_APPROVAL = "PENDING_TEST_WINDOW_APPROVAL"
    READY_TO_FREEZE = "READY_TO_FREEZE"
    FROZEN_LOCAL_PENDING_EXTERNAL_REVIEW = "FROZEN_LOCAL_PENDING_EXTERNAL_REVIEW"
    GOVERNANCE_PACKAGE_READY_FOR_EXTERNAL_REVIEW = "GOVERNANCE_PACKAGE_READY_FOR_EXTERNAL_REVIEW"
    BLOCKED = "BLOCKED"
    REOPENED = "REOPENED"


class GovernanceValidationError(ValueError):
    pass


def _aware(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise GovernanceValidationError(f"{field_name} must be timezone-aware")
    return value


def _reject_identity(value: str, field_name: str) -> None:
    if RAW_IDENTITY_RE.search(value):
        raise GovernanceValidationError(f"{field_name} contains raw identity")


def _stable_hash(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class Appointment:
    appointment_id: str
    role: str
    principal_ref: str
    organization_ref: str
    appointed_by_role: str
    scope: str
    effective_from: datetime
    expires_at: datetime
    conflict_declaration: str
    appointment_evidence_ref: str
    verification_status: str = "PENDING_EXTERNAL_VERIFICATION"

    def validate(self, now: datetime) -> None:
        if self.role not in ROLE_SET:
            raise GovernanceValidationError(f"unsupported governance role: {self.role}")
        if not self.appointment_id or not self.principal_ref or not self.organization_ref:
            raise GovernanceValidationError("appointment identity fields are required")
        for name, value in {
            "principal_ref": self.principal_ref,
            "organization_ref": self.organization_ref,
            "scope": self.scope,
            "appointment_evidence_ref": self.appointment_evidence_ref,
        }.items():
            _reject_identity(value, name)
        start = _aware(self.effective_from, "effective_from")
        expiry = _aware(self.expires_at, "expires_at")
        if expiry <= start:
            raise GovernanceValidationError("appointment expires_at must be after effective_from")
        if expiry <= _aware(now, "now"):
            raise GovernanceValidationError("appointment is expired")
        if self.conflict_declaration not in {"DECLARED_REVIEWED", "DECLARED_UNRESOLVED", "NOT_DECLARED"}:
            raise GovernanceValidationError("invalid conflict_declaration")
        if self.verification_status not in {"PENDING_EXTERNAL_VERIFICATION", "VERIFIED_OUTSIDE_BASELINE"}:
            raise GovernanceValidationError("invalid appointment verification_status")


@dataclass(frozen=True)
class SignedScope:
    scope_id: str
    purpose: str
    in_scope: tuple[str, ...]
    out_of_scope: tuple[str, ...]
    environment: str
    test_window_ref: str
    rollback_plan_ref: str
    stop_criteria_ref: str
    expiry: datetime
    signed_by_external_role: str
    signature_ref: str
    verification_status: str = "PENDING_EXTERNAL_VERIFICATION"

    def validate(self, now: datetime) -> None:
        if not self.scope_id or not self.purpose or not self.environment:
            raise GovernanceValidationError("scope identity and purpose are required")
        for name, values in {
            "purpose": (self.purpose,),
            "in_scope": self.in_scope,
            "out_of_scope": self.out_of_scope,
            "test_window_ref": (self.test_window_ref,),
            "rollback_plan_ref": (self.rollback_plan_ref,),
            "stop_criteria_ref": (self.stop_criteria_ref,),
            "signature_ref": (self.signature_ref,),
        }.items():
            for value in values:
                _reject_identity(value, name)
        if not self.in_scope or not self.out_of_scope:
            raise GovernanceValidationError("signed scope must have in_scope and out_of_scope")
        if self.signed_by_external_role not in ROLE_SET:
            raise GovernanceValidationError("signed_by_external_role must be an approved role")
        if self.verification_status not in {"PENDING_EXTERNAL_VERIFICATION", "VERIFIED_OUTSIDE_BASELINE"}:
            raise GovernanceValidationError("invalid scope verification_status")
        if _aware(self.expiry, "scope.expiry") <= _aware(now, "now"):
            raise GovernanceValidationError("scope is expired")


@dataclass(frozen=True)
class TestWindow:
    window_id: str
    starts_at: datetime
    ends_at: datetime
    allowed_systems: tuple[str, ...]
    allowed_devices: tuple[str, ...]
    allowed_networks: tuple[str, ...]
    allowed_data_class: str
    operator_roles: tuple[str, ...]
    preflight_checks: tuple[str, ...]
    rollback_steps: tuple[str, ...]
    stop_authority_ref: str
    incident_channel_ref: str
    evidence_capture_plan: str
    approval_status: str = "PENDING_EXTERNAL_VERIFICATION"

    def validate(self, now: datetime) -> None:
        start = _aware(self.starts_at, "test_window.starts_at")
        end = _aware(self.ends_at, "test_window.ends_at")
        if end <= start:
            raise GovernanceValidationError("test window ends_at must be after starts_at")
        if end <= _aware(now, "now"):
            raise GovernanceValidationError("test window is expired")
        if not self.allowed_systems or not self.allowed_devices or not self.allowed_networks:
            raise GovernanceValidationError("test window allowlists are required")
        if self.allowed_data_class not in {"SYNTHETIC_NON_PII", "DE_IDENTIFIED", "CLINICAL_GOVERNED"}:
            raise GovernanceValidationError("invalid allowed_data_class")
        if self.allowed_data_class != "SYNTHETIC_NON_PII":
            raise GovernanceValidationError("non-synthetic data requires separate clinical governance evidence")
        if not self.operator_roles or not self.preflight_checks or not self.rollback_steps:
            raise GovernanceValidationError("test window operational controls are required")
        for name, values in {
            "allowed_systems": self.allowed_systems,
            "allowed_devices": self.allowed_devices,
            "allowed_networks": self.allowed_networks,
            "operator_roles": self.operator_roles,
            "preflight_checks": self.preflight_checks,
            "rollback_steps": self.rollback_steps,
            "stop_authority_ref": (self.stop_authority_ref,),
            "incident_channel_ref": (self.incident_channel_ref,),
            "evidence_capture_plan": (self.evidence_capture_plan,),
        }.items():
            for value in values:
                _reject_identity(value, name)
        if self.approval_status not in {"PENDING_EXTERNAL_VERIFICATION", "VERIFIED_OUTSIDE_BASELINE"}:
            raise GovernanceValidationError("invalid test-window approval_status")


@dataclass(frozen=True)
class StopAuthority:
    authority_id: str
    role: str
    trigger_classes: tuple[str, ...]
    notification_ref: str
    restart_approval_ref: str
    verification_status: str = "PENDING_EXTERNAL_VERIFICATION"

    def validate(self) -> None:
        if self.role != "stop_authority":
            raise GovernanceValidationError("stop authority must use stop_authority role")
        if not self.trigger_classes or not self.notification_ref or not self.restart_approval_ref:
            raise GovernanceValidationError("stop authority controls are required")
        for value in (self.notification_ref, self.restart_approval_ref, *self.trigger_classes):
            _reject_identity(value, "stop_authority")
        if self.verification_status not in {"PENDING_EXTERNAL_VERIFICATION", "VERIFIED_OUTSIDE_BASELINE"}:
            raise GovernanceValidationError("invalid stop authority verification_status")


@dataclass(frozen=True)
class FreezeRecord:
    freeze_id: str
    manifest_version: int
    manifest_sha256: str
    previous_manifest_sha256: str | None
    frozen_at: datetime
    frozen_by_role: str
    scope_id: str
    window_id: str
    change_policy: str
    custody_ref: str
    external_verification_required: bool = True
    external_authority: str = "NONE"

    def validate(self) -> None:
        _aware(self.frozen_at, "frozen_at")
        if self.frozen_by_role != "evidence_custodian":
            raise GovernanceValidationError("freeze must be created by evidence_custodian")
        if len(self.manifest_sha256) != 64 or not re.fullmatch(r"[0-9a-f]{64}", self.manifest_sha256):
            raise GovernanceValidationError("invalid manifest sha256")
        if self.manifest_version < 1 or not self.scope_id or not self.window_id:
            raise GovernanceValidationError("invalid freeze identity")
        if self.change_policy != "APPEND_ONLY_NEW_VERSION_WITH_REASON":
            raise GovernanceValidationError("invalid freeze change policy")
        if not self.external_verification_required or self.external_authority != "NONE":
            raise GovernanceValidationError("local freeze cannot self-claim external authority")
        _reject_identity(self.custody_ref, "custody_ref")


@dataclass
class Wave0GovernancePackage:
    package_id: str
    created_at: datetime
    appointments: list[Appointment] = field(default_factory=list)
    scope: SignedScope | None = None
    test_window: TestWindow | None = None
    stop_authority: StopAuthority | None = None
    freeze: FreezeRecord | None = None
    state: GovernanceState = GovernanceState.DRAFT
    external_authority: str = "NONE"
    clinical_validation_authorized: bool = False
    production_authorized: bool = False
    runtime_authority: str = "NONE"

    def validate(self, now: datetime | None = None) -> dict[str, Any]:
        now = now or datetime.now(UTC)
        checks: dict[str, bool] = {}
        errors: list[str] = []
        try:
            _aware(self.created_at, "created_at")
            checks["package_timestamp"] = True
        except GovernanceValidationError as exc:
            checks["package_timestamp"] = False
            errors.append(str(exc))
        seen_ids: set[str] = set()
        for appointment in self.appointments:
            try:
                if appointment.appointment_id in seen_ids:
                    raise GovernanceValidationError("duplicate appointment_id")
                seen_ids.add(appointment.appointment_id)
                appointment.validate(now)
            except GovernanceValidationError as exc:
                errors.append(str(exc))
        checks["appointments_schema"] = not any("appointment" in error for error in errors)
        role_set = {appointment.role for appointment in self.appointments}
        checks["required_roles_present"] = REQUIRED_ROLES.issubset(role_set)
        if not checks["required_roles_present"]:
            errors.append("required governance roles are missing")
        checks["scope_schema"] = self.scope is not None
        if self.scope is not None:
            try:
                self.scope.validate(now)
            except GovernanceValidationError as exc:
                checks["scope_schema"] = False
                errors.append(str(exc))
        else:
            errors.append("signed scope is missing")
        checks["test_window_schema"] = self.test_window is not None
        if self.test_window is not None:
            try:
                self.test_window.validate(now)
            except GovernanceValidationError as exc:
                checks["test_window_schema"] = False
                errors.append(str(exc))
        else:
            errors.append("test window is missing")
        checks["stop_authority_schema"] = self.stop_authority is not None
        if self.stop_authority is not None:
            try:
                self.stop_authority.validate()
            except GovernanceValidationError as exc:
                checks["stop_authority_schema"] = False
                errors.append(str(exc))
        else:
            errors.append("stop authority is missing")
        checks["freeze_schema"] = self.freeze is not None
        if self.freeze is not None:
            try:
                self.freeze.validate()
            except GovernanceValidationError as exc:
                checks["freeze_schema"] = False
                errors.append(str(exc))
        checks["authorization_locked"] = (
            self.external_authority == "NONE"
            and self.clinical_validation_authorized is False
            and self.production_authorized is False
            and self.runtime_authority == "NONE"
        )
        if not checks["authorization_locked"]:
            errors.append("authorization boundary is not locked")
        checks["external_verification_pending"] = not all(
            item.verification_status == "VERIFIED_OUTSIDE_BASELINE" for item in self.appointments
        ) or (self.scope is not None and self.scope.verification_status != "VERIFIED_OUTSIDE_BASELINE")
        checks["local_ready_for_external_review"] = all(
            checks.get(key, False)
            for key in (
                "package_timestamp",
                "appointments_schema",
                "required_roles_present",
                "scope_schema",
                "test_window_schema",
                "stop_authority_schema",
                "freeze_schema",
                "authorization_locked",
            )
        )
        if errors:
            self.state = GovernanceState.BLOCKED
        elif self.freeze is None and all(
            checks.get(key, False)
            for key in (
                "package_timestamp",
                "appointments_schema",
                "required_roles_present",
                "scope_schema",
                "test_window_schema",
                "stop_authority_schema",
                "authorization_locked",
            )
        ):
            self.state = GovernanceState.READY_TO_FREEZE
        elif self.freeze is not None:
            self.state = GovernanceState.GOVERNANCE_PACKAGE_READY_FOR_EXTERNAL_REVIEW
        return {
            "package_id": self.package_id,
            "state": self.state.value,
            "checks": checks,
            "errors": errors,
            "external_authority": self.external_authority,
            "clinical_validation_authorized": self.clinical_validation_authorized,
            "production_authorized": self.production_authorized,
            "runtime_authority": self.runtime_authority,
        }

    def freeze_local(self, manifest_entries: list[dict[str, Any]], frozen_at: datetime, reason: str = "") -> FreezeRecord:
        if self.freeze is not None:
            raise GovernanceValidationError("evidence register is already frozen; create a new version")
        if self.scope is None or self.test_window is None:
            raise GovernanceValidationError("scope and test window are required before freeze")
        if not reason and self.state == GovernanceState.BLOCKED:
            raise GovernanceValidationError("blocked package requires a change reason before freeze")
        _aware(frozen_at, "frozen_at")
        canonical = sorted(manifest_entries, key=lambda entry: str(entry.get("evidence_id", "")))
        manifest_sha256 = _stable_hash(canonical)
        self.freeze = FreezeRecord(
            freeze_id=f"{self.package_id}-freeze-1",
            manifest_version=1,
            manifest_sha256=manifest_sha256,
            previous_manifest_sha256=None,
            frozen_at=frozen_at,
            frozen_by_role="evidence_custodian",
            scope_id=self.scope.scope_id,
            window_id=self.test_window.window_id,
            change_policy="APPEND_ONLY_NEW_VERSION_WITH_REASON",
            custody_ref="local://wave0/freeze-simulation",
        )
        self.state = GovernanceState.FROZEN_LOCAL_PENDING_EXTERNAL_REVIEW
        return self.freeze

    def export(self) -> dict[str, Any]:
        if self.freeze is None:
            raise GovernanceValidationError("cannot export an unfrozen governance package")
        return {
            "package_id": self.package_id,
            "state": self.state.value,
            "appointments": [appointment.__dict__ for appointment in self.appointments],
            "scope": self.scope.__dict__ if self.scope else None,
            "test_window": self.test_window.__dict__ if self.test_window else None,
            "stop_authority": self.stop_authority.__dict__ if self.stop_authority else None,
            "freeze": self.freeze.__dict__,
            "external_authority": self.external_authority,
            "clinical_validation_authorized": self.clinical_validation_authorized,
            "production_authorized": self.production_authorized,
            "runtime_authority": self.runtime_authority,
        }


def build_synthetic_wave0_package(now: datetime | None = None) -> Wave0GovernancePackage:
    now = now or datetime(2026, 8, 20, 8, 0, tzinfo=UTC)
    expiry = now + timedelta(days=30)
    roles = sorted(REQUIRED_ROLES | {"privacy_security_reviewer", "evidence_custodian"})
    appointments = [
        Appointment(
            appointment_id=f"wave0-appt-{index:02d}",
            role=role,
            principal_ref=f"external-principal-{role}",
            organization_ref="external-org-review-boundary",
            appointed_by_role="external_governance_secretary",
            scope=f"Wave 0 governance responsibility for {role}",
            effective_from=now,
            expires_at=expiry,
            conflict_declaration="DECLARED_REVIEWED",
            appointment_evidence_ref=f"external://appointment/{role}",
        )
        for index, role in enumerate(roles, start=1)
    ]
    package = Wave0GovernancePackage(
        package_id="wave0-governance-20260820",
        created_at=now,
        appointments=appointments,
        scope=SignedScope(
            scope_id="wave0-scope-20260820",
            purpose="Prepare external authorization evidence without clinical or production activity",
            in_scope=("synthetic corpus", "isolated software regression", "non-production manifest freeze"),
            out_of_scope=("real patient care", "production network", "raw identifiers", "real HIS/IdP"),
            environment="isolated-software-baseline",
            test_window_ref="wave0-window-20260820",
            rollback_plan_ref="local://wave0/rollback-plan",
            stop_criteria_ref="local://wave0/stop-criteria",
            expiry=expiry,
            signed_by_external_role="independent_reviewer",
            signature_ref="external://scope-signature-pending",
        ),
        test_window=TestWindow(
            window_id="wave0-window-20260820",
            starts_at=now,
            ends_at=now + timedelta(hours=8),
            allowed_systems=("smart-ward-hub-test-runner", "evidence-manifest-validator"),
            allowed_devices=("synthetic-fixture-only",),
            allowed_networks=("sandbox-local-only",),
            allowed_data_class="SYNTHETIC_NON_PII",
            operator_roles=("evidence_custodian", "independent_reviewer"),
            preflight_checks=("zero-pii-scan", "manifest-hash-check", "authorization-boundary-check"),
            rollback_steps=("stop-runner", "retain-freeze-record", "notify-stop-authority"),
            stop_authority_ref="external://stop-authority-pending",
            incident_channel_ref="external://incident-channel-pending",
            evidence_capture_plan="local://wave0/evidence-capture-plan",
        ),
        stop_authority=StopAuthority(
            authority_id="wave0-stop-authority-20260820",
            role="stop_authority",
            trigger_classes=("SAFETY", "PRIVACY", "IDENTITY", "INFRASTRUCTURE", "EVIDENCE", "GOVERNANCE"),
            notification_ref="external://stop-notification-pending",
            restart_approval_ref="external://restart-approval-pending",
        ),
    )
    return package
