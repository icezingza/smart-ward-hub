from __future__ import annotations

from copy import deepcopy

from wave0_owner_appointment_intake import IntakeValidationError, REQUIRED_ROLES, template, validate_owner_appointment_intake


TIMESTAMP_START = "2026-08-21T10:00:00+00:00"
TIMESTAMP_END = "2026-08-21T11:00:00+00:00"


def expect_error(action, fragment: str) -> None:
    try:
        action()
    except IntakeValidationError as exc:
        assert fragment in str(exc), (str(exc), fragment)
    else:
        raise AssertionError(f"expected IntakeValidationError containing {fragment}")


def submitted_payload() -> dict:
    payload = template()
    payload.update({
        "package_id": "opaque:wave0-package-001",
        "source_revision": "opaque:revision-9555597",
        "freeze_manifest_sha256": "a" * 64,
        "status": "OWNER_APPOINTMENT_SUBMITTED",
    })
    payload["scope"] = {
        "scope_id": "scope:wave0-001",
        "signed_scope_ref": "approval:signed-scope-001",
        "approved_by_ref": "approval:scope-approver-001",
        "in_scope": ["non-production software evidence review", "isolated validation coordination"],
        "out_of_scope": ["production deployment", "clinical intervention"],
    }
    payload["test_window"] = {
        "start_utc": TIMESTAMP_START,
        "end_utc": TIMESTAMP_END,
        "approval_ref": "approval:test-window-001",
        "allowlist_ref": "opaque:allowlist-001",
    }
    payload["roles"] = {
        role: {
            "actor_ref": f"opaque:{role}-actor-001",
            "organization_ref": "org:external-hospital-001",
            "appointment_ref": f"approval:{role}-appointment-001",
        }
        for role in REQUIRED_ROLES
    }
    payload["stop_authority"] = {
        "stop_rule_ref": "scope:stop-rule-001",
        "notification_ref": "opaque:stop-notification-001",
    }
    payload["rollback_plan"] = {
        "target_revision": "opaque:rollback-revision-001",
        "owner_approval_ref": "approval:rollback-001",
        "restore_drill_ref": "evidence:restore-drill-001",
    }
    payload["evidence_intake"] = {
        "submission_manifest_ref": "evidence:wave0-manifest-001",
        "custody_ref": "evidence:wave0-custody-001",
        "redaction": "PASS",
    }
    return payload


def run() -> None:
    valid = submitted_payload()
    result = validate_owner_appointment_intake(valid)
    assert result["valid"] is True
    assert result["mode"] == "SUBMITTED"
    assert result["execution_ready"] is False
    assert result["owner_appointment_ready"] is True
    assert result["external_execution_authorized"] is False
    print("[WAVE0 ADV] Valid submitted owner appointment remains external-execution blocked: PASSED")

    # Blank-safe template must not become partially populated or structurally ambiguous.
    mutations = [
        ("repository", "other/repository", "repository mismatch"),
        ("roles", {**template()["roles"], "clinical_owner": "opaque:actor-001"}, "template roles must remain blank-safe"),
        ("scope", {**template()["scope"], "unexpected": "reject"}, "template.scope fields mismatch"),
        ("test_window", {**template()["test_window"], "start_utc": TIMESTAMP_START}, "template test window timestamps must remain blank"),
        ("evidence_intake", {**template()["evidence_intake"], "redaction": "PASS"}, "template evidence redaction must remain pending"),
    ]
    for field, value, fragment in mutations:
        payload = template()
        payload[field] = value
        expect_error(lambda payload=payload: validate_owner_appointment_intake(payload, template_only=True), fragment)
    print("[WAVE0 ADV] Template completeness and blank-safe mutations: PASSED")

    # Identity, secret and nested-shape boundaries.
    raw_scope = deepcopy(valid)
    raw_scope["scope"]["in_scope"][0] = "review HN-2026-1234"
    expect_error(lambda: validate_owner_appointment_intake(raw_scope), "must not contain raw identity/contact data")

    secret_scope = deepcopy(valid)
    secret_scope["scope"]["out_of_scope"][0] = "token: bearer-secret"
    expect_error(lambda: validate_owner_appointment_intake(secret_scope), "must not contain secret material")

    nested_unknown = deepcopy(valid)
    nested_unknown["roles"]["clinical_owner"]["unexpected"] = "reject"
    expect_error(lambda: validate_owner_appointment_intake(nested_unknown), "roles.clinical_owner fields mismatch")

    raw_package = deepcopy(valid)
    raw_package["package_id"] = "HN-2026-1234"
    expect_error(lambda: validate_owner_appointment_intake(raw_package), "package_id must be an opaque typed reference")
    print("[WAVE0 ADV] Raw identity, secret marker and nested schema mutations: PASSED")

    # Time/hash/role separation failures.
    naive_window = deepcopy(valid)
    naive_window["test_window"]["start_utc"] = "2026-08-21T10:00:00"
    expect_error(lambda: validate_owner_appointment_intake(naive_window), "test_window.start_utc must be timezone-aware")

    reversed_window = deepcopy(valid)
    reversed_window["test_window"]["start_utc"] = TIMESTAMP_END
    expect_error(lambda: validate_owner_appointment_intake(reversed_window), "must precede end_utc")

    bad_hash = deepcopy(valid)
    bad_hash["freeze_manifest_sha256"] = "A" * 64
    expect_error(lambda: validate_owner_appointment_intake(bad_hash), "must be lowercase SHA-256")

    role_collision = deepcopy(valid)
    role_collision["roles"]["rollback_owner"]["actor_ref"] = role_collision["roles"]["stop_authority"]["actor_ref"]
    expect_error(lambda: validate_owner_appointment_intake(role_collision), "separation of duties")

    independent_collision = deepcopy(valid)
    independent_collision["roles"]["independent_verifier"]["actor_ref"] = independent_collision["roles"]["external_coordinator"]["actor_ref"]
    expect_error(lambda: validate_owner_appointment_intake(independent_collision), "separation of duties")
    print("[WAVE0 ADV] Timestamp/hash/role-separation mutations: PASSED")

    # Authorization and status escalation attempts.
    auth_mutation = deepcopy(valid)
    auth_mutation["external_execution_authorized"] = True
    expect_error(lambda: validate_owner_appointment_intake(auth_mutation), "cannot authorize external execution")

    production_mutation = deepcopy(valid)
    production_mutation["production_authorized"] = True
    expect_error(lambda: validate_owner_appointment_intake(production_mutation), "cannot authorize production")

    boundary_mutation = deepcopy(valid)
    boundary_mutation["authorization_boundary"]["pilot_gate_status"] = "AUTHORIZED"
    expect_error(lambda: validate_owner_appointment_intake(boundary_mutation), "authorization boundary must remain locked")

    template_status = deepcopy(valid)
    template_status["status"] = "OWNER_APPOINTMENT_TEMPLATE"
    expect_error(lambda: validate_owner_appointment_intake(template_status), "submitted validation cannot use template status")

    pending_submitted = deepcopy(valid)
    pending_submitted["roles"]["clinical_owner"]["actor_ref"] = "PENDING_EXTERNAL_APPOINTMENT"
    expect_error(lambda: validate_owner_appointment_intake(pending_submitted), "opaque typed reference")
    print("[WAVE0 ADV] Authorization/status escalation and pending-submission mutations: PASSED")

    # Evidence and scope quality failures.
    duplicate_scope = deepcopy(valid)
    duplicate_scope["scope"]["in_scope"].append(duplicate_scope["scope"]["in_scope"][0])
    expect_error(lambda: validate_owner_appointment_intake(duplicate_scope), "must not contain duplicate items")

    bad_redaction = deepcopy(valid)
    bad_redaction["evidence_intake"]["redaction"] = "PENDING"
    expect_error(lambda: validate_owner_appointment_intake(bad_redaction), "redaction must be PASS")

    evidence_unknown = deepcopy(valid)
    evidence_unknown["evidence_intake"]["extra"] = "reject"
    expect_error(lambda: validate_owner_appointment_intake(evidence_unknown), "evidence_intake fields mismatch")
    print("[WAVE0 ADV] Scope duplicate/evidence redaction/schema mutations: PASSED")

    print("WAVE0_OWNER_APPOINTMENT_HARDENING_PASSED")


if __name__ == "__main__":
    run()
