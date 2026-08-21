from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone

from wave1_external_evidence_intake import (
    AUTHORIZATION_BOUNDARY,
    FREEZE_REFERENCE,
    IntakeValidationError,
    PREREQUISITES,
    canonical_sha256,
    template,
    validate,
)


def expect_error(callback, label: str) -> None:
    try:
        callback()
    except IntakeValidationError:
        print(f"[Wave 1 Intake] {label}: PASSED")
        return
    raise AssertionError(f"{label}: unsafe input was accepted")


def submitted_payload(received: int = 1) -> dict:
    payload = template()
    payload.update(
        {
            "package_id": "package:wave1-intake-20260821",
            "source_revision": "revision:aa6bb550065bd2604cc86ee1b792f1bb81b66d68",
            "submission_status": "EXTERNAL_EVIDENCE_RECEIVED",
        }
    )
    for index, item in enumerate(payload["prerequisites"][:received]):
        item.update(
            {
                "status": "RECEIVED_EXTERNAL_UNVERIFIED",
                "owner_ref": f"owner:role-{index}",
                "evidence_ref": f"evidence:external-{index}",
                "observed_at_utc": "2026-08-21T10:00:00Z",
                "artifact_sha256": f"{index + 1:064x}",
                "redaction": "PASS",
                "independent_readback_ref": f"readback:external-{index}",
            }
        )
    return payload


def run() -> None:
    blank = template()
    result = validate(blank, template_only=True)
    assert result == {
        "valid": True,
        "mode": "TEMPLATE_ONLY",
        "readiness": "READY_FOR_OWNER_APPOINTMENT",
        "execution_ready": False,
        "external_execution_authorized": False,
        "missing_count": 15,
    }
    assert len(blank["prerequisites"]) == 15
    assert tuple(item["prerequisite_id"] for item in blank["prerequisites"]) == tuple(item["id"] for item in PREREQUISITES)
    assert blank["freeze_manifest_sha256"] == FREEZE_REFERENCE
    assert blank["authorization_boundary"] == AUTHORIZATION_BOUNDARY
    print("[Wave 1 Intake] Blank-safe 15-prerequisite template: PASSED")

    partial = submitted_payload(received=2)
    partial_result = validate(partial)
    assert partial_result["received_count"] == 2
    assert partial_result["missing_count"] == 13
    assert partial_result["execution_ready"] is False
    assert partial_result["external_execution_authorized"] is False
    print("[Wave 1 Intake] Partial external intake remains owner-appointment only: PASSED")

    expect_error(lambda: validate({**blank, "production_authorized": True}, template_only=True), "production authorization mutation")
    bad_status = submitted_payload(received=1)
    bad_status["readiness"] = "READY_FOR_EXTERNAL_EXECUTION"
    expect_error(lambda: validate(bad_status), "execution readiness escalation")
    bad_status = submitted_payload(received=1)
    bad_status["submission_status"] = "PASSED"
    expect_error(lambda: validate(bad_status), "passed status escalation")

    unknown = template()
    unknown["unexpected"] = "deny"
    expect_error(lambda: validate(unknown, template_only=True), "unknown top-level field")

    duplicate = submitted_payload(received=2)
    duplicate["prerequisites"][1]["evidence_ref"] = duplicate["prerequisites"][0]["evidence_ref"]
    expect_error(lambda: validate(duplicate), "duplicate evidence reference")

    raw_identity = submitted_payload(received=1)
    raw_identity["prerequisites"][0]["evidence_ref"] = "evidence:HN-2026-8901"
    expect_error(lambda: validate(raw_identity), "raw patient reference")

    secret = submitted_payload(received=1)
    secret["prerequisites"][0]["evidence_ref"] = "evidence:Bearer-secret-token"
    expect_error(lambda: validate(secret), "bearer secret marker")

    naive = submitted_payload(received=1)
    naive["prerequisites"][0]["observed_at_utc"] = "2026-08-21T10:00:00"
    expect_error(lambda: validate(naive), "naive timestamp")

    wrong_hash = submitted_payload(received=1)
    wrong_hash["prerequisites"][0]["artifact_sha256"] = "A" * 64
    expect_error(lambda: validate(wrong_hash), "uppercase hash")

    mutation = submitted_payload(received=1)
    original = deepcopy(mutation)
    mutation["prerequisites"][0]["required_evidence"] = "mutated"
    expect_error(lambda: validate(mutation), "required-evidence definition mutation")
    assert original["prerequisites"][0]["required_evidence"] != mutation["prerequisites"][0]["required_evidence"]

    canonical = canonical_sha256(blank)
    assert len(canonical) == 64
    assert canonical == canonical_sha256(deepcopy(blank))
    print("[Wave 1 Intake] Canonical template hash is deterministic: PASSED")

    print("WAVE1_EXTERNAL_EVIDENCE_INTAKE_TESTS_PASSED")


if __name__ == "__main__":
    run()
