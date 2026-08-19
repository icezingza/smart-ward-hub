from __future__ import annotations

from clinical_validation_readiness import ClinicalValidationPlan, ClinicalValidationReadinessError, require_not_ready_for_real_world


def plan(**overrides) -> ClinicalValidationPlan:
    values = {
        "protocol_version": "P1-006-v1",
        "intended_use": "Non-interventional shadow review of ward safety signals",
        "excluded_uses": ("diagnosis", "treatment order", "autonomous escalation"),
        "clinical_owner": "clinical-owner",
        "technical_owner": "technical-owner",
        "inclusion_exclusion_criteria": True,
        "privacy_security_review": True,
        "security_review": True,
        "clinical_governance_approval": True,
        "data_retention_decision": True,
        "consent_or_waiver": True,
        "training_complete": True,
        "stop_conditions": True,
        "incident_response": True,
        "rollback_plan": True,
        "manual_fallback": True,
        "backup_restore_verified": True,
        "device_qualification": True,
        "auth_transport_validation": True,
        "his_integration_verified": True,
        "independent_review_plan": True,
        "analysis_plan": True,
    }
    values.update(overrides)
    return ClinicalValidationPlan(**values)


def run() -> None:
    incomplete = plan(clinical_governance_approval=False, manual_fallback=False, consent_or_waiver=False)
    result = incomplete.preflight()
    assert result["status"] == "NOT_READY_FOR_CLINICAL_VALIDATION"
    assert "missing_gate_clinical_governance_approval" in result["missing_gates"]
    assert "missing_gate_manual_fallback" in result["missing_gates"]
    assert result["real_world_authorization"] is False
    print("[P1-006] Missing clinical governance, consent/waiver and fallback gates block readiness: PASSED")

    complete = plan()
    result = complete.preflight()
    assert result["status"] == "READY_FOR_EXTERNAL_GOVERNANCE_REVIEW"
    assert result["clinical_approval_required"] is True
    assert result["real_world_authorization"] is False
    assert result["evidence_class"] == "SOFTWARE_PREFLIGHT_UNVERIFIED"
    require_not_ready_for_real_world(complete)
    print("[P1-006] Complete software preflight stops at external governance review: PASSED")

    invalid_evidence = plan(evidence_class="CLINICAL_VALIDATED")
    result = invalid_evidence.preflight()
    assert result["status"] == "NOT_READY_FOR_CLINICAL_VALIDATION"
    assert "software_preflight_cannot_assert_external_evidence" in result["missing_gates"]
    print("[P1-006] Software preflight cannot self-assert clinical evidence: PASSED")

    try:
        require_not_ready_for_real_world(incomplete)
    except ClinicalValidationReadinessError as exc:
        assert str(exc) == "clinical_validation_preflight_blocked"
    else:
        raise AssertionError("incomplete plan passed real-world preflight")
    print("[P1-006] Real-world preflight remains fail-closed for incomplete plans: PASSED")
    print("CLINICAL_VALIDATION_READINESS_TESTS_PASSED")


if __name__ == "__main__":
    run()
