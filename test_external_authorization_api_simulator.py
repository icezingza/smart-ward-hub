from __future__ import annotations

from pathlib import Path

from external_authorization_api_simulator import (
    SimulatedExternalAuthorizationApi,
    SimulationApiError,
    load_wave0_package,
)


ROOT = Path(__file__).resolve().parent
PACKAGE = load_wave0_package(ROOT / "evals/micro_rag/evidence/wave0-governance-handoff-20260820.json")
PACKAGE_ID = PACKAGE.get("package_id") or PACKAGE["validation"]["package_id"]
BASE_REQUEST = {
    "submission_idempotency_key": "test-submit-001",
    "package_id": PACKAGE_ID,
    "manifest_version": PACKAGE["freeze"]["manifest_version"],
    "manifest_sha256": PACKAGE["freeze"]["manifest_sha256"],
    "scope_id": PACKAGE["freeze"]["scope_id"],
    "window_id": PACKAGE["freeze"]["window_id"],
    "artifact_refs": ["repo://WAVE_0_GOVERNANCE_HANDOFF_REPORT.md"],
    "submitted_by_role": "evidence_custodian",
    "claim_boundary": "SIMULATION_ONLY; external authorization remains pending",
    "external_verification_required": True,
    "submitted_at": "2026-08-20T08:05:00+00:00",
}


def expect_code(api: SimulatedExternalAuthorizationApi, request: dict, code: str) -> None:
    try:
        api.submit(request)
    except SimulationApiError as exc:
        assert exc.code == code, (exc.code, code)
    else:
        raise AssertionError(f"expected {code}")


def main() -> int:
    api = SimulatedExternalAuthorizationApi(PACKAGE)
    received = api.submit(BASE_REQUEST)
    assert received["status"] == "RECEIVED_FOR_SIMULATION"
    assert received["simulation"] is True
    assert received["external_authority"] == "NONE"
    assert received["clinical_validation_authorized"] is False
    assert received["production_authorized"] is False

    repeated = api.submit(dict(BASE_REQUEST))
    assert repeated["submission_id"] == received["submission_id"]
    assert repeated["audit_event_id"] is None

    conflict = dict(BASE_REQUEST)
    conflict["manifest_sha256"] = "f" * 64
    expect_code(api, conflict, "REJECTED_IDEMPOTENCY_CONFLICT")

    review = api.start_review(received["submission_id"], "2026-08-20T08:06:00+00:00")
    assert review["status"] == "IN_SIMULATED_REVIEW"
    finding = api.issue_finding(
        received["submission_id"],
        {
            "finding_id": "test-finding-001",
            "severity": "HIGH",
            "category": "MISSING_EXTERNAL_GOVERNANCE",
            "summary": "External appointment remains pending verification.",
            "evidence_refs": ["repo://WAVE_0_GOVERNANCE_HANDOFF_REPORT.md"],
            "required_action": "Provide external appointment and signed scope.",
            "reviewer_role": "independent_reviewer",
            "reviewer_identity_ref": "external-reviewer-ref-test",
            "external_verification_status": "PENDING_EXTERNAL_VERIFICATION",
        },
        "2026-08-20T08:07:00+00:00",
    )
    assert finding["status"] == "REQUIRES_CLARIFICATION"

    expect_code(api, {**BASE_REQUEST, "submission_idempotency_key": "raw-identity", "artifact_refs": ["repo://HN-1234.txt"]}, "REJECTED_RAW_IDENTITY")
    expect_code(api, {**BASE_REQUEST, "submission_idempotency_key": "bad-hash", "manifest_sha256": "0" * 64}, "REJECTED_MANIFEST_MISMATCH")
    expect_code(api, {**BASE_REQUEST, "submission_idempotency_key": "bad-auth", "clinical_validation_authorized": True}, "REJECTED_AUTHORIZATION_ESCALATION")
    expect_code(api, {**BASE_REQUEST, "submission_idempotency_key": "bad-time", "submitted_at": "2026-08-20T08:05:00"}, "REJECTED_TIMEZONE_REQUIRED")
    expect_code(api, {**BASE_REQUEST, "submission_idempotency_key": "bad-verification", "external_verification_required": False}, "REJECTED_VERIFICATION_BYPASS")

    audit = api.audit()
    assert audit["chain_valid"] is True
    assert audit["event_count"] == 3
    assert all(event["simulation"] is True for event in audit["events"])
    assert all(event["external_authority"] == "NONE" for event in audit["events"])
    print("EXTERNAL_AUTHORIZATION_API_SIMULATOR_TESTS_PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
