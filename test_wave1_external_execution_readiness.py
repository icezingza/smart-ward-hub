from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
EVIDENCE = ROOT / "evals/micro_rag/evidence/wave1-external-execution-readiness-20260820.json"


def test_wave1_readiness_is_owner_appointment_only():
    payload = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "wave1-external-execution-readiness-v1"
    assert payload["readiness"] == "READY_FOR_OWNER_APPOINTMENT"
    assert payload["execution_status"] == "NOT_STARTED"
    assert len(payload["missing_external_prerequisites"]) == 15
    assert payload["evidence_class"] == "SOFTWARE_VERIFIED/SIMULATION_ONLY"
    assert payload["authorization_boundary"] == {
        "external_authority": "NONE",
        "clinical_validation_authorized": False,
        "production_authorized": False,
        "runtime_authority": "NONE",
        "pilot_gate_status": "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION",
    }


def test_wave1_readiness_requires_external_prerequisites():
    payload = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    required = payload["missing_external_prerequisites"]
    for key in (
        "gv04_nonproduction_idp",
        "gv04_certificate_owner",
        "gv08_custody_owner",
        "gv06_acer_fixture",
        "gv06_loopback_fixture",
        "wave0_signed_scope",
    ):
        assert key in required


if __name__ == "__main__":
    test_wave1_readiness_is_owner_appointment_only()
    test_wave1_readiness_requires_external_prerequisites()
    print("WAVE1_EXTERNAL_EXECUTION_READINESS_TESTS_PASSED")
