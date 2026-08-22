"""Phase-end hardening gate for the P4 reviewer read-back decision guard."""
from __future__ import annotations

import ast
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

from export_p4_reviewer_readback_decision_guard import export_reviewer_readback_decision_guard
from p4_reviewer_readback_decision_guard import evaluate_readback_guard


ROOT = Path(__file__).resolve().parent
FOCUSED = ROOT / "test_p4_reviewer_readback_decision_guard.py"
TARGETS = (
    ROOT / "p4_reviewer_readback_decision_guard.py",
    ROOT / "export_p4_reviewer_readback_decision_guard.py",
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
    assert completed.returncode == 0, f"focused read-back suite failed:\n{completed.stdout}\n{completed.stderr}"
    print("[P4 Read-back Gate] focused/adversarial suite: PASSED")

    imported: set[str] = set()
    for target in TARGETS:
        tree = ast.parse(target.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".", 1)[0])
    assert not imported.intersection(FORBIDDEN_IMPORTS), imported.intersection(FORBIDDEN_IMPORTS)
    print("[P4 Read-back Gate] no network/provider/transport/scheduler imports: PASSED")

    report = evaluate_readback_guard()
    assert report["decision"] == "P4_REVIEWER_READBACK_GUARD_VERIFIED"
    assert report["remediation_codes"] == []
    assert all(report["checks"].values())
    assert report["fresh_poll_result"]["result"] == "POLL_ACCEPTED_UNVERIFIED"
    assert report["fresh_poll_result"]["trusted"] is False
    assert report["fresh_poll_result"]["external_decision_verified"] is False
    assert report["stale_poll_result"]["result"] == "STALE_RESPONSE_REJECTED"
    assert report["external_update_result"]["state"] == "BLOCKED_SIMULATION"
    assert report["external_update_result"]["trusted"] is False
    assert report["external_update_result"]["external_decision_verified"] is False
    assert report["external_update_result"]["authorization_promoted"] is False
    assert report["post_update_status"]["authorization_boundary"] == {
        "external_authority": "NONE",
        "clinical_validation_authorized": False,
        "production_authorized": False,
        "runtime_authority": "NONE",
        "pilot_gate_status": "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION",
    }
    assert report["unauthorized_local_update_rejected"] is True
    assert report["audit_event_count"] == 2
    assert report["appointment_confirmed"] is False
    assert report["ready_for_external_appointment"] is True
    assert report["ready_for_external_review"] is False
    assert report["submission_allowed"] is False
    assert report["external_transmission_performed"] is False
    assert report["runtime_mutation_performed"] is False
    assert report["authorization_promoted"] is False
    assert report["production_ready"] is False
    assert report["hardware_evidence"] == "UNVERIFIED"
    print("[P4 Read-back Gate] poll/update/revision and locked boundary: PASSED")

    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory) / "p4-reviewer-readback-decision-guard.json"
        exported = export_reviewer_readback_decision_guard(output=output)
        assert exported["decision"] == "P4_REVIEWER_READBACK_GUARD_VERIFIED"
        assert exported["evidence_scope"] == "LOCAL_DETERMINISTIC_FIXTURE_ONLY"
        assert exported["redaction_verified"] is True
        assert exported["external_submission_allowed"] is False
        assert exported["external_transmission_performed"] is False
        assert exported["external_readback_trusted"] is False
        assert exported["external_decision_verified"] is False
        assert exported["authorization_promoted"] is False
        assert json.loads(output.read_text(encoding="utf-8")) == exported
    print("[P4 Read-back Gate] exporter round-trip and locked export boundary: PASSED")

    serialized = json.dumps(report, ensure_ascii=True, sort_keys=True)
    assert re.search(r"\b(?:HN|AN|MRN|NATIONAL[_ -]?ID)(?:\s*[-_:]\s*[A-Z0-9-]{2,}|\s+\d[A-Z0-9-]{1,})\b", serialized, re.IGNORECASE) is None
    for marker in ("patient_id", "patient_token", "private key", "bearer ", "password", "api_key", "@"):
        assert marker.lower() not in serialized.lower()
    source = "\n".join(target.read_text(encoding="utf-8") for target in TARGETS)
    assert report["authorization_promoted"] is False
    assert report["external_transmission_performed"] is False
    assert report["runtime_mutation_performed"] is False
    assert report["production_ready"] is False
    assert '"production_authorized": True' not in source
    assert '"clinical_validation_authorized": True' not in source
    assert '"external_execution_authorized": True' not in source
    for marker in PRIVATE_KEY_MARKERS:
        assert marker not in source
    print("[P4 Read-back Gate] redaction, no-self-authorization and private-key scan: PASSED")

    diff_check = subprocess.run(["git", "diff", "--check"], cwd=ROOT, capture_output=True, text=True)
    assert diff_check.returncode == 0, diff_check.stdout + diff_check.stderr
    print("[P4 Read-back Gate] git diff --check: PASSED")
    print("P4_REVIEWER_READBACK_DECISION_GUARD_PHASE_END_HARDENING_GATE_PASSED")


if __name__ == "__main__":
    run()
