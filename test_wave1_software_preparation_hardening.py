from __future__ import annotations

from copy import deepcopy

from wave1_software_preparation import PreparationValidationError, TRACKS, template, validate_preparation_manifest



def expect_error(action, fragment: str) -> None:
    try:
        action()
    except PreparationValidationError as exc:
        assert fragment in str(exc), (str(exc), fragment)
    else:
        raise AssertionError(f"expected PreparationValidationError containing {fragment}")


def populated_manifest() -> dict:
    payload = deepcopy(template())
    payload.update({
        "package_id": "opaque:wave1-package-001",
        "source_revision": "opaque:revision-b5dff8c",
        "freeze_manifest_sha256": "b" * 64,
    })
    payload["common_controls"]["scope_ref"] = "scope:wave1-scope-001"
    payload["common_controls"]["window_ref"] = "window:wave1-window-001"
    payload["common_controls"]["rollback_ref"] = "rollback:wave1-rollback-001"
    for name in TRACKS:
        payload["tracks"][name]["owner_appointment_ref"] = f"approval:{name}-owner-001"
        payload["tracks"][name]["test_matrix_ref"] = f"artifact:{name}-matrix-001"
    return payload


def run() -> None:
    assert validate_preparation_manifest(template(), template_only=True)["valid"] is True
    populated = populated_manifest()
    assert validate_preparation_manifest(populated, template_only=False)["valid"] is True
    print("[WAVE1 ADV] Blank-safe and populated non-production manifest shapes: PASSED")

    # Template objects must not share mutable references with global contracts.
    mutated = template()
    mutated["authorization_boundary"]["pilot_gate_status"] = "AUTHORIZED"
    mutated["tracks"]["oidc_mtls"]["planned_test_ids"].append("ID-999")
    mutated["tracks"]["acer_bench"]["stop_conditions"].clear()
    fresh = template()
    assert fresh["authorization_boundary"]["pilot_gate_status"] == "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION"
    assert "ID-999" not in fresh["tracks"]["oidc_mtls"]["planned_test_ids"]
    assert fresh["tracks"]["acer_bench"]["stop_conditions"]
    print("[WAVE1 ADV] Template caller-mutation isolation: PASSED")

    # Top-level and nested schema confusion.
    unknown = template()
    unknown["unexpected"] = "reject"
    expect_error(lambda: validate_preparation_manifest(unknown, template_only=True), "unknown fields")

    common_unknown = template()
    common_unknown["common_controls"]["unexpected"] = "reject"
    expect_error(lambda: validate_preparation_manifest(common_unknown, template_only=True), "common_controls fields mismatch")

    track_unknown = template()
    track_unknown["tracks"]["oidc_mtls"]["unexpected"] = "reject"
    expect_error(lambda: validate_preparation_manifest(track_unknown, template_only=True), "tracks.oidc_mtls fields mismatch")

    stop_as_string = template()
    stop_as_string["tracks"]["key_custody"]["stop_conditions"] = "not-a-list"
    expect_error(lambda: validate_preparation_manifest(stop_as_string, template_only=True), "stop_conditions must be non-empty")
    print("[WAVE1 ADV] Top-level/nested schema and type confusion: PASSED")

    # Track-specific status and external validation claims.
    for track_name in TRACKS:
        status_mutation = template()
        status_mutation["tracks"][track_name]["status"] = "EXTERNAL_VERIFIED"
        expect_error(lambda status_mutation=status_mutation: validate_preparation_manifest(status_mutation, template_only=True), "status mismatch")

        validation_mutation = template()
        validation_mutation["tracks"][track_name]["hardware_or_external_validation"] = "PASSED"
        expect_error(lambda validation_mutation=validation_mutation: validate_preparation_manifest(validation_mutation, template_only=True), "external validation must remain unverified")
    print("[WAVE1 ADV] GV-04/GV-08/GV-06 status and external-claim mutations: PASSED")

    # Unsafe content and production-target claims.
    unsafe_fields = [
        ("common_controls", "stop_rule", "HN-2026-1234 observed", "raw identity/contact data"),
        ("common_controls", "stop_rule", "Contact owner@example.invalid", "raw identity/contact data"),
        ("common_controls", "stop_rule", "Bearer abc123", "secret material"),
        ("common_controls", "stop_rule", "production deployment is allowed", "must not describe a production target"),
    ]
    for section, field, value, fragment in unsafe_fields:
        payload = template()
        payload[section][field] = value
        expect_error(lambda payload=payload: validate_preparation_manifest(payload, template_only=True), fragment)

    for track_name in TRACKS:
        unsafe_track = template()
        unsafe_track["tracks"][track_name]["stop_conditions"][0] = "HN-2026-1234 must stop"
        expect_error(lambda unsafe_track=unsafe_track: validate_preparation_manifest(unsafe_track, template_only=True), "raw identity/contact data")
    print("[WAVE1 ADV] PII, secret marker and production-claim rejection: PASSED")

    # Authorization, execution and pending reference mutation.
    auth = template()
    auth["external_execution_authorized"] = True
    expect_error(lambda: validate_preparation_manifest(auth, template_only=True), "cannot authorize external execution")

    boundary = template()
    boundary["authorization_boundary"]["clinical_validation_authorized"] = True
    expect_error(lambda: validate_preparation_manifest(boundary, template_only=True), "authorization boundary must remain locked")

    started = template()
    started["execution_status"] = "STARTED"
    expect_error(lambda: validate_preparation_manifest(started, template_only=True), "execution_status must remain NOT_STARTED")

    populated_pending = populated_manifest()
    populated_pending["tracks"]["oidc_mtls"]["owner_appointment_ref"] = "PENDING_EXTERNAL_APPOINTMENT"
    expect_error(lambda: validate_preparation_manifest(populated_pending, template_only=False), "must be an opaque reference")
    print("[WAVE1 ADV] Authorization, execution and pending-reference escalation: PASSED")

    # Populated manifests require exact opaque external references and lowercase hashes.
    bad_hash = populated_manifest()
    bad_hash["freeze_manifest_sha256"] = "C" * 64
    expect_error(lambda: validate_preparation_manifest(bad_hash, template_only=False), "lowercase SHA-256")

    bad_scope = populated_manifest()
    bad_scope["common_controls"]["scope_ref"] = "HN-2026-1234"
    expect_error(lambda: validate_preparation_manifest(bad_scope, template_only=False), "must be an opaque reference")

    print("WAVE1_SOFTWARE_PREPARATION_HARDENING_PASSED")


if __name__ == "__main__":
    run()
