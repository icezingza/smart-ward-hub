from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime
from pathlib import Path

from clinical_validation_readiness import ClinicalValidationPlan, ClinicalValidationReadinessError, require_not_ready_for_real_world
from p1_006_clinical_validation_readiness import ClinicalValidationReadinessManifestError, template, validate_manifest

ROOT = Path(__file__).resolve().parent
TEMPLATE_PATH = ROOT / "evals/micro_rag/evidence/p1-006-clinical-validation-readiness-template-20260820.json"
SCHEMA_PATH = ROOT / "evals/micro_rag/evidence/p1-006-clinical-validation-readiness-schema-v1.json"


def expect_plan_issue(plan: ClinicalValidationPlan, fragment: str) -> None:
    result = plan.preflight()
    assert result["status"] == "NOT_READY_FOR_CLINICAL_VALIDATION"
    assert any(fragment in issue for issue in result["missing_gates"]), result["missing_gates"]


def expect_manifest_rejection(payload: dict, fragment: str) -> None:
    try:
        validate_manifest(payload, template_only=True)
    except ClinicalValidationReadinessManifestError as exc:
        assert fragment in str(exc), str(exc)
    else:
        raise AssertionError("manifest mutation was accepted")


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


def test_manifest_mutations() -> None:
    payload = template()
    assert validate_manifest(payload, template_only=True)["valid"] is True
    assert json.loads(TEMPLATE_PATH.read_text(encoding="utf-8"))["preflight_status"] == "READY_FOR_EXTERNAL_GOVERNANCE_REVIEW"
    assert json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))["$id"].endswith("p1-006-clinical-validation-readiness-v1")
    payload = template()
    payload["unexpected"] = True
    expect_manifest_rejection(payload, "unknown fields")
    mutations = (
        ("real_world_authorization", True, "real_world_authorization must remain false"),
        ("preflight_status", "AUTHORIZED", "preflight status must remain external-review only"),
        ("execution_status", "RUNNING", "execution status must remain NOT_STARTED"),
        ("clinical_validation", "AUTHORIZED", "clinical validation must remain PENDING"),
        ("clinical_claim_boundary", "CLINICAL_ACCURACY", "clinical claim boundary mismatch"),
        ("evidence_class", "CLINICAL_VALIDATED", "evidence class mismatch"),
    )
    for field, value, fragment in mutations:
        mutated = template()
        mutated[field] = value
        expect_manifest_rejection(mutated, fragment)
    mutated = template()
    mutated["tracks"].pop("CV-009")
    expect_manifest_rejection(mutated, "tracks must contain exactly")
    mutated = template()
    mutated["hard_stops"] = mutated["hard_stops"][:9]
    expect_manifest_rejection(mutated, "hard_stops must contain exactly 10")
    mutated = template()
    mutated["protocol_ref"] = "clinical@example.invalid"
    expect_manifest_rejection(mutated, "must be an opaque reference")
    mutated = template()
    mutated["analysis_semantics"]["accuracy_claim_forbidden"] = False
    expect_manifest_rejection(mutated, "accuracy claim must remain forbidden")
    print("[P1-006] Readiness manifest claim, execution, track, stop and reference mutations: PASSED")


def test_plan_mutations() -> None:
    expect_plan_issue(plan(protocol_version=None), "missing_protocol_version")
    expect_plan_issue(plan(clinical_owner="clinical@example.invalid"), "invalid_clinical_owner")
    expect_plan_issue(plan(technical_owner="HN-2026-1234"), "unsafe_technical_owner")
    expect_plan_issue(plan(intended_use="Use token=embedded-secret in protocol"), "unsafe_intended_use")
    expect_plan_issue(plan(excluded_uses="diagnosis"), "excluded_uses_required")
    expect_plan_issue(plan(inclusion_exclusion_criteria="yes"), "missing_gate_inclusion_exclusion_criteria")
    expect_plan_issue(plan(real_world_authorization=True), "real_world_authorization_must_remain_false")
    expect_plan_issue(plan(real_world_authorization="false"), "real_world_authorization_must_remain_false")
    expect_plan_issue(plan(evidence_class="CLINICAL_VALIDATED"), "software_preflight_cannot_assert_external_evidence")
    expect_plan_issue(plan(analysis_plan=1), "missing_gate_analysis_plan")
    print("[P1-006] Plan type/identity/secret/gate/authorization mutations: PASSED")


def test_output_and_boundary_mutations() -> None:
    complete = plan()
    result = complete.preflight()
    assert result["status"] == "READY_FOR_EXTERNAL_GOVERNANCE_REVIEW"
    assert result["real_world_authorization"] is False
    assert result["clinical_validation_authorized"] is False
    assert result["production_authorized"] is False
    assert result["software_evidence_only"] is True
    assert result["authorization_boundary"]["pilot_gate_status"] == "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION"
    assert result["evidence_class"] == "SOFTWARE_PREFLIGHT_UNVERIFIED"
    assert result["clinical_approval_required"] is True
    require_not_ready_for_real_world(complete)

    result["excluded_uses"].append("treatment")
    result["authorization_boundary"]["production_authorized"] = True
    result["missing_gates"].append("injected")
    second = complete.preflight()
    assert "treatment" not in second["excluded_uses"]
    assert second["authorization_boundary"]["production_authorized"] is False
    assert "injected" not in second["missing_gates"]

    incomplete = plan(manual_fallback=False)
    try:
        require_not_ready_for_real_world(incomplete)
    except ClinicalValidationReadinessError as exc:
        assert str(exc) == "clinical_validation_preflight_blocked"
    else:
        raise AssertionError("incomplete plan passed real-world boundary")
    print("[P1-006] Preflight output-copy, no-authorization and incomplete-plan boundaries: PASSED")


if __name__ == "__main__":
    test_manifest_mutations()
    test_plan_mutations()
    test_output_and_boundary_mutations()
    print("P1_006_CLINICAL_VALIDATION_HARDENING_TESTS_PASSED")
