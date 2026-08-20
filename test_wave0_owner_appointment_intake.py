from __future__ import annotations

import copy
import json
from pathlib import Path

from wave0_owner_appointment_intake import IntakeValidationError, template, validate_owner_appointment_intake

ROOT = Path(__file__).resolve().parent
TEMPLATE_PATH = ROOT / "evals/micro_rag/evidence/wave0-owner-appointment-intake-template-20260820.json"
SCHEMA_PATH = ROOT / "evals/micro_rag/evidence/wave0-owner-appointment-intake-schema-v1.json"


def test_blank_safe_template():
    result = validate_owner_appointment_intake(template(), template_only=True)
    assert result == {
        "valid": True,
        "mode": "TEMPLATE_ONLY",
        "execution_ready": False,
        "owner_appointment_ready": False,
    }


def test_template_rejects_unknown_field():
    payload = template()
    payload["unexpected"] = "deny"
    try:
        validate_owner_appointment_intake(payload, template_only=True)
    except IntakeValidationError as exc:
        assert "unknown fields" in str(exc)
    else:
        raise AssertionError("unknown field was accepted")


def test_template_locks_authorization():
    payload = template()
    payload["production_authorized"] = True
    try:
        validate_owner_appointment_intake(payload, template_only=True)
    except IntakeValidationError as exc:
        assert "cannot authorize production" in str(exc)
    else:
        raise AssertionError("authorization mutation was accepted")


def test_exported_artifacts_parse():
    assert json.loads(TEMPLATE_PATH.read_text(encoding="utf-8"))["status"] == "OWNER_APPOINTMENT_TEMPLATE"
    assert json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))["$id"].endswith("wave0-owner-appointment-intake-v1")


if __name__ == "__main__":
    test_blank_safe_template()
    test_template_rejects_unknown_field()
    test_template_locks_authorization()
    test_exported_artifacts_parse()
    print("WAVE0_OWNER_APPOINTMENT_INTAKE_TESTS_PASSED")
