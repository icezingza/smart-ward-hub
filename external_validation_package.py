from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import re
from typing import Any

SAFE_REF = re.compile(r"[A-Za-z0-9._:/-]{1,160}")
RAW_ID = re.compile(r"\b(?:HN|AN|MRN|NATIONAL_ID)(?:\s*[-_:]\s*[A-Z0-9-]{2,}|\s+\d[A-Z0-9-]{1,})\b", re.IGNORECASE)
RAW_CONTACT = re.compile(r"(?:@|\+?\d[\d\s().-]{6,})")
SECRET_MARKER = re.compile(r"(?:BEGIN (?:RSA|EC|OPENSSH|DSA|PRIVATE) KEY|Bearer\s+\S+|(?:password|secret|token|private_key|seed)\s*[:=]\s*\S+)", re.IGNORECASE)
FORBIDDEN_CLAIMS = {"clinical-ready", "tamper-proof", "production-ready", "hipaa/pdpa compliant 100%", "clinical validated", "clinical validation passed"}
UNSUPPORTED_EVIDENCE_CLAIMS = {"CLINICAL_VALIDATED", "PRODUCTION_READY", "TAMPER_PROOF", "CLINICAL_ACCURACY", "CLINICAL_EFFECTIVENESS"}
VALID_STATUSES = {"OPEN", "EVIDENCE_SUBMITTED", "BLOCKED"}
LOCKED_EXTERNAL_OWNER_APPOINTMENT = "PENDING_EXTERNAL_APPOINTMENT"


class ExternalValidationPackageError(ValueError):
    pass


def _safe_ref(value: Any, error: str) -> None:
    if not isinstance(value, str) or not value.strip() or not SAFE_REF.fullmatch(value.strip()) or RAW_ID.search(value) or RAW_CONTACT.search(value) or SECRET_MARKER.search(value):
        raise ExternalValidationPackageError(error)


def _safe_text(value: Any, error: str, *, max_length: int = 512) -> None:
    if not isinstance(value, str) or not value.strip() or len(value) > max_length or RAW_ID.search(value) or RAW_CONTACT.search(value) or SECRET_MARKER.search(value):
        raise ExternalValidationPackageError(error)


def _safe_reason(value: Any, error: str) -> None:
    _safe_text(value, error, max_length=240)


@dataclass(frozen=True)
class GateEvidence:
    evidence_ref: str
    evidence_class: str
    submitted_at_utc: str

    def validate(self) -> None:
        _safe_ref(self.evidence_ref, "unsafe_evidence_reference")
        if not isinstance(self.evidence_class, str) or not self.evidence_class.strip() or RAW_ID.search(self.evidence_class) or RAW_CONTACT.search(self.evidence_class) or SECRET_MARKER.search(self.evidence_class):
            raise ExternalValidationPackageError("invalid_evidence_class")
        if self.evidence_class.strip().upper() in UNSUPPORTED_EVIDENCE_CLAIMS:
            raise ExternalValidationPackageError("unsupported_evidence_claim")
        if not isinstance(self.submitted_at_utc, str):
            raise ExternalValidationPackageError("invalid_evidence_timestamp")
        try:
            parsed = datetime.fromisoformat(self.submitted_at_utc.replace("Z", "+00:00"))
        except (AttributeError, TypeError, ValueError) as exc:
            raise ExternalValidationPackageError("invalid_evidence_timestamp") from exc
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ExternalValidationPackageError("evidence_timestamp_must_be_timezone_aware")


@dataclass
class ValidationGate:
    gate_id: str
    domain: str
    owner_role: str
    required_evidence: tuple[str, ...]
    status: str = "OPEN"
    blocker: str | None = None
    evidence: list[GateEvidence] = field(default_factory=list)

    def validate(self) -> None:
        _safe_ref(self.gate_id, "unsafe_gate_identifier")
        _safe_ref(self.domain, "unsafe_gate_identifier")
        _safe_ref(self.owner_role, "unsafe_gate_owner")
        if not isinstance(self.required_evidence, (tuple, list)) or not self.required_evidence:
            raise ExternalValidationPackageError("gate_owner_and_evidence_required")
        for required in self.required_evidence:
            _safe_ref(required, "unsafe_required_evidence_reference")
        if self.status not in VALID_STATUSES:
            raise ExternalValidationPackageError("invalid_gate_status")
        if self.status == "BLOCKED":
            if self.blocker is None or not self.blocker.strip():
                raise ExternalValidationPackageError("blocked_gate_requires_reason")
        elif self.blocker is not None:
            raise ExternalValidationPackageError("non_blocked_gate_cannot_have_blocker")
        if not isinstance(self.evidence, list):
            raise ExternalValidationPackageError("gate_evidence_must_be_list")
        seen: set[str] = set()
        for item in self.evidence:
            if not isinstance(item, GateEvidence):
                raise ExternalValidationPackageError("invalid_gate_evidence_record")
            item.validate()
            if item.evidence_ref in seen:
                raise ExternalValidationPackageError("duplicate_gate_evidence")
            seen.add(item.evidence_ref)

    def submit_evidence(self, item: GateEvidence) -> None:
        self.validate()
        if self.status == "BLOCKED":
            raise ExternalValidationPackageError("blocked_gate_requires_reopen")
        item.validate()
        if item.evidence_ref in {existing.evidence_ref for existing in self.evidence}:
            raise ExternalValidationPackageError("duplicate_gate_evidence")
        self.evidence.append(item)
        self.status = "EVIDENCE_SUBMITTED"
        self.blocker = None

    def block(self, reason: str) -> None:
        if self.status == "BLOCKED":
            raise ExternalValidationPackageError("gate_already_blocked")
        _safe_reason(reason, "blocker_reason_required")
        self.status = "BLOCKED"
        self.blocker = reason.strip()

    def reopen(self, reason: str) -> None:
        if self.status != "BLOCKED":
            raise ExternalValidationPackageError("gate_not_blocked")
        _safe_reason(reason, "reopen_reason_required")
        self.status = "OPEN"
        self.blocker = None


@dataclass
class ExternalValidationPackage:
    package_id: str
    scope: str
    intended_use: str
    claim_boundary: str = "CONTROLLED_PROTOTYPE_SOFTWARE_EVIDENCE_ONLY"
    real_world_authorization: bool = False
    gates: dict[str, ValidationGate] = field(default_factory=dict)
    external_owner_appointment: str = LOCKED_EXTERNAL_OWNER_APPOINTMENT
    execution_status: str = "NOT_STARTED"
    clinical_validation_authorized: bool = False
    production_authorized: bool = False

    def validate(self) -> None:
        _safe_ref(self.package_id, "unsafe_package_identifier")
        _safe_text(self.scope, "package_scope_and_intended_use_required")
        _safe_text(self.intended_use, "package_scope_and_intended_use_required")
        if self.real_world_authorization is not False:
            raise ExternalValidationPackageError("software_package_cannot_authorize_real_world_testing")
        if self.clinical_validation_authorized is not False or self.production_authorized is not False:
            raise ExternalValidationPackageError("software_package_cannot_authorize_real_world_testing")
        if self.external_owner_appointment != LOCKED_EXTERNAL_OWNER_APPOINTMENT:
            raise ExternalValidationPackageError("external_owner_appointment_boundary_breached")
        if self.execution_status != "NOT_STARTED":
            raise ExternalValidationPackageError("external_execution_boundary_breached")
        if not isinstance(self.claim_boundary, str) or not self.claim_boundary.strip():
            raise ExternalValidationPackageError("forbidden_claim_boundary")
        lowered = self.claim_boundary.lower()
        if any(claim in lowered for claim in FORBIDDEN_CLAIMS):
            raise ExternalValidationPackageError("forbidden_claim_boundary")
        if not isinstance(self.gates, dict) or not self.gates:
            raise ExternalValidationPackageError("validation_gates_required")
        for gate_key, gate in self.gates.items():
            if not isinstance(gate, ValidationGate) or gate_key != gate.gate_id:
                raise ExternalValidationPackageError("gate_registry_key_mismatch")
            gate.validate()

    def submit_evidence(self, gate_id: str, evidence_ref: str, evidence_class: str) -> None:
        self.validate()
        gate = self.gates.get(gate_id)
        if gate is None:
            raise ExternalValidationPackageError("unknown_validation_gate")
        timestamp = datetime.now(timezone.utc).isoformat()
        gate.submit_evidence(GateEvidence(evidence_ref, evidence_class, timestamp))

    def block_gate(self, gate_id: str, reason: str) -> None:
        self.validate()
        gate = self.gates.get(gate_id)
        if gate is None:
            raise ExternalValidationPackageError("unknown_validation_gate")
        gate.block(reason)

    def reopen_gate(self, gate_id: str, reason: str) -> None:
        self.validate()
        gate = self.gates.get(gate_id)
        if gate is None:
            raise ExternalValidationPackageError("unknown_validation_gate")
        gate.reopen(reason)

    def readiness_summary(self) -> dict[str, Any]:
        self.validate()
        counts = {status: 0 for status in VALID_STATUSES}
        for gate in self.gates.values():
            counts[gate.status] += 1
        return {
            "package_id": self.package_id,
            "scope": self.scope,
            "gate_count": len(self.gates),
            "status_counts": dict(counts),
            "ready_for_external_review": counts["OPEN"] == 0 and counts["BLOCKED"] == 0,
            "external_owner_appointment": LOCKED_EXTERNAL_OWNER_APPOINTMENT,
            "execution_status": "NOT_STARTED",
            "real_world_authorization": False,
            "clinical_validation_authorized": False,
            "production_authorized": False,
            "runtime_authority": "NONE",
            "evidence_class": "COORDINATION_ARTIFACT_UNVERIFIED",
            "clinical_governance_required": True,
        }


def default_pilot_package() -> ExternalValidationPackage:
    gate_definitions = (
        ("GV-01", "clinical_governance", "clinical_owner", ("approved_protocol", "consent_or_waiver", "signed_scope")),
        ("GV-02", "privacy_security", "privacy_security_reviewer", ("zero_pii_review", "retention_decision", "access_control_review")),
        ("GV-03", "his_admission", "integration_owner", ("real_his_transcript", "fhir_ack_reconciliation", "failure_recovery")),
        ("GV-04", "identity_transport", "security_owner", ("real_oidc_validation", "real_mtls_handshake", "key_rotation_transcript")),
        ("GV-05", "fixed_hub_host", "host_operator", ("acer_hardening_checklist", "firewall_acl_evidence", "service_recovery")),
        ("GV-06", "hardware_recovery", "reliability_owner", ("serial_loopback_s015", "power_loss_drill", "disk_full_drill")),
        ("GV-07", "forensic_anchor", "forensic_owner", ("external_worm_receipt", "trusted_timestamp", "cross_boundary_verify")),
        ("GV-08", "device_trust", "security_owner", ("manufacturer_provenance", "hardware_key_custody", "revocation_distribution")),
        ("GV-09", "clinical_operations", "ward_manager", ("staff_training", "manual_fallback_sop", "alarm_fatigue_review")),
        ("GV-10", "independent_review", "independent_reviewer", ("analysis_plan", "adjudication_plan", "audit_export")),
    )
    package = ExternalValidationPackage(
        package_id="smart-ward-pilot-validation-v1",
        scope="Controlled non-interventional external validation coordination for Smart Ward Hub",
        intended_use="Evidence coordination and governance review only; not diagnosis or treatment",
    )
    package.gates = {
        gate_id: ValidationGate(gate_id, domain, owner, evidence)
        for gate_id, domain, owner, evidence in gate_definitions
    }
    package.validate()
    return package
