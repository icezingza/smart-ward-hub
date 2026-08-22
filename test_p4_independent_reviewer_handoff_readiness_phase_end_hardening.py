"""Phase-end hardening gate for the P4 reviewer-handoff readiness control."""
from __future__ import annotations

import ast
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from export_p4_independent_reviewer_handoff_readiness import export_reviewer_handoff_readiness
from p4_independent_reviewer_handoff_readiness import evaluate_reviewer_handoff_readiness


ROOT = Path(__file__).resolve().parent
FOCUSED = ROOT / "test_p4_independent_reviewer_handoff_readiness.py"
TARGETS = (
    ROOT / "p4_independent_reviewer_handoff_readiness.py",
    ROOT / "export_p4_independent_reviewer_handoff_readiness.py",
)
FORBIDDEN_IMPORTS = {
    "requests",
    "httpx",
    "socket",
    "urllib",
    "serial",
    "bleak",
    "paho",
    "websockets",
    "google",
    "azure",
    "boto3",
    "celery",
    "apscheduler",
    "schedule",
    "subprocess",
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
    env = os.environ.copy()
    env["PATH"] = f"{Path(sys.executable).parent}:{env.get('PATH', '')}"
    completed = subprocess.run(
        [sys.executable, str(FOCUSED)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, f"focused reviewer handoff suite failed:\n{completed.stdout}\n{completed.stderr}"
    print("[P4 Reviewer Gate] focused/adversarial suite: PASSED")

    imported: set[str] = set()
    for target in TARGETS:
        tree = ast.parse(target.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".", 1)[0])
    assert not imported.intersection(FORBIDDEN_IMPORTS), imported.intersection(FORBIDDEN_IMPORTS)
    print("[P4 Reviewer Gate] no network/provider/transport/scheduler imports: PASSED")

    report = evaluate_reviewer_handoff_readiness()
    assert report["decision"] == "P4_INDEPENDENT_REVIEWER_HANDOFF_READY"
    assert report["remediation_codes"] == []
    assert all(report["checks"].values())
    assert report["mapping_count"] == 12
    assert report["artifact_count"] == 22
    assert report["external_inputs_pending_count"] == 12
    assert report["checklist_status_counts"] == {
        "PENDING_EXTERNAL": 8,
        "SOFTWARE_VERIFIED_PENDING_READBACK": 3,
        "SOFTWARE_LOCKED_EXTERNAL_REVIEW_PENDING": 1,
    }
    assert report["external_gate_status_counts"] == {
        "BLOCKED": 7,
        "EVIDENCE_SUBMITTED": 0,
        "OPEN": 3,
        "TOTAL": 10,
    }
    assert report["ready_for_external_appointment"] is True
    assert report["ready_for_external_review"] is False
    assert report["submission_allowed"] is False
    assert report["read_only"] is True
    assert report["external_transmission_performed"] is False
    assert report["runtime_mutation_performed"] is False
    assert report["authorization_promoted"] is False
    assert report["production_ready"] is False
    assert report["hardware_evidence"] == "UNVERIFIED"
    print("[P4 Reviewer Gate] preflight, checklist and locked boundary: PASSED")

    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory) / "reviewer-handoff.json"
        exported = export_reviewer_handoff_readiness(output=output)
        assert exported["decision"] == "P4_INDEPENDENT_REVIEWER_HANDOFF_READY"
        assert exported["redaction_verified"] is True
        assert exported["external_submission_allowed"] is False
        assert json.loads(output.read_text(encoding="utf-8")) == exported
    print("[P4 Reviewer Gate] exporter round-trip and redaction: PASSED")

    serialized = json.dumps(report, ensure_ascii=True, sort_keys=True).lower()
    for marker in ("hn-", "an-", "mrn", "patient_id", "patient_token", "private key", "bearer ", "password", "api_key", "@"):
        assert marker not in serialized
    source = "\n".join(target.read_text(encoding="utf-8") for target in TARGETS)
    assert '"ready_for_external_review": False' in source
    assert '"submission_allowed": False' in source
    assert '"production_ready": False' in source
    assert '"external_transmission_performed": False' in source
    assert '"runtime_mutation_performed": False' in source
    assert '"authorization_promoted": False' in source
    assert '"production_authorized": True' not in source
    assert '"clinical_validation_authorized": True' not in source
    for marker in PRIVATE_KEY_MARKERS:
        assert marker not in source
    print("[P4 Reviewer Gate] redaction, no-self-authorization and private-key scan: PASSED")

    diff_check = subprocess.run(["git", "diff", "--check"], cwd=ROOT, capture_output=True, text=True)
    assert diff_check.returncode == 0, diff_check.stdout + diff_check.stderr
    print("[P4 Reviewer Gate] git diff --check: PASSED")
    print("P4_INDEPENDENT_REVIEWER_HANDOFF_READINESS_PHASE_END_HARDENING_GATE_PASSED")


if __name__ == "__main__":
    run()
