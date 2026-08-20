from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from wave1_software_preparation import TRACKS, template, validate_preparation_manifest


ROOT = Path(__file__).resolve().parent
FOCUSED_TESTS = (
    "test_wave1_software_preparation.py",
    "test_wave1_software_preparation_hardening.py",
    "test_wave1_external_execution_readiness.py",
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
        print(f"[WAVE1 GATE] {script}: PASSED")

    template_path = ROOT / "evals/micro_rag/evidence/wave1-software-preparation-template-20260820.json"
    schema_path = ROOT / "evals/micro_rag/evidence/wave1-software-preparation-schema-v1.json"
    external_readiness_path = ROOT / "evals/micro_rag/evidence/wave1-external-execution-readiness-20260820.json"
    for path in (template_path, schema_path, external_readiness_path):
        if not path.is_file():
            raise AssertionError(f"missing Wave 1 artifact: {path}")

    prep_payload = json.loads(template_path.read_text(encoding="utf-8"))
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    assert validate_preparation_manifest(prep_payload, template_only=True)["valid"] is True
    assert schema["$id"].endswith("wave1-software-preparation-v1")
    assert prep_payload["status"] == "SOFTWARE_PREPARATION_READY"
    assert prep_payload["environment"] == "ISOLATED_NON_PRODUCTION_ONLY"
    assert prep_payload["execution_status"] == "NOT_STARTED"
    assert prep_payload["external_execution_authorized"] is False
    assert prep_payload["authorization_boundary"]["external_authority"] == "NONE"
    assert prep_payload["authorization_boundary"]["pilot_gate_status"] == "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION"
    assert set(prep_payload["tracks"]) == set(TRACKS)
    assert template()["authorization_boundary"]["production_authorized"] is False
    print("[WAVE1 GATE] Software-preparation template/schema, GV-04/GV-08/GV-06 coverage and no-authorization boundary: PASSED")

    external_payload = json.loads(external_readiness_path.read_text(encoding="utf-8"))
    assert external_payload["readiness"] == "READY_FOR_OWNER_APPOINTMENT"
    assert external_payload["execution_status"] == "NOT_STARTED"
    assert len(external_payload["missing_external_prerequisites"]) == 15
    assert external_payload["evidence_class"] == "SOFTWARE_VERIFIED/SIMULATION_ONLY"
    assert external_payload["authorization_boundary"]["pilot_gate_status"] == "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION"
    print("[WAVE1 GATE] External-execution readiness remains owner-appointment-only with 15 prerequisites: PASSED")

    scanned = [
        ROOT / "wave1_software_preparation.py",
        ROOT / "export_wave1_software_preparation.py",
        ROOT / "wave1_external_execution_readiness.py",
        ROOT / "WAVE_1_SOFTWARE_PREPARATION_PACKAGE_20260820.md",
        ROOT / "WAVE_1_EXTERNAL_EXECUTION_READINESS_REPORT_20260820.md",
        template_path,
        external_readiness_path,
    ]
    for path in scanned:
        text = path.read_text(encoding="utf-8")
        assert not any(marker in text for marker in FORBIDDEN_PRIVATE_MARKERS), path
    print("[WAVE1 GATE] Private-key block scan on software/external-readiness artifacts: PASSED")

    diff_check = subprocess.run(["git", "diff", "--check"], cwd=ROOT, capture_output=True, text=True)
    if diff_check.returncode != 0:
        raise AssertionError(f"git diff --check failed:\n{diff_check.stdout}\n{diff_check.stderr}")
    print("[WAVE1 GATE] git diff --check: PASSED")
    print("WAVE1_SOFTWARE_PREPARATION_PHASE_END_HARDENING_GATE_PASSED")


if __name__ == "__main__":
    run()
