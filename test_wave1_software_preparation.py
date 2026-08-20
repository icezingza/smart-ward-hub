from __future__ import annotations

import copy
import json
from pathlib import Path

from wave1_software_preparation import PreparationValidationError, template, validate_preparation_manifest

ROOT = Path(__file__).resolve().parent
TEMPLATE_PATH = ROOT / "evals/micro_rag/evidence/wave1-software-preparation-template-20260820.json"
SCHEMA_PATH = ROOT / "evals/micro_rag/evidence/wave1-software-preparation-schema-v1.json"


def expect_rejection(payload: dict, fragment: str) -> None:
    try:
        validate_preparation_manifest(payload, template_only=True)
    except PreparationValidationError as exc:
        assert fragment in str(exc), str(exc)
    else:
        raise AssertionError("mutation was accepted")


def test_blank_safe_template():
    result = validate_preparation_manifest(template(), template_only=True)
    assert result["valid"] is True
    assert result["execution_status"] == "NOT_STARTED"
    assert result["external_execution_authorized"] is False
    assert result["tracks"] == ["acer_bench", "key_custody", "oidc_mtls"]


def test_unknown_field_rejected():
    payload = template()
    payload["unexpected"] = "deny"
    expect_rejection(payload, "unknown fields")


def test_authorization_mutation_rejected():
    payload = template()
    payload["external_execution_authorized"] = True
    expect_rejection(payload, "cannot authorize external execution")


def test_track_status_mutation_rejected():
    payload = template()
    payload["tracks"]["oidc_mtls"]["execution_status"] = "STARTED"
    expect_rejection(payload, "execution_status mismatch")


def test_raw_identity_and_secret_rejected():
    payload = template()
    payload["common_controls"]["stop_rule"] = "Contact owner@example.invalid with Bearer abc123"
    expect_rejection(payload, "must not contain raw identity/contact data")


def test_exported_artifacts_parse():
    assert json.loads(TEMPLATE_PATH.read_text(encoding="utf-8"))["status"] == "SOFTWARE_PREPARATION_READY"
    assert json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))["$id"].endswith("wave1-software-preparation-v1")


if __name__ == "__main__":
    test_blank_safe_template()
    test_unknown_field_rejected()
    test_authorization_mutation_rejected()
    test_track_status_mutation_rejected()
    test_raw_identity_and_secret_rejected()
    test_exported_artifacts_parse()
    print("WAVE1_SOFTWARE_PREPARATION_TESTS_PASSED")
