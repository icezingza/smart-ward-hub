from __future__ import annotations

from copy import deepcopy
import json

from external_decision_record import (
    AUTHORIZATION_BOUNDARY,
    DecisionRecordValidationError,
    RECEIVED_STATUS,
    TEMPLATE_STATUS,
    canonical_sha256,
    template,
    validate,
)


def expect_error(callback, label: str) -> None:
    try:
        callback()
    except DecisionRecordValidationError:
        print(f"[Decision Record] {label}: PASSED")
        return
    raise AssertionError(f"{label}: unsafe decision record was accepted")


def received_record() -> dict:
    payload = template()
    payload.update(
        {
            "record_id": "decision:record-20260821-01",
            "decision_id": "decision:decision-20260821-01",
            "submission_id": "submission:submission-20260821-01",
            "manifest_sha256": "1" * 64,
            "scope_id": "scope:nonproduction-ward",
            "window_id": "window:20260821-01",
            "decision": "BLOCKED",
            "decision_basis": {
                "evidence_ids": ["evidence:manifest-01"],
                "finding_ids": ["finding:external-01"],
                "residual_risk_ids": ["risk:external-01"],
                "condition_ids": ["condition:owner-appointment"],
            },
            "decided_by_role": "external_authority",
            "decided_by_ref": "owner:external-authority-01",
            "decision_timestamp": "2026-08-21T10:00:00Z",
            "effective_from": "2026-08-21T10:00:00Z",
            "expires_at": "2026-08-21T11:00:00Z",
            "rollback_ref": "rollback:revision-01",
            "stop_authority_ref": "stop:authority-01",
            "signature_ref": "signature:external-01",
            "independent_verification_ref": "readback:reviewer-01",
            "revocation_ref": "revocation:decision-01",
            "response_authenticity": {
                "verification_status": "EXTERNAL_VERIFIER_PENDING",
                "key_id_ref": "key:external-signing-01",
                "certificate_ref": "certificate:external-01",
                "trust_chain_ref": "trust:external-chain-01",
                "verified_at_utc": "2026-08-21T10:01:00Z",
            },
            "status": RECEIVED_STATUS,
            "evidence_class": "EXTERNAL_UNVERIFIED",
        }
    )
    return payload


def run() -> None:
    blank = template()
    result = validate(blank, template_only=True)
    assert result == {
        "valid": True,
        "mode": "TEMPLATE_ONLY",
        "decision_record_ready": False,
        "authorization_promoted": False,
        "external_decision_verified": False,
    }
    assert blank["status"] == TEMPLATE_STATUS
    assert blank["authorization_boundary"] == AUTHORIZATION_BOUNDARY
    assert blank["authorization_promoted"] is False
    print("[Decision Record] Blank-safe decision template: PASSED")

    received = received_record()
    received_result = validate(received)
    assert received_result["decision_record_ready"] is True
    assert received_result["authorization_promoted"] is False
    assert received_result["external_decision_verified"] is False
    assert received_result["decision"] == "BLOCKED"
    print("[Decision Record] Complete external record remains unverified/non-authorizing: PASSED")

    mutation = deepcopy(received)
    mutation["production_authorized"] = True
    expect_error(lambda: validate(mutation), "production authorization mutation")

    mutation = deepcopy(received)
    mutation["authorization_promoted"] = True
    expect_error(lambda: validate(mutation), "authorization promotion mutation")

    mutation = deepcopy(received)
    mutation["status"] = "READY_FOR_EXTERNAL_EXECUTION"
    expect_error(lambda: validate(mutation), "execution readiness status escalation")

    mutation = deepcopy(received)
    mutation["decision"] = "PASSED"
    expect_error(lambda: validate(mutation), "unsupported decision status")

    mutation = deepcopy(received)
    mutation["response_authenticity"]["verification_status"] = "VERIFIED"
    expect_error(lambda: validate(mutation), "local authenticity promotion")

    mutation = deepcopy(received)
    mutation["signature_ref"] = "PENDING_EXTERNAL_APPOINTMENT"
    expect_error(lambda: validate(mutation), "missing signature reference")

    mutation = deepcopy(received)
    mutation["expires_at"] = "2026-08-21T09:00:00Z"
    expect_error(lambda: validate(mutation), "expired decision window ordering")

    mutation = deepcopy(received)
    mutation["decision_timestamp"] = "2026-08-21T10:00:00"
    expect_error(lambda: validate(mutation), "naive decision timestamp")

    mutation = deepcopy(received)
    mutation["decision_basis"]["evidence_ids"] = ["evidence:HN-2026-8901"]
    expect_error(lambda: validate(mutation), "raw patient evidence reference")

    mutation = deepcopy(received)
    mutation["decision_basis"]["condition_ids"] = ["condition:Bearer-secret-token"]
    expect_error(lambda: validate(mutation), "secret evidence reference")

    mutation = deepcopy(received)
    mutation["decision_basis"] = {"evidence_ids": [], "finding_ids": [], "residual_risk_ids": [], "condition_ids": []}
    expect_error(lambda: validate(mutation), "empty decision basis")

    mutation = deepcopy(received)
    mutation["response_authenticity"]["certificate_ref"] = "https://production.example.invalid/cert"
    expect_error(lambda: validate(mutation), "non-opaque certificate reference")

    mutation = deepcopy(received)
    mutation["stop_authority_ref"] = "stop:0812345678"
    expect_error(lambda: validate(mutation), "numeric-only contact reference")

    unknown = deepcopy(blank)
    unknown["unexpected"] = "deny"
    expect_error(lambda: validate(unknown, template_only=True), "unknown field")

    first_hash = canonical_sha256(blank)
    second_hash = canonical_sha256(json.loads(json.dumps(blank)))
    assert len(first_hash) == 64 and first_hash == second_hash
    print("[Decision Record] Canonical template hash is deterministic: PASSED")

    print("EXTERNAL_DECISION_RECORD_TESTS_PASSED")


if __name__ == "__main__":
    run()
