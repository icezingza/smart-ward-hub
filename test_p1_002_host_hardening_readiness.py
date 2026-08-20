from __future__ import annotations

import json
from pathlib import Path

from p1_002_host_hardening_readiness import HostHardeningValidationError, template, validate_host_hardening_manifest

ROOT = Path(__file__).resolve().parent
TEMPLATE_PATH = ROOT / "evals/micro_rag/evidence/p1-002-host-hardening-readiness-template-20260820.json"
SCHEMA_PATH = ROOT / "evals/micro_rag/evidence/p1-002-host-hardening-readiness-schema-v1.json"


def expect_rejection(payload: dict, fragment: str) -> None:
    try:
        validate_host_hardening_manifest(payload, template_only=True)
    except HostHardeningValidationError as exc:
        assert fragment in str(exc), str(exc)
    else:
        raise AssertionError("mutation was accepted")


def test_blank_safe_template():
    result = validate_host_hardening_manifest(template(), template_only=True)
    assert result["valid"] is True
    assert result["host_execution_status"] == "NOT_STARTED"
    assert result["physical_validation"] == "UNVERIFIED"
    assert result["software_evidence_only"] is True


def test_unknown_field_rejected():
    payload = template()
    payload["unexpected"] = "deny"
    expect_rejection(payload, "unknown fields")


def test_authorization_mutation_rejected():
    payload = template()
    payload["authorization_boundary"]["production_authorized"] = True
    expect_rejection(payload, "authorization boundary must remain locked")


def test_host_execution_mutation_rejected():
    payload = template()
    payload["host_execution_status"] = "STARTED"
    expect_rejection(payload, "host execution must remain NOT_STARTED")


def test_control_set_mutation_rejected():
    payload = template()
    payload["controls"].pop("firewall_and_network")
    expect_rejection(payload, "controls must contain exactly")


def test_raw_identity_and_secret_rejected():
    payload = template()
    payload["common_controls"]["stop_rule"] = "Contact owner@example.invalid with Bearer abc123"
    expect_rejection(payload, "must not contain raw identity/contact data")


def test_external_evidence_ref_requires_opaque_ref():
    payload = template()
    payload["source_revision"] = "commit:abc123"
    payload["package_id"] = "opaque:p1-002"
    payload["freeze_manifest_sha256"] = "a" * 64
    payload["external_owner_appointment"] = "PENDING_EXTERNAL_APPOINTMENT"
    payload["common_controls"]["scope_ref"] = "scope:p1-002"
    payload["common_controls"]["window_ref"] = "window:p1-002"
    payload["common_controls"]["rollback_ref"] = "rollback:p1-002"
    for control in payload["controls"].values():
        control["evidence_ref"] = "evidence:p1-002"
    payload["controls"]["disk_encryption"]["evidence_ref"] = "operator@example.invalid"
    try:
        validate_host_hardening_manifest(payload, template_only=False)
    except HostHardeningValidationError as exc:
        assert "evidence_ref must be an opaque reference" in str(exc)
    else:
        raise AssertionError("raw evidence identity was accepted")


def test_exported_artifacts_parse():
    assert json.loads(TEMPLATE_PATH.read_text(encoding="utf-8"))["status"] == "HOST_HARDENING_SOFTWARE_PREPARATION_READY"
    assert json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))["$id"].endswith("p1-002-host-hardening-readiness-v1")


if __name__ == "__main__":
    test_blank_safe_template()
    test_unknown_field_rejected()
    test_authorization_mutation_rejected()
    test_host_execution_mutation_rejected()
    test_control_set_mutation_rejected()
    test_raw_identity_and_secret_rejected()
    test_external_evidence_ref_requires_opaque_ref()
    test_exported_artifacts_parse()
    print("P1_002_HOST_HARDENING_READINESS_TESTS_PASSED")
