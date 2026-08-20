from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from p1_006_clinical_validation_readiness import template, validate_manifest

ROOT = Path(__file__).resolve().parent
FOCUSED_TESTS = (
    "test_clinical_validation_readiness.py",
    "test_p1_006_clinical_validation_hardening.py",
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
        print(f"[P1-006 GATE] {script}: PASSED")

    template_path = ROOT / "evals/micro_rag/evidence/p1-006-clinical-validation-readiness-template-20260820.json"
    schema_path = ROOT / "evals/micro_rag/evidence/p1-006-clinical-validation-readiness-schema-v1.json"
    payload = json.loads(template_path.read_text(encoding="utf-8"))
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    assert validate_manifest(payload, template_only=True)["valid"] is True
    assert schema["$id"].endswith("p1-006-clinical-validation-readiness-v1")
    assert payload["preflight_status"] == "READY_FOR_EXTERNAL_GOVERNANCE_REVIEW"
    assert payload["execution_status"] == "NOT_STARTED"
    assert payload["clinical_governance"] == "PENDING"
    assert payload["clinical_validation"] == "PENDING"
    assert payload["real_world_authorization"] is False
    assert payload["software_evidence_only"] is True
    assert payload["evidence_class"] == "SOFTWARE_PREFLIGHT_UNVERIFIED"
    assert payload["clinical_claim_boundary"] == "NO_CLINICAL_VALIDATION_OR_ACCURACY_CLAIM"
    assert payload["analysis_semantics"]["accuracy_claim_forbidden"] is True
    assert payload["analysis_semantics"]["synthetic_data_not_clinical_evidence"] is True
    assert payload["authorization_boundary"]["clinical_validation_authorized"] is False
    assert payload["authorization_boundary"]["production_authorized"] is False
    assert len(payload["tracks"]) == 10
    assert len(payload["hard_stops"]) == 10
    print("[P1-006 GATE] Readiness template/schema, 10-track coverage and no-authorization boundary: PASSED")

    scanned = [
        ROOT / "clinical_validation_readiness.py",
        ROOT / "p1_006_clinical_validation_readiness.py",
        ROOT / "export_p1_006_clinical_validation_readiness.py",
        ROOT / "P1_006_CLINICAL_VALIDATION_READINESS_REPORT.md",
        template_path,
    ]
    for path in scanned:
        text = path.read_text(encoding="utf-8")
        assert not any(marker in text for marker in FORBIDDEN_PRIVATE_MARKERS), path
    print("[P1-006 GATE] Private-key block scan on runtime/readiness artifacts: PASSED")

    diff_check = subprocess.run(["git", "diff", "--check"], cwd=ROOT, capture_output=True, text=True)
    if diff_check.returncode != 0:
        raise AssertionError(f"git diff --check failed:\n{diff_check.stdout}\n{diff_check.stderr}")
    print("[P1-006 GATE] git diff --check: PASSED")
    print("P1_006_PHASE_END_HARDENING_GATE_PASSED")


if __name__ == "__main__":
    run()
