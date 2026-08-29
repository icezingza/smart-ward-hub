from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from wave3_governance_host_clinical_readiness import LOCKED_AUTHORIZATION, TRACKS, template, validate_wave3_manifest

ROOT = Path(__file__).resolve().parent
PYTHON = sys.executable
FOCUSED_TESTS = (
    "test_wave3_governance_host_clinical_hardening.py",
    "test_p1_002_host_hardening_readiness.py",
    "test_p1_005_clinical_shadow_hardening.py",
    "test_p1_006_clinical_validation_hardening.py",
    "test_p1_006_phase_end_hardening_gate.py",
)
PRIVATE_MARKERS = (
    "-" * 5 + "BEGIN RSA " + "PRIVATE KEY" + "-" * 5,
    "-" * 5 + "BEGIN EC " + "PRIVATE KEY" + "-" * 5,
    "-" * 5 + "BEGIN OPENSSH " + "PRIVATE KEY" + "-" * 5,
    "-" * 5 + "BEGIN " + "PRIVATE KEY" + "-" * 5,
)


def run() -> None:
    for script in FOCUSED_TESTS:
        completed = subprocess.run([PYTHON, script], cwd=ROOT, capture_output=True, text=True)
        if completed.returncode != 0:
            raise AssertionError(f"{script} failed:\n{completed.stdout}\n{completed.stderr}")
        print(f"[WAVE3 GATE] {script}: PASSED")

    template_path = ROOT / "evals/micro_rag/evidence/wave3-governance-host-clinical-readiness-template-20260821.json"
    schema_path = ROOT / "evals/micro_rag/evidence/wave3-governance-host-clinical-readiness-schema-v1.json"
    for path in (template_path, schema_path):
        if not path.is_file():
            raise AssertionError(f"missing Wave 3 artifact: {path}")
    payload = json.loads(template_path.read_text(encoding="utf-8"))
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    assert validate_wave3_manifest(payload, template_only=True)["valid"] is True
    assert schema["$id"].endswith("wave3-governance-host-clinical-readiness-v1")
    assert set(payload["tracks"]) == set(TRACKS)
    assert payload["authorization_boundary"] == LOCKED_AUTHORIZATION
    assert payload["status"] == "WAVE3_SOFTWARE_PREPARATION_READY"
    assert payload["execution_status"] == "NOT_STARTED"
    assert len(payload["required_external_prerequisites"]) == 16
    print("[WAVE3 GATE] Four-track template/schema and locked boundary: PASSED")

    scanned = [
        ROOT / "wave3_governance_host_clinical_readiness.py",
        ROOT / "export_wave3_governance_host_clinical_readiness.py",
        ROOT / "test_wave3_governance_host_clinical_hardening.py",
        ROOT / "test_wave3_governance_host_clinical_phase_end_hardening.py",
        template_path,
        schema_path,
    ]
    for path in scanned:
        text = path.read_text(encoding="utf-8")
        assert not any(marker in text for marker in PRIVATE_MARKERS), path
    print("[WAVE3 GATE] Private-key block scan: PASSED")

    diff_check = subprocess.run(["git", "diff", "--check"], cwd=ROOT, capture_output=True, text=True)
    if diff_check.returncode != 0:
        raise AssertionError(f"git diff --check failed:\n{diff_check.stdout}\n{diff_check.stderr}")
    print("[WAVE3 GATE] git diff --check: PASSED")
    print("WAVE3_GOVERNANCE_HOST_CLINICAL_PHASE_END_HARDENING_GATE_PASSED")


if __name__ == "__main__":
    run()
