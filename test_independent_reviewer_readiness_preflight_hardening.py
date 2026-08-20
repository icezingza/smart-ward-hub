from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from independent_reviewer_readiness_preflight import CHECKS, EXTERNAL_INPUTS, LOCKED_AUTHORIZATION, build_preflight, template, validate_preflight

ROOT = Path(__file__).resolve().parent


def expect_error(action, fragment: str) -> None:
    try:
        action()
    except Exception as exc:
        assert fragment in str(exc), (str(exc), fragment)
    else:
        raise AssertionError(f"expected failure containing {fragment!r}")


def run() -> None:
    base = template()
    assert validate_preflight(base, template_only=True)["valid"] is True
    print("[REVIEWER PREFLIGHT ADV] Blank-safe preflight template: PASSED")

    payload = deepcopy(base)
    payload["unknown"] = True
    expect_error(lambda: validate_preflight(payload, template_only=True), "unknown preflight fields")
    payload = deepcopy(base)
    payload["reviewer_checklist"] = payload["reviewer_checklist"][:-1]
    expect_error(lambda: validate_preflight(payload, template_only=True), "exactly 12 checks")
    payload = deepcopy(base)
    payload["reviewer_checklist"][1]["check_id"] = payload["reviewer_checklist"][0]["check_id"]
    expect_error(lambda: validate_preflight(payload, template_only=True), "invalid or duplicate")
    print("[REVIEWER PREFLIGHT ADV] Strict checklist coverage: PASSED")

    for field, value, fragment in (
        ("submission_status", "SUBMITTED", "submission_status must remain"),
        ("reviewer_appointment", "APPOINTED", "reviewer appointment must remain"),
        ("external_decision", "AUTHORIZED_BY_EXTERNAL_OWNER", "external decision must remain"),
        ("package_state", "READY_FOR_INDEPENDENT_REVIEW", "package state mismatch"),
        ("wave_e_bundle_state", "READY_FOR_INDEPENDENT_REVIEW", "Wave E bundle must remain"),
    ):
        payload = deepcopy(base)
        payload[field] = value
        expect_error(lambda payload=payload: validate_preflight(payload, template_only=True), fragment)
    payload = deepcopy(base)
    payload["authorization_boundary"]["production_authorized"] = True
    expect_error(lambda: validate_preflight(payload, template_only=True), "authorization boundary must remain locked")
    print("[REVIEWER PREFLIGHT ADV] Submission/decision/authorization escalation refusal: PASSED")

    payload = deepcopy(base)
    payload["reviewer_checklist"][0]["external_action"] = "Verify HN-2026-8901 before review"
    expect_error(lambda: validate_preflight(payload, template_only=True), "raw identity")
    payload = deepcopy(base)
    payload["reviewer_checklist"][0]["external_action"] = "Use Bearer secret-value"
    expect_error(lambda: validate_preflight(payload, template_only=True), "secret material")
    payload = deepcopy(base)
    payload["external_inputs_pending"] = list(EXTERNAL_INPUTS[:-1])
    expect_error(lambda: validate_preflight(payload, template_only=True), "authoritative external-input list")
    print("[REVIEWER PREFLIGHT ADV] Unsafe-content and pending-input mutation refusal: PASSED")

    local = build_preflight(ROOT)
    assert validate_preflight(local)["valid"] is True
    assert local["mapping_count"] == 12
    assert local["artifact_count"] == 22
    assert local["authorization_boundary"] == LOCKED_AUTHORIZATION
    assert local["submission_status"] == "NOT_SUBMITTED"
    assert len(local["external_inputs_pending"]) == len(EXTERNAL_INPUTS)
    print("[REVIEWER PREFLIGHT ADV] Local preflight/index binding: PASSED")

    fresh = template()
    fresh["authorization_boundary"]["clinical_validation_authorized"] = True
    assert template()["authorization_boundary"] == LOCKED_AUTHORIZATION
    print("[REVIEWER PREFLIGHT ADV] Caller mutation isolation: PASSED")
    print("INDEPENDENT_REVIEWER_READINESS_PREFLIGHT_HARDENING_PASSED")


if __name__ == "__main__":
    run()
