from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class ClinicalValidationReadinessError(ValueError):
    pass


@dataclass(frozen=True)
class ClinicalValidationPlan:
    protocol_version: str
    intended_use: str
    excluded_uses: tuple[str, ...]
    clinical_owner: str
    technical_owner: str
    inclusion_exclusion_criteria: bool
    privacy_security_review: bool
    security_review: bool
    clinical_governance_approval: bool
    data_retention_decision: bool
    consent_or_waiver: bool
    training_complete: bool
    stop_conditions: bool
    incident_response: bool
    rollback_plan: bool
    manual_fallback: bool
    backup_restore_verified: bool
    device_qualification: bool
    auth_transport_validation: bool
    his_integration_verified: bool
    independent_review_plan: bool
    analysis_plan: bool
    real_world_authorization: bool = False
    evidence_class: str = "SOFTWARE_FIXTURE_UNVERIFIED"

    def validate(self) -> list[str]:
        issues: list[str] = []
        for field_name in ("protocol_version", "intended_use", "clinical_owner", "technical_owner"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                issues.append(f"missing_{field_name}")
        if not self.excluded_uses:
            issues.append("excluded_uses_required")
        boolean_gates = (
            "inclusion_exclusion_criteria",
            "privacy_security_review",
            "security_review",
            "clinical_governance_approval",
            "data_retention_decision",
            "consent_or_waiver",
            "training_complete",
            "stop_conditions",
            "incident_response",
            "rollback_plan",
            "manual_fallback",
            "backup_restore_verified",
            "device_qualification",
            "auth_transport_validation",
            "his_integration_verified",
            "independent_review_plan",
            "analysis_plan",
        )
        for field_name in boolean_gates:
            if not getattr(self, field_name):
                issues.append(f"missing_gate_{field_name}")
        if self.evidence_class != "SOFTWARE_FIXTURE_UNVERIFIED":
            issues.append("software_preflight_cannot_assert_external_evidence")
        return issues

    def preflight(self) -> dict[str, Any]:
        issues = self.validate()
        if issues:
            status = "NOT_READY_FOR_CLINICAL_VALIDATION"
        else:
            status = "READY_FOR_EXTERNAL_GOVERNANCE_REVIEW"
        return {
            "status": status,
            "protocol_version": self.protocol_version,
            "intended_use": self.intended_use,
            "excluded_uses": list(self.excluded_uses),
            "missing_gates": issues,
            "real_world_authorization": False,
            "evidence_class": "SOFTWARE_PREFLIGHT_UNVERIFIED",
            "clinical_approval_required": True,
            "note": "Software preflight does not authorize testing with real patients.",
        }


def require_not_ready_for_real_world(plan: ClinicalValidationPlan) -> None:
    result = plan.preflight()
    if result["status"] != "READY_FOR_EXTERNAL_GOVERNANCE_REVIEW":
        raise ClinicalValidationReadinessError("clinical_validation_preflight_blocked")
    if result["real_world_authorization"] is not False or result["clinical_approval_required"] is not True:
        raise ClinicalValidationReadinessError("real_world_authorization_boundary_breached")
