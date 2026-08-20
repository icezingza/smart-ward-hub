from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from p1_005_clinical_shadow_readiness import template, validate_shadow_manifest

ROOT = Path(__file__).resolve().parent
FOCUSED_TESTS = (
    "test_clinical_shadow_mode.py",
    "test_clinical_shadow_mode_negative.py",
    "test_p1_005_clinical_shadow_hardening.py",
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
        print(f"[P1-005 GATE] {script}: PASSED")

    template_path = ROOT / "evals/micro_rag/evidence/p1-005-clinical-shadow-readiness-template-20260820.json"
    schema_path = ROOT / "evals/micro_rag/evidence/p1-005-clinical-shadow-readiness-schema-v1.json"
    payload = json.loads(template_path.read_text(encoding="utf-8"))
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    assert validate_shadow_manifest(payload, template_only=True)["valid"] is True
    assert schema["$id"].endswith("p1-005-clinical-shadow-readiness-v1")
    assert payload["shadow_execution"] == "NOT_STARTED"
    assert payload["clinical_governance"] == "PENDING"
    assert payload["clinical_validation"] == "PENDING"
    assert payload["real_world_authorization"] is False
    assert payload["software_evidence_only"] is True
    assert payload["notification_mode"] == "DISABLED"
    assert payload["evidence_class"] == "SOFTWARE_SHADOW_MODE_NOT_CLINICAL_ACCURACY"
    assert payload["zero_pii_claim"] == "TESTED_INPUT_MARKER_BOUNDARY_NOT_SYSTEMWIDE_PRIVACY_PROOF"
    assert payload["metrics_claim"] == "NON_ACCURACY_WORKFLOW_DATA_QUALITY_ONLY"
    assert payload["authorization_boundary"]["clinical_validation_authorized"] is False
    assert payload["authorization_boundary"]["production_authorized"] is False
    print("[P1-005 GATE] Readiness template/schema, clinical claim lock and no-authorization boundary: PASSED")

    scanned = [
        ROOT / "clinical_shadow_mode.py",
        ROOT / "p1_005_clinical_shadow_readiness.py",
        ROOT / "P1_005_CLINICAL_SHADOW_MODE_CONTRACT.md",
        ROOT / "P1_005_CLINICAL_SHADOW_READINESS_REPORT.md",
        template_path,
    ]
    for path in scanned:
        text = path.read_text(encoding="utf-8")
        assert not any(marker in text for marker in FORBIDDEN_PRIVATE_MARKERS), path
    print("[P1-005 GATE] Private-key block scan on runtime/readiness artifacts: PASSED")

    diff_check = subprocess.run(["git", "diff", "--check"], cwd=ROOT, capture_output=True, text=True)
    if diff_check.returncode != 0:
        raise AssertionError(f"git diff --check failed:\n{diff_check.stdout}\n{diff_check.stderr}")
    print("[P1-005 GATE] git diff --check: PASSED")
    print("P1_005_PHASE_END_HARDENING_GATE_PASSED")


if __name__ == "__main__":
    run()
