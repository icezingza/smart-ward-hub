from __future__ import annotations

import json
import subprocess
from pathlib import Path

from independent_reviewer_readiness_preflight import CHECKS, EXTERNAL_INPUTS, LOCKED_AUTHORIZATION, template, validate_preflight

ROOT = Path(__file__).resolve().parent
PYTHON = "/home/ubuntu/.venvs/smart-ward-audit/bin/python"
FOCUSED_TESTS = (
    "test_independent_reviewer_readiness_preflight_hardening.py",
    "test_wave4_independent_review_package_phase_end_hardening.py",
    "test_wave_e_evidence.py",
    "test_gv10_evidence.py",
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
        print(f"[REVIEWER PREFLIGHT GATE] {script}: PASSED")

    template_path = ROOT / "evals/micro_rag/evidence/independent-reviewer-readiness-preflight-template-20260821.json"
    local_path = ROOT / "evals/micro_rag/evidence/independent-reviewer-readiness-preflight-local-20260821.json"
    schema_path = ROOT / "evals/micro_rag/evidence/independent-reviewer-readiness-preflight-schema-v1.json"
    for path in (template_path, local_path, schema_path):
        if not path.is_file():
            raise AssertionError(f"missing reviewer-preflight artifact: {path}")
    template_payload = json.loads(template_path.read_text(encoding="utf-8"))
    local_payload = json.loads(local_path.read_text(encoding="utf-8"))
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    assert validate_preflight(template_payload, template_only=True)["valid"] is True
    assert validate_preflight(local_payload)["valid"] is True
    assert schema["$id"].endswith("independent-reviewer-readiness-preflight-v1")
    assert len(local_payload["reviewer_checklist"]) == len(CHECKS)
    assert len(local_payload["external_inputs_pending"]) == len(EXTERNAL_INPUTS)
    assert local_payload["mapping_count"] == 12
    assert local_payload["artifact_count"] == 22
    assert local_payload["authorization_boundary"] == LOCKED_AUTHORIZATION
    assert local_payload["submission_status"] == "NOT_SUBMITTED"
    print("[REVIEWER PREFLIGHT GATE] Template/local/schema and locked state: PASSED")

    scanned = [
        ROOT / "independent_reviewer_readiness_preflight.py",
        ROOT / "export_independent_reviewer_readiness_preflight.py",
        ROOT / "test_independent_reviewer_readiness_preflight_hardening.py",
        ROOT / "test_independent_reviewer_readiness_preflight_phase_end_hardening.py",
        template_path,
        local_path,
        schema_path,
    ]
    for path in scanned:
        text = path.read_text(encoding="utf-8")
        assert not any(marker in text for marker in PRIVATE_MARKERS), path
    print("[REVIEWER PREFLIGHT GATE] Private-key block scan: PASSED")

    diff_check = subprocess.run(["git", "diff", "--check"], cwd=ROOT, capture_output=True, text=True)
    if diff_check.returncode != 0:
        raise AssertionError(f"git diff --check failed:\n{diff_check.stdout}\n{diff_check.stderr}")
    print("[REVIEWER PREFLIGHT GATE] git diff --check: PASSED")
    print("INDEPENDENT_REVIEWER_READINESS_PREFLIGHT_PHASE_END_HARDENING_GATE_PASSED")


if __name__ == "__main__":
    run()
