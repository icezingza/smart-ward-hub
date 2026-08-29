from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from wave2_integration_forensic_readiness import LOCKED_AUTHORIZATION, TRACKS, template, validate_wave2_manifest

ROOT = Path(__file__).resolve().parent
FOCUSED_TESTS = (
    "test_p0_his_admission_contract.py",
    "test_fhir.py",
    "test_forensics.py",
    "test_external_anchor_contract.py",
    "test_external_anchor_fault_injection.py",
    "test_file_anchor_store.py",
    "test_wave2_integration_forensic_hardening.py",
)
FORBIDDEN_PRIVATE_MARKERS = (
    "-" * 5 + "BEGIN RSA " + "PRIVATE KEY" + "-" * 5,
    "-" * 5 + "BEGIN EC " + "PRIVATE KEY" + "-" * 5,
    "-" * 5 + "BEGIN OPENSSH " + "PRIVATE KEY" + "-" * 5,
    "-" * 5 + "BEGIN " + "PRIVATE KEY" + "-" * 5,
)
PYTHON = sys.executable


def run() -> None:
    for script in FOCUSED_TESTS:
        completed = subprocess.run([PYTHON, script], cwd=ROOT, capture_output=True, text=True)
        if completed.returncode != 0:
            raise AssertionError(f"{script} failed:\n{completed.stdout}\n{completed.stderr}")
        print(f"[WAVE2 GATE] {script}: PASSED")

    template_path = ROOT / "evals/micro_rag/evidence/wave2-integration-forensic-readiness-template-20260821.json"
    schema_path = ROOT / "evals/micro_rag/evidence/wave2-integration-forensic-readiness-schema-v1.json"
    for path in (template_path, schema_path):
        if not path.is_file():
            raise AssertionError(f"missing Wave 2 artifact: {path}")

    payload = json.loads(template_path.read_text(encoding="utf-8"))
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    result = validate_wave2_manifest(payload, template_only=True)
    assert result["valid"] is True
    assert schema["$id"].endswith("wave2-integration-forensic-readiness-v1")
    assert payload["status"] == "WAVE2_SOFTWARE_PREPARATION_READY"
    assert payload["execution_status"] == "NOT_STARTED"
    assert payload["external_integration"] == "UNVERIFIED"
    assert payload["software_evidence_only"] is True
    assert payload["authorization_boundary"] == LOCKED_AUTHORIZATION
    assert set(payload["tracks"]) == set(TRACKS)
    assert len(payload["required_external_prerequisites"]) == 8
    print("[WAVE2 GATE] Readiness template/schema, GV-03/GV-07 coverage and locked boundary: PASSED")

    scanned = [
        ROOT / "main.py",
        ROOT / "his_admission_gateway_contract.py",
        ROOT / "external_anchor.py",
        ROOT / "edge_controls.py",
        ROOT / "wave2_integration_forensic_readiness.py",
        ROOT / "export_wave2_integration_forensic_readiness.py",
        ROOT / "test_wave2_integration_forensic_hardening.py",
        template_path,
        schema_path,
    ]
    for path in scanned:
        text = path.read_text(encoding="utf-8")
        assert not any(marker in text for marker in FORBIDDEN_PRIVATE_MARKERS), path
    print("[WAVE2 GATE] Private-key block scan: PASSED")

    diff_check = subprocess.run(["git", "diff", "--check"], cwd=ROOT, capture_output=True, text=True)
    if diff_check.returncode != 0:
        raise AssertionError(f"git diff --check failed:\n{diff_check.stdout}\n{diff_check.stderr}")
    print("[WAVE2 GATE] git diff --check: PASSED")
    print("WAVE2_INTEGRATION_FORENSIC_PHASE_END_HARDENING_GATE_PASSED")


if __name__ == "__main__":
    run()
