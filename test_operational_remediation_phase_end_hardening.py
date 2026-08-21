from __future__ import annotations

import ast
import json
from pathlib import Path
import os
import subprocess
import sys
import tempfile

from export_operational_remediation import export_evidence
from operational_remediation_rehearsal import RESUME_CONFIRMATION, run_rehearsal


ROOT = Path(__file__).resolve().parent
TARGETS = (
    ROOT / "operational_remediation_rehearsal.py",
    ROOT / "export_operational_remediation.py",
)
FOCUSED = ROOT / "test_operational_remediation_rehearsal.py"
FORBIDDEN_IMPORTS = {
    "requests",
    "httpx",
    "socket",
    "urllib",
    "boto3",
    "google",
    "azure",
    "celery",
    "apscheduler",
    "schedule",
}
PRIVATE_KEY_MARKERS = tuple(
    "-----BEGIN " + label + "-----"
    for label in (
        "PRIVATE" + " " + "KEY",
        "RSA" + " " + "PRIVATE" + " " + "KEY",
        "EC" + " " + "PRIVATE" + " " + "KEY",
        "OPENSSH" + " " + "PRIVATE" + " " + "KEY",
    )
)


def run() -> None:
    completed = subprocess.run(
        [sys.executable, str(FOCUSED)],
        cwd=ROOT,
        env=os.environ.copy(),
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, f"focused remediation suite failed:\n{completed.stdout}\n{completed.stderr}"
    print("[Remediation GATE] focused/adversarial suite: PASSED")

    imported = set()
    for target in TARGETS:
        tree = ast.parse(target.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".", 1)[0])
    assert not imported.intersection(FORBIDDEN_IMPORTS), imported.intersection(FORBIDDEN_IMPORTS)
    print("[Remediation GATE] no network/provider/scheduler imports: PASSED")

    report = run_rehearsal()
    assert report["transcript_integrity_valid"] is True
    assert report["initial_decision"]["resume_permitted"] is False
    assert report["post_remediation_decision"]["resume_permitted"] is False
    assert report["software_eligibility_decision"]["resume_permitted"] is True
    assert report["software_eligibility_decision"]["resume_executed"] is False
    assert report["production_authorized"] is False
    assert report["clinical_validation_authorized"] is False
    assert report["external_authority"] == "NONE"
    serialized = json.dumps(report, ensure_ascii=True)
    assert "patient_id" not in serialized
    assert "patient_token" not in serialized
    assert "PRIVATE KEY" not in serialized
    print("[Remediation GATE] blocked/confirmation/software-eligibility decisions: PASSED")

    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory) / "evidence.json"
        evidence = export_evidence(output=output, project_root=ROOT)
        assert evidence["read_only"] is True
        assert evidence["execution_performed"] is False
        assert evidence["redaction_verified"] is True
        assert evidence["report"]["transcript_integrity_valid"] is True
        assert json.loads(output.read_text(encoding="utf-8")) == evidence
    print("[Remediation GATE] redacted exporter and transcript hash-chain: PASSED")

    source = "\n".join(target.read_text(encoding="utf-8") for target in TARGETS)
    assert '"production_authorized": True' not in source
    assert '"clinical_validation_authorized": True' not in source
    assert '"external_authority": "NONE"' in source
    assert '"resume_executed": False' in source
    assert RESUME_CONFIRMATION in source
    for marker in PRIVATE_KEY_MARKERS:
        assert marker not in source
    print("[Remediation GATE] no-self-authorization and private-key scan: PASSED")

    diff_check = subprocess.run(["git", "diff", "--check"], cwd=ROOT, capture_output=True, text=True)
    assert diff_check.returncode == 0, diff_check.stdout + diff_check.stderr
    print("[Remediation GATE] git diff --check: PASSED")
    print("OPERATIONAL_REMEDIATION_PHASE_END_HARDENING_GATE_PASSED")


if __name__ == "__main__":
    run()
