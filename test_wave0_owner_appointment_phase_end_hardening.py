from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from wave0_owner_appointment_intake import template, validate_owner_appointment_intake


ROOT = Path(__file__).resolve().parent
FOCUSED_TESTS = (
    "test_wave0_owner_appointment_intake.py",
    "test_wave0_owner_appointment_hardening.py",
)
FORBIDDEN_PRIVATE_MARKERS = (
    "-" * 5 + "BEGIN RSA " + "PRIVATE KEY" + "-" * 5,
    "-" * 5 + "BEGIN EC " + "PRIVATE KEY" + "-" * 5,
    "-" * 5 + "BEGIN OPENSSH " + "PRIVATE KEY" + "-" * 5,
    "-" * 5 + "BEGIN " + "PRIVATE KEY" + "-" * 5,
)


def run() -> None:
    for script in FOCUSED_TESTS:
        completed = subprocess.run([sys.executable, script], cwd=ROOT, capture_output=True, text=True)
        if completed.returncode != 0:
            raise AssertionError(f"{script} failed:\n{completed.stdout}\n{completed.stderr}")
        print(f"[WAVE0 GATE] {script}: PASSED")

    template_path = ROOT / "evals/micro_rag/evidence/wave0-owner-appointment-intake-template-20260820.json"
    schema_path = ROOT / "evals/micro_rag/evidence/wave0-owner-appointment-intake-schema-v1.json"
    if not template_path.is_file() or not schema_path.is_file():
        raise AssertionError("Wave 0 template/schema artifacts are missing")
    payload = json.loads(template_path.read_text(encoding="utf-8"))
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    assert validate_owner_appointment_intake(payload, template_only=True)["valid"] is True
    assert schema["$id"].endswith("wave0-owner-appointment-intake-v1")
    assert payload["repository"] == "icezingza/smart-ward-hub"
    assert payload["status"] == "OWNER_APPOINTMENT_TEMPLATE"
    assert payload["external_execution_authorized"] is False
    assert payload["production_authorized"] is False
    assert payload["clinical_validation_authorized"] is False
    assert payload["authorization_boundary"]["external_authority"] == "NONE"
    assert payload["authorization_boundary"]["pilot_gate_status"] == "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION"
    assert set(payload["roles"]) == {
        "external_coordinator", "clinical_owner", "security_owner", "integration_owner", "custody_owner",
        "reliability_owner", "independent_verifier", "stop_authority", "rollback_owner",
    }
    assert template()["freeze_manifest_sha256"] == "0" * 64
    print("[WAVE0 GATE] Template/schema, nine-role coverage and no-authorization boundary: PASSED")

    scanned = [
        ROOT / "wave0_owner_appointment_intake.py",
        ROOT / "export_wave0_owner_appointment_intake.py",
        ROOT / "WAVE_0_EXTERNAL_OWNER_APPOINTMENT_PACKAGE_20260820.md",
        template_path,
    ]
    for path in scanned:
        text = path.read_text(encoding="utf-8")
        assert not any(marker in text for marker in FORBIDDEN_PRIVATE_MARKERS), path
    print("[WAVE0 GATE] Private-key block scan on Wave 0 artifacts: PASSED")

    diff_check = subprocess.run(["git", "diff", "--check"], cwd=ROOT, capture_output=True, text=True)
    if diff_check.returncode != 0:
        raise AssertionError(f"git diff --check failed:\n{diff_check.stdout}\n{diff_check.stderr}")
    print("[WAVE0 GATE] git diff --check: PASSED")
    print("WAVE0_OWNER_APPOINTMENT_PHASE_END_HARDENING_GATE_PASSED")


if __name__ == "__main__":
    run()
