"""Focused/adversarial tests for the local-only P0 HIS/FHIR readiness guard."""
from __future__ import annotations

from copy import deepcopy

from p0_his_fhir_contract_readiness_guard import (
    HISContractGuardError,
    evaluate_contract_readiness,
    validate_his_acknowledgment,
    validate_hub_handover_envelope,
)


BASE_ENVELOPE = {
    "bundle_id": "bundle:fixture-his-001",
    "idempotency_key": "idempotency:fixture-his-001",
    "patient_token": "ptok-fixture-opaque-20260823",
    "device_id": "device:fixture-01",
    "window_start": "2026-08-22T23:00:00Z",
    "window_end": "2026-08-23T00:00:00Z",
}

BASE_ACK = {
    "acknowledged": True,
    "status_code": 200,
    "acknowledged_bundle_id": BASE_ENVELOPE["bundle_id"],
    "acknowledgment_id": "ack:fixture-his-001",
    "receiving_system": "system:fixture-his",
    "server_time": "2026-08-23T00:00:00Z",
    "accepted_version": "FHIR-R4",
    "accepted_profile": "profile:fixture-observation-v1",
    "error_message": None,
}


def _expect_error(callback, label: str) -> None:
    try:
        callback()
    except HISContractGuardError:
        print(f"[P0 HIS/FHIR] {label}: PASSED")
        return
    raise AssertionError(f"{label}: unsafe input was accepted")


def test_valid_contract_readiness_is_software_only():
    report = evaluate_contract_readiness()
    assert report["all_passed"] is True
    assert report["decision"] == "P0_HIS_FHIR_CONTRACT_SOFTWARE_VERIFIED_PENDING_EXTERNAL_DECISIONS"
    assert report["mode"] == "LOCAL_DETERMINISTIC_FIXTURE_ONLY"
    assert report["external_decision_count"] == 9
    assert report["external_submission_allowed"] is False
    assert report["external_transmission_performed"] is False
    assert report["external_verification_performed"] is False
    assert report["authorization_promoted"] is False
    assert report["purge_executed"] is False
    assert report["success_ack_result"]["purge_eligible"] is True
    assert report["success_ack_result"]["purge_executed"] is False
    assert report["failure_ack_result"]["result"] == "RETAINED_FOR_RETRY"
    print("[P0 HIS/FHIR] Deterministic contract readiness remains non-authorizing: PASSED")


def test_raw_identity_and_secret_markers_are_rejected():
    raw = deepcopy(BASE_ENVELOPE)
    raw["patient_token"] = "HN-RAW-IDENTITY-0001"
    _expect_error(lambda: validate_hub_handover_envelope(raw), "Raw HN patient reference")

    secret = deepcopy(BASE_ENVELOPE)
    secret["idempotency_key"] = "Bearer-secret-fixture"
    _expect_error(lambda: validate_hub_handover_envelope(secret), "Secret marker in envelope")

    secret_ack = deepcopy(BASE_ACK)
    secret_ack["acknowledgment_id"] = "ack:private_key-leak"
    _expect_error(lambda: validate_his_acknowledgment(secret_ack, expected_bundle_id=BASE_ENVELOPE["bundle_id"]), "Secret marker in acknowledgment")


def test_generic_200_and_failed_ack_retain_without_purge():
    generic_200 = {
        "acknowledged": False,
        "status_code": 200,
        "acknowledged_bundle_id": None,
        "acknowledgment_id": None,
        "receiving_system": None,
        "server_time": None,
        "accepted_version": None,
        "accepted_profile": None,
        "error_message": "generic body unavailable",
    }
    result = validate_his_acknowledgment(generic_200, expected_bundle_id=BASE_ENVELOPE["bundle_id"])
    assert result["result"] == "RETAINED_FOR_RETRY"
    assert result["purge_eligible"] is False
    assert result["purge_executed"] is False

    failed = deepcopy(generic_200)
    failed["status_code"] = 503
    failed_result = validate_his_acknowledgment(failed, expected_bundle_id=BASE_ENVELOPE["bundle_id"])
    assert failed_result["result"] == "RETAINED_FOR_RETRY"
    assert failed_result["purge_executed"] is False
    print("[P0 HIS/FHIR] Generic 200 and transport failure retain local data: PASSED")


def test_structured_ack_requires_exact_bundle_and_fields():
    mismatch = deepcopy(BASE_ACK)
    mismatch["acknowledged_bundle_id"] = "bundle:other-fixture"
    _expect_error(lambda: validate_his_acknowledgment(mismatch, expected_bundle_id=BASE_ENVELOPE["bundle_id"]), "Mismatched bundle acknowledgment")

    missing = deepcopy(BASE_ACK)
    missing["accepted_profile"] = None
    _expect_error(lambda: validate_his_acknowledgment(missing, expected_bundle_id=BASE_ENVELOPE["bundle_id"]), "Incomplete structured acknowledgment")

    generic_ack = deepcopy(BASE_ACK)
    generic_ack["status_code"] = 202
    _expect_error(lambda: validate_his_acknowledgment(generic_ack, expected_bundle_id=BASE_ENVELOPE["bundle_id"]), "Non-200 acknowledged response")


def test_invalid_window_and_timestamp_fail_closed():
    reversed_window = deepcopy(BASE_ENVELOPE)
    reversed_window["window_start"], reversed_window["window_end"] = reversed_window["window_end"], reversed_window["window_start"]
    _expect_error(lambda: validate_hub_handover_envelope(reversed_window), "Reversed handover window")

    naive_ack = deepcopy(BASE_ACK)
    naive_ack["server_time"] = "2026-08-23T00:00:00"
    _expect_error(lambda: validate_his_acknowledgment(naive_ack, expected_bundle_id=BASE_ENVELOPE["bundle_id"]), "Naive server timestamp")


def test_boundary_return_values_are_copy_safe_and_non_authorizing():
    report = evaluate_contract_readiness()
    report["authorization_boundary"]["production_authorized"] = True
    report["success_ack_result"]["purge_executed"] = True
    fresh = evaluate_contract_readiness()
    assert fresh["authorization_boundary"]["production_authorized"] is False
    assert fresh["success_ack_result"]["purge_executed"] is False
    assert fresh["authorization_promoted"] is False
    assert fresh["clinical_validation_authorized"] is False
    print("[P0 HIS/FHIR] Returned evidence mutation cannot promote authority or purge: PASSED")


def run() -> None:
    tests = [
        test_valid_contract_readiness_is_software_only,
        test_raw_identity_and_secret_markers_are_rejected,
        test_generic_200_and_failed_ack_retain_without_purge,
        test_structured_ack_requires_exact_bundle_and_fields,
        test_invalid_window_and_timestamp_fail_closed,
        test_boundary_return_values_are_copy_safe_and_non_authorizing,
    ]
    for test in tests:
        test()
    print(f"[P0 HIS/FHIR] focused/adversarial tests: {len(tests)} PASSED")
    print("P0_HIS_FHIR_CONTRACT_READINESS_GUARD_TESTS_PASSED")


if __name__ == "__main__":
    run()
