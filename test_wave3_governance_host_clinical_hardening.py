from __future__ import annotations

from wave3_governance_host_clinical_readiness import LOCKED_AUTHORIZATION, TRACKS, template, validate_wave3_manifest


def expect_error(action, fragment: str) -> None:
    try:
        action()
    except Exception as exc:
        assert fragment in str(exc), (str(exc), fragment)
    else:
        raise AssertionError(f"expected failure containing {fragment!r}")


def run() -> None:
    base = template()
    assert validate_wave3_manifest(base, template_only=True)["valid"] is True
    print("[WAVE3 ADV] Blank-safe four-track manifest: PASSED")

    mutated = template()
    mutated["unknown"] = True
    expect_error(lambda: validate_wave3_manifest(mutated, template_only=True), "unknown fields")
    mutated = template()
    mutated["tracks"]["GV-05"]["unknown"] = True
    expect_error(lambda: validate_wave3_manifest(mutated, template_only=True), "unknown GV-05 fields")
    mutated = template()
    mutated["common_controls"]["unknown"] = True
    expect_error(lambda: validate_wave3_manifest(mutated, template_only=True), "unknown common_controls fields")
    print("[WAVE3 ADV] Top-level/nested allowlists: PASSED")

    for field, value, fragment in (
        ("execution_status", "STARTED", "execution_status must remain"),
        ("clinical_governance", "APPROVED", "clinical governance must remain"),
        ("host_validation", "VERIFIED", "host validation must remain"),
        ("privacy_review", "VERIFIED", "privacy review must remain"),
        ("clinical_operations", "STARTED", "clinical operations must remain"),
        ("clinical_validation", "AUTHORIZED", "clinical validation must remain"),
    ):
        payload = template()
        payload[field] = value
        expect_error(lambda payload=payload: validate_wave3_manifest(payload, template_only=True), fragment)
    escalated = template()
    escalated["authorization_boundary"] = {**LOCKED_AUTHORIZATION, "clinical_validation_authorized": True}
    expect_error(lambda: validate_wave3_manifest(escalated, template_only=True), "authorization boundary must remain locked")
    print("[WAVE3 ADV] Status and authorization escalation refusal: PASSED")

    payload = template()
    payload["common_controls"]["scope_ref"] = "opaque:scope-HN-2026-8901"
    expect_error(lambda: validate_wave3_manifest(payload, template_only=True), "raw identity")
    payload = template()
    payload["common_controls"]["stop_rule"] = "Bearer abc123"
    expect_error(lambda: validate_wave3_manifest(payload, template_only=True), "secret material")
    payload = template()
    payload["tracks"]["GV-02"]["stop_conditions"][0] = "Review contact@example.invalid before release"
    expect_error(lambda: validate_wave3_manifest(payload, template_only=True), "raw identity/contact")
    print("[WAVE3 ADV] Raw identity/contact and secret rejection: PASSED")

    for gate in TRACKS:
        payload = template()
        first_ref = next(iter(payload["tracks"][gate]["evidence_refs"]))
        del payload["tracks"][gate]["evidence_refs"][first_ref]
        expect_error(lambda payload=payload: validate_wave3_manifest(payload, template_only=True), f"tracks.{gate}.evidence_refs mismatch")
    payload = template()
    payload["required_external_prerequisites"] = payload["required_external_prerequisites"][:-1]
    expect_error(lambda: validate_wave3_manifest(payload, template_only=True), "required_external_prerequisites mismatch")
    print("[WAVE3 ADV] Per-gate evidence binding and prerequisite completeness: PASSED")

    caller = template()
    caller["authorization_boundary"]["production_authorized"] = True
    fresh = template()
    assert fresh["authorization_boundary"] == LOCKED_AUTHORIZATION
    assert fresh["authorization_boundary"] is not caller["authorization_boundary"]
    print("[WAVE3 ADV] Caller mutation isolation and boundary re-materialization: PASSED")

    output = validate_wave3_manifest(template(), template_only=True)
    assert output["status"] == "WAVE3_SOFTWARE_PREPARATION_READY"
    assert output["execution_status"] == "NOT_STARTED"
    assert output["prerequisite_count"] == 16
    print("WAVE3_GOVERNANCE_HOST_CLINICAL_HARDENING_PASSED")


if __name__ == "__main__":
    run()
