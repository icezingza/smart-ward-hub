from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any


class ClinicalValidationReadinessError(ValueError):
    pass


OPAQUE_REF = re.compile(r"[A-Za-z0-9._~-]{3,128}")
RAW_ID = re.compile(r"\b(?:HN|AN|MRN|NATIONAL_ID)\s*[-_:]?\s*[A-Z0-9-]+\b", re.IGNORECASE)
SECRET_MARKER = re.compile(r"(?:BEGIN (?:RSA|EC|OPENSSH|DSA|PRIVATE) KEY|Bearer\s+\S+|(?:password|secret|token|private_key|seed)\s*[:=]\s*\S+)", re.IGNORECASE)
RAW_CONTACT = re.compile(r"(?:@|\+?\d[\d\s().-]{6,})")
EVIDENCE_CLASS = "SOFTWARE_FIXTURE_UNVERIFIED"
PREFLIGHT_EVIDENCE_CLASS = "SOFTWARE_PREFLIGHT_UNVERIFIED"
LOCKED_AUTHORIZATION_BOUNDARY = {
    "external_authority": "NONE",
    "clinical_validation_authorized": False,
    "production_authorized": False,
    "runtime_authority": "NONE",
    "pilot_gate_status": "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION",
}

BOOLEAN_GATES = (
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


def _safe_reference(value: Any, field: str) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return f"missing_{field}"
    if OPAQUE_REF.fullmatch(value.strip()) is None:
        return f"invalid_{field}"
    if RAW_ID.search(value) or RAW_CONTACT.search(value) or SECRET_MARKER.search(value):
        return f"unsafe_{field}"
    return None


def _safe_text(value: Any, field: str) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return f"missing_{field}"
    if RAW_ID.search(value) or RAW_CONTACT.search(value) or SECRET_MARKER.search(value):
        return f"unsafe_{field}"
    return None


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
    evidence_class: str = EVIDENCE_CLASS

    def validate(self) -> list[str]:
        issues: list[str] = []
        protocol_issue = _safe_reference(self.protocol_version, "protocol_version")
        if protocol_issue:
            issues.append(protocol_issue)
        for field_name in ("intended_use",):
            issue = _safe_text(getattr(self, field_name), field_name)
            if issue:
                issues.append(issue)
        if not isinstance(self.excluded_uses, (tuple, list)) or not self.excluded_uses:
            issues.append("excluded_uses_required")
        else:
            for index, excluded_use in enumerate(self.excluded_uses):
                issue = _safe_text(excluded_use, f"excluded_uses[{index}]")
                if issue:
                    issues.append(issue)
        for field_name in ("clinical_owner", "technical_owner"):
            issue = _safe_reference(getattr(self, field_name), field_name)
            if issue:
                issues.append(issue)
        for field_name in BOOLEAN_GATES:
            if getattr(self, field_name) is not True:
                issues.append(f"missing_gate_{field_name}")
        if self.real_world_authorization is not False:
            issues.append("real_world_authorization_must_remain_false")
        if self.evidence_class != EVIDENCE_CLASS:
            issues.append("software_preflight_cannot_assert_external_evidence")
        return issues

    def preflight(self) -> dict[str, Any]:
        issues = self.validate()
        status = "NOT_READY_FOR_CLINICAL_VALIDATION" if issues else "READY_FOR_EXTERNAL_GOVERNANCE_REVIEW"
        return {
            "status": status,
            "protocol_version": self.protocol_version,
            "intended_use": self.intended_use,
            "excluded_uses": list(self.excluded_uses) if isinstance(self.excluded_uses, (tuple, list)) else [],
            "missing_gates": list(issues),
            "real_world_authorization": False,
            "clinical_validation_authorized": False,
            "production_authorized": False,
            "runtime_authority": "NONE",
            "pilot_gate_status": "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION",
            "authorization_boundary": dict(LOCKED_AUTHORIZATION_BOUNDARY),
            "evidence_class": PREFLIGHT_EVIDENCE_CLASS,
            "software_evidence_only": True,
            "clinical_approval_required": True,
            "note": "Software preflight does not authorize testing with real patients.",
        }


def require_not_ready_for_real_world(plan: ClinicalValidationPlan) -> None:
    result = plan.preflight()
    if result["status"] != "READY_FOR_EXTERNAL_GOVERNANCE_REVIEW":
        raise ClinicalValidationReadinessError("clinical_validation_preflight_blocked")
    if (
        result["real_world_authorization"] is not False
        or result["clinical_validation_authorized"] is not False
        or result["production_authorized"] is not False
        or result["clinical_approval_required"] is not True
        or result["authorization_boundary"] != LOCKED_AUTHORIZATION_BOUNDARY
    ):
        raise ClinicalValidationReadinessError("real_world_authorization_boundary_breached")
