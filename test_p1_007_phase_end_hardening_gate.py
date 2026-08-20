from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from p1_007_external_validation_readiness import template, validate_manifest

ROOT = Path(__file__).resolve().parent
FOCUSED_TESTS = (
    "test_external_validation_package.py",
    "test_external_validation_gate_matrix.py",
    "test_p1_007_external_validation_hardening.py",
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
        print(f"[P1-007 GATE] {script}: PASSED")

    template_path = ROOT / "evals/micro_rag/evidence/p1-007-external-validation-readiness-template-20260820.json"
    schema_path = ROOT / "evals/micro_rag/evidence/p1-007-external-validation-readiness-schema-v1.json"
    payload = json.loads(template_path.read_text(encoding="utf-8"))
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    assert validate_manifest(payload, template_only=True)["valid"] is True
    assert schema["$id"].endswith("p1-007-external-validation-readiness-v1")
    assert payload["gate_count"] == 10
    assert payload["gate_status_counts"] == {"OPEN": 10, "EVIDENCE_SUBMITTED": 0, "BLOCKED": 0}
    assert payload["external_execution_status"] == "NOT_STARTED"
    assert payload["external_owner_appointment"] == "PENDING_EXTERNAL_APPOINTMENT"
    assert payload["real_world_authorization"] is False
    assert payload["clinical_validation_authorized"] is False
    assert payload["production_authorized"] is False
    assert payload["coordination_evidence_only"] is True
    assert payload["evidence_class"] == "COORDINATION_ARTIFACT_UNVERIFIED"
    assert payload["authorization_boundary"]["pilot_gate_status"] == "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION"
    assert payload["reopen_policy"]["blocked_gate_submission"] == "REJECT_UNTIL_REOPEN"
    assert len(payload["gates"]) == 10
    print("[P1-007 GATE] Readiness template/schema, 10-gate coverage, blocker/reopen and no-authorization boundary: PASSED")

    scanned = [
        ROOT / "external_validation_package.py",
        ROOT / "p1_007_external_validation_readiness.py",
        ROOT / "export_p1_007_external_validation_readiness.py",
        ROOT / "P1_007_EXTERNAL_VALIDATION_READINESS_REPORT.md",
        template_path,
    ]
    for path in scanned:
        text = path.read_text(encoding="utf-8")
        assert not any(marker in text for marker in FORBIDDEN_PRIVATE_MARKERS), path
    print("[P1-007 GATE] Private-key block scan on runtime/readiness artifacts: PASSED")

    diff_check = subprocess.run(["git", "diff", "--check"], cwd=ROOT, capture_output=True, text=True)
    if diff_check.returncode != 0:
        raise AssertionError(f"git diff --check failed:\n{diff_check.stdout}\n{diff_check.stderr}")
    print("[P1-007 GATE] git diff --check: PASSED")
    print("P1_007_PHASE_END_HARDENING_GATE_PASSED")


if __name__ == "__main__":
    run()
