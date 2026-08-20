from __future__ import annotations

import json
import subprocess
from pathlib import Path

from wave4_independent_review_package import ARTIFACT_PATHS, LOCKED_AUTHORIZATION, TEST_SPECS, template, validate_package

ROOT = Path(__file__).resolve().parent
PYTHON = "/home/ubuntu/.venvs/smart-ward-audit/bin/python"
FOCUSED_TESTS = (
    "test_wave4_independent_review_package_hardening.py",
    "test_wave_e_evidence.py",
    "test_gv10_evidence.py",
    "test_independent_review_operations.py",
    "test_p1_008_phase_end_hardening_gate.py",
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
        print(f"[WAVE4 GATE] {script}: PASSED")

    template_path = ROOT / "evals/micro_rag/evidence/wave4-independent-review-package-template-20260821.json"
    local_path = ROOT / "evals/micro_rag/evidence/wave4-independent-review-package-local-index-20260821.json"
    schema_path = ROOT / "evals/micro_rag/evidence/wave4-independent-review-package-schema-v1.json"
    for path in (template_path, local_path, schema_path):
        if not path.is_file():
            raise AssertionError(f"missing Wave 4 artifact: {path}")
    template_payload = json.loads(template_path.read_text(encoding="utf-8"))
    local_payload = json.loads(local_path.read_text(encoding="utf-8"))
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    assert validate_package(template_payload, template_only=True)["valid"] is True
    assert validate_package(local_payload)["valid"] is True
    assert schema["$id"].endswith("wave4-independent-review-package-v1")
    assert {entry["test_case_id"] for entry in local_payload["mapping"]} == set(TEST_SPECS)
    assert len(local_payload["artifacts"]) == len(ARTIFACT_PATHS)
    assert local_payload["authorization_boundary"] == LOCKED_AUTHORIZATION
    assert local_payload["package_state"] == "READY_FOR_EXTERNAL_OWNER_APPOINTMENT"
    assert local_payload["wave_e_bundle_state"] == "NOT_EXECUTED"
    print("[WAVE4 GATE] Template/local index/schema and locked boundary: PASSED")

    scanned = [
        ROOT / "wave4_independent_review_package.py",
        ROOT / "export_wave4_independent_review_package.py",
        ROOT / "test_wave4_independent_review_package_hardening.py",
        ROOT / "test_wave4_independent_review_package_phase_end_hardening.py",
        template_path,
        local_path,
        schema_path,
    ]
    for path in scanned:
        text = path.read_text(encoding="utf-8")
        assert not any(marker in text for marker in PRIVATE_MARKERS), path
    print("[WAVE4 GATE] Private-key block scan: PASSED")

    diff_check = subprocess.run(["git", "diff", "--check"], cwd=ROOT, capture_output=True, text=True)
    if diff_check.returncode != 0:
        raise AssertionError(f"git diff --check failed:\n{diff_check.stdout}\n{diff_check.stderr}")
    print("[WAVE4 GATE] git diff --check: PASSED")
    print("WAVE4_INDEPENDENT_REVIEW_PACKAGE_PHASE_END_HARDENING_GATE_PASSED")


if __name__ == "__main__":
    run()
