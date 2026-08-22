"""Focused/adversarial tests for local-only OIDC/mTLS readiness."""
from __future__ import annotations

from copy import deepcopy

from p0_identity_transport_readiness_guard import (
    IdentityTransportGuardError,
    evaluate_identity_transport_readiness,
    validate_mtls_fixture,
    validate_oidc_fixture,
)


BASE_OIDC = {
    "auth_mode": "oidc",
    "issuer": "https://idp.example.test/",
    "audience": "smart-ward-hub",
    "jwks_url": "https://idp.example.test/.well-known/jwks.json",
    "algorithms": ["RS256"],
}
BASE_MTLS = {
    "certfile_present": True,
    "keyfile_present": True,
    "ca_certs_present": True,
    "key_mode": 0o600,
    "client_cert_required": True,
}


def _expect_error(callback, label: str) -> None:
    try:
        callback()
    except IdentityTransportGuardError:
        print(f"[P0 Identity/Transport] {label}: PASSED")
        return
    raise AssertionError(f"{label}: unsafe fixture was accepted")


def test_valid_readiness_is_local_only_and_unverified_live():
    report = evaluate_identity_transport_readiness()
    assert report["all_passed"] is True
    assert report["decision"] == "P0_IDENTITY_TRANSPORT_SOFTWARE_VERIFIED_PENDING_LIVE_EVIDENCE"
    assert report["mode"] == "LOCAL_DETERMINISTIC_FIXTURE_ONLY"
    assert report["oidc_result"]["live_issuer_reachable"] is False
    assert report["oidc_result"]["live_jwks_rotation_verified"] is False
    assert report["mtls_result"]["live_handshake_verified"] is False
    assert report["mtls_result"]["live_rotation_verified"] is False
    assert report["external_submission_allowed"] is False
    assert report["external_transmission_performed"] is False
    assert report["authorization_promoted"] is False
    assert report["production_authorized"] is False
    assert report["clinical_validation_authorized"] is False
    assert report["external_gate_snapshot"] == {"blocked": 7, "open": 3, "evidence_submitted": 0, "passed": 0}
    print("[P0 Identity/Transport] Local readiness does not claim live identity evidence: PASSED")


def test_oidc_missing_https_and_unsafe_algorithm_fail_closed():
    missing_mode = deepcopy(BASE_OIDC)
    missing_mode["auth_mode"] = "static"
    _expect_error(lambda: validate_oidc_fixture(missing_mode), "OIDC mode mismatch")

    http_issuer = deepcopy(BASE_OIDC)
    http_issuer["issuer"] = "http://idp.example.test/"
    _expect_error(lambda: validate_oidc_fixture(http_issuer), "Non-HTTPS issuer")

    http_jwks = deepcopy(BASE_OIDC)
    http_jwks["jwks_url"] = "http://idp.example.test/jwks"
    _expect_error(lambda: validate_oidc_fixture(http_jwks), "Non-HTTPS JWKS URL")

    none_algorithm = deepcopy(BASE_OIDC)
    none_algorithm["algorithms"] = ["none"]
    _expect_error(lambda: validate_oidc_fixture(none_algorithm), "OIDC none algorithm")

    unknown_algorithm = deepcopy(BASE_OIDC)
    unknown_algorithm["algorithms"] = ["HS256"]
    _expect_error(lambda: validate_oidc_fixture(unknown_algorithm), "Unapproved OIDC algorithm")


def test_mtls_missing_client_requirement_and_open_key_permissions_fail_closed():
    missing_client_auth = deepcopy(BASE_MTLS)
    missing_client_auth["client_cert_required"] = False
    _expect_error(lambda: validate_mtls_fixture(missing_client_auth), "mTLS client certificate requirement")

    open_key = deepcopy(BASE_MTLS)
    open_key["key_mode"] = 0o640
    _expect_error(lambda: validate_mtls_fixture(open_key), "Group-readable private key")

    missing_ca = deepcopy(BASE_MTLS)
    missing_ca["ca_certs_present"] = False
    _expect_error(lambda: validate_mtls_fixture(missing_ca), "Missing mTLS CA bundle")


def test_unknown_fields_and_secret_markers_are_rejected():
    unknown = deepcopy(BASE_OIDC)
    unknown["unexpected"] = "fixture"
    _expect_error(lambda: validate_oidc_fixture(unknown), "Unknown OIDC field")

    secret = deepcopy(BASE_OIDC)
    secret["audience"] = "Bearer-secret-fixture"
    _expect_error(lambda: validate_oidc_fixture(secret), "OIDC secret marker")

    malformed_mtls = deepcopy(BASE_MTLS)
    malformed_mtls["key_mode"] = "0600"
    _expect_error(lambda: validate_mtls_fixture(malformed_mtls), "Malformed mTLS key mode")


def test_boundary_and_returned_evidence_mutation_are_safe():
    report = evaluate_identity_transport_readiness()
    report["authorization_boundary"]["production_authorized"] = True
    report["oidc_result"]["live_issuer_reachable"] = True
    report["external_gate_snapshot"]["passed"] = 10
    fresh = evaluate_identity_transport_readiness()
    assert fresh["authorization_boundary"]["production_authorized"] is False
    assert fresh["oidc_result"]["live_issuer_reachable"] is False
    assert fresh["external_gate_snapshot"]["passed"] == 0
    assert fresh["authorization_promoted"] is False
    assert fresh["external_submission_allowed"] is False
    print("[P0 Identity/Transport] Returned evidence mutation cannot authorize or alter gate counts: PASSED")


def run() -> None:
    tests = [
        test_valid_readiness_is_local_only_and_unverified_live,
        test_oidc_missing_https_and_unsafe_algorithm_fail_closed,
        test_mtls_missing_client_requirement_and_open_key_permissions_fail_closed,
        test_unknown_fields_and_secret_markers_are_rejected,
        test_boundary_and_returned_evidence_mutation_are_safe,
    ]
    for test in tests:
        test()
    print(f"[P0 Identity/Transport] focused/adversarial tests: {len(tests)} PASSED")
    print("P0_IDENTITY_TRANSPORT_READINESS_GUARD_TESTS_PASSED")


if __name__ == "__main__":
    run()
