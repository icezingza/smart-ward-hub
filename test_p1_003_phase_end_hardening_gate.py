from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from p1_003_key_custody_readiness import template, validate_key_custody_manifest

ROOT = Path(__file__).resolve().parent
FOCUSED_TESTS = (
    "test_key_custody_contract.py",
    "test_key_custody_contract_negative.py",
    "test_p1_003_key_custody_hardening.py",
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
        print(f"[P1-003 GATE] {script}: PASSED")

    template_path = ROOT / "evals/micro_rag/evidence/p1-003-key-custody-readiness-template-20260820.json"
    schema_path = ROOT / "evals/micro_rag/evidence/p1-003-key-custody-readiness-schema-v1.json"
    payload = json.loads(template_path.read_text(encoding="utf-8"))
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    assert validate_key_custody_manifest(payload, template_only=True)["valid"] is True
    assert schema["$id"].endswith("p1-003-key-custody-readiness-v1")
    assert payload["software_evidence_only"] is True
    assert payload["hardware_custody_validation"] == "UNVERIFIED"
    assert payload["key_custody_execution"] == "NOT_STARTED"
    assert payload["authorization_boundary"]["production_authorized"] is False
    print("[P1-003 GATE] Readiness template/schema and locked boundary: PASSED")

    scanned = [
        ROOT / "key_custody_contract.py",
        ROOT / "p1_003_key_custody_readiness.py",
        ROOT / "P1_003_KEY_CUSTODY_READINESS_REPORT.md",
        template_path,
    ]
    for path in scanned:
        text = path.read_text(encoding="utf-8")
        assert not any(marker in text for marker in FORBIDDEN_PRIVATE_MARKERS), path
    print("[P1-003 GATE] Private-key block scan on runtime/readiness artifacts: PASSED")

    diff_check = subprocess.run(["git", "diff", "--check"], cwd=ROOT, capture_output=True, text=True)
    if diff_check.returncode != 0:
        raise AssertionError(f"git diff --check failed:\n{diff_check.stdout}\n{diff_check.stderr}")
    print("[P1-003 GATE] git diff --check: PASSED")
    print("P1_003_PHASE_END_HARDENING_GATE_PASSED")


if __name__ == "__main__":
    run()
