from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import re
from typing import Any


SAFE_REF = re.compile(r"[A-Za-z0-9._:/-]{1,160}")
RAW_ID = re.compile(r"\b(?:HN|AN|MRN|NATIONAL_ID)\s*[-_:]?\s*[A-Z0-9-]+\b", re.IGNORECASE)
FORBIDDEN_CLAIMS = {"clinical-ready", "tamper-proof", "production-ready", "hipaa/pdpa compliant 100%", "clinical validated"}
VALID_STATUSES = {"OPEN", "EVIDENCE_SUBMITTED", "BLOCKED"}


class ExternalValidationPackageError(ValueError):
    pass


@dataclass(frozen=True)
class GateEvidence:
    evidence_ref: str
    evidence_class: str
    submitted_at_utc: str

    def validate(self) -> None:
        if not SAFE_REF.fullmatch(self.evidence_ref) or RAW_ID.search(self.evidence_ref):
            raise ExternalValidationPackageError("unsafe_evidence_reference")
        if self.evidence_class.strip().upper() in {"CLINICAL_VALIDATED", "PRODUCTION_READY", "TAMPER_PROOF"}:
            raise ExternalValidationPackageError("unsupported_evidence_claim")
        try:
            parsed = datetime.fromisoformat(self.submitted_at_utc.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ExternalValidationPackageError("invalid_evidence_timestamp") from exc
        if parsed.tzinfo is None:
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
        if not SAFE_REF.fullmatch(self.gate_id) or not SAFE_REF.fullmatch(self.domain):
            raise ExternalValidationPackageError("unsafe_gate_identifier")
        if not self.owner_role.strip() or not self.required_evidence:
            raise ExternalValidationPackageError("gate_owner_and_evidence_required")
        if self.status not in VALID_STATUSES:
            raise ExternalValidationPackageError("invalid_gate_status")
        for item in self.evidence:
            item.validate()

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
        if not reason.strip():
            raise ExternalValidationPackageError("blocker_reason_required")
        self.status = "BLOCKED"
        self.blocker = reason.strip()[:240]

    def reopen(self, reason: str) -> None:
        if self.status != "BLOCKED":
            raise ExternalValidationPackageError("gate_not_blocked")
        if not reason.strip():
            raise ExternalValidationPackageError("reopen_reason_required")
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

    def validate(self) -> None:
        if not SAFE_REF.fullmatch(self.package_id) or RAW_ID.search(self.package_id):
            raise ExternalValidationPackageError("unsafe_package_identifier")
        if not self.scope.strip() or not self.intended_use.strip():
            raise ExternalValidationPackageError("package_scope_and_intended_use_required")
        if self.real_world_authorization is not False:
            raise ExternalValidationPackageError("software_package_cannot_authorize_real_world_testing")
        lowered = self.claim_boundary.lower()
        if any(claim in lowered for claim in FORBIDDEN_CLAIMS):
            raise ExternalValidationPackageError("forbidden_claim_boundary")
        if not self.gates:
            raise ExternalValidationPackageError("validation_gates_required")
        for gate in self.gates.values():
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

    def readiness_summary(self) -> dict[str, Any]:
        self.validate()
        counts = {status: 0 for status in VALID_STATUSES}
        for gate in self.gates.values():
            counts[gate.status] += 1
        return {
            "package_id": self.package_id,
            "scope": self.scope,
            "gate_count": len(self.gates),
            "status_counts": counts,
            "ready_for_external_review": counts["OPEN"] == 0 and counts["BLOCKED"] == 0,
            "real_world_authorization": False,
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
