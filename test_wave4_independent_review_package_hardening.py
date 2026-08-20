from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from wave4_independent_review_package import ARTIFACT_PATHS, LOCKED_AUTHORIZATION, build_local_package, template, validate_package

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
    assert validate_package(base, template_only=True)["valid"] is True
    print("[WAVE4 ADV] Blank-safe package template: PASSED")

    payload = deepcopy(base)
    payload["unknown"] = True
    expect_error(lambda: validate_package(payload, template_only=True), "unknown package fields")
    payload = deepcopy(base)
    payload["mapping"] = payload["mapping"][:-1]
    expect_error(lambda: validate_package(payload, template_only=True), "mapping must contain exactly 12")
    payload = deepcopy(base)
    payload["mapping"][1]["test_case_id"] = payload["mapping"][0]["test_case_id"]
    expect_error(lambda: validate_package(payload, template_only=True), "invalid or duplicate")
    print("[WAVE4 ADV] Package and T-01..T-12 coverage allowlists: PASSED")

    payload = deepcopy(base)
    payload["authorization_boundary"]["production_authorized"] = True
    expect_error(lambda: validate_package(payload, template_only=True), "authorization boundary must remain locked")
    payload = deepcopy(base)
    payload["package_state"] = "READY_FOR_INDEPENDENT_REVIEW"
    expect_error(lambda: validate_package(payload, template_only=True), "package_state must remain owner-appointment ready")
    payload = deepcopy(base)
    payload["wave_e_bundle_state"] = "READY_FOR_INDEPENDENT_REVIEW"
    expect_error(lambda: validate_package(payload, template_only=True), "Wave E bundle state must remain not executed")
    print("[WAVE4 ADV] Dossier/execution/authorization escalation refusal: PASSED")

    payload = deepcopy(base)
    payload["mapping"][0]["reviewer_action"] = "Verify HN-2026-8901 before review"
    expect_error(lambda: validate_package(payload, template_only=True), "raw identity")
    payload = deepcopy(base)
    payload["mapping"][0]["reviewer_action"] = "Use Bearer secret-value"
    expect_error(lambda: validate_package(payload, template_only=True), "secret material")
    payload = deepcopy(base)
    payload["artifacts"][0]["repo_path"] = "../outside.txt"
    expect_error(lambda: validate_package(payload, template_only=True), "repo_path unsafe")
    payload = deepcopy(base)
    payload["artifacts"][0]["repo_path"] = "/tmp/secret.txt"
    expect_error(lambda: validate_package(payload, template_only=True), "repo_path unsafe")
    print("[WAVE4 ADV] Raw identity/secret/path traversal rejection: PASSED")

    payload = deepcopy(base)
    payload["artifacts"][0]["artifact_sha256"] = "a" * 63
    expect_error(lambda: validate_package(payload, template_only=True), "template artifact hash must be blank")
    payload = deepcopy(base)
    payload["artifacts"][0]["source_revision"] = "a" * 40
    expect_error(lambda: validate_package(payload, template_only=True), "template artifact revision must be pending")
    payload = deepcopy(base)
    payload["artifacts"][0]["evidence_class"] = "EXTERNAL_VERIFIED"
    expect_error(lambda: validate_package(payload, template_only=True), "artifact evidence class mismatch")
    print("[WAVE4 ADV] Artifact hash/revision/evidence-class mutation rejection: PASSED")

    local = build_local_package(ROOT)
    assert validate_package(local)["valid"] is True
    assert local["authorization_boundary"] == LOCKED_AUTHORIZATION
    assert local["package_state"] == "READY_FOR_EXTERNAL_OWNER_APPOINTMENT"
    assert len(local["mapping"]) == 12
    assert len(local["artifacts"]) == len(ARTIFACT_PATHS)
    print("[WAVE4 ADV] Local artifact hash/index build and locked state: PASSED")

    fresh = template()
    fresh["authorization_boundary"]["clinical_validation_authorized"] = True
    assert template()["authorization_boundary"] == LOCKED_AUTHORIZATION
    print("[WAVE4 ADV] Template caller-mutation isolation: PASSED")
    print("WAVE4_INDEPENDENT_REVIEW_PACKAGE_HARDENING_PASSED")


if __name__ == "__main__":
    run()
