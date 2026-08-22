"""Phase-end hardening gate for the P4 blocked-gate readiness control."""
from __future__ import annotations

import ast
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from export_p4_blocked_gate_unblock_readiness import export_p4_readiness
from p4_blocked_gate_unblock_readiness import EXPECTED_BLOCKED, evaluate_p4_blocked_gate_readiness


ROOT = Path(__file__).resolve().parent
FOCUSED = ROOT / "test_p4_blocked_gate_unblock_readiness.py"
TARGETS = (
    ROOT / "p4_blocked_gate_unblock_readiness.py",
    ROOT / "export_p4_blocked_gate_unblock_readiness.py",
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
    assert completed.returncode == 0, f"focused P4 blocker suite failed:\n{completed.stdout}\n{completed.stderr}"
    print("[P4 Blockers Gate] focused/adversarial suite: PASSED")

    imported: set[str] = set()
    for target in TARGETS:
        tree = ast.parse(target.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".", 1)[0])
    assert not imported.intersection(FORBIDDEN_IMPORTS), imported.intersection(FORBIDDEN_IMPORTS)
    print("[P4 Blockers Gate] no network/provider/transport/scheduler imports: PASSED")

    report = evaluate_p4_blocked_gate_readiness()
    assert report["decision"] == "P4_BLOCKED_GATE_UNBLOCK_READINESS_RECONCILED"
    assert report["remediation_codes"] == []
    assert all(report["checks"].values())
    assert report["blocked_gate_ids"] == EXPECTED_BLOCKED
    assert report["status_counts"] == {"BLOCKED": 7, "EVIDENCE_SUBMITTED": 0, "OPEN": 3, "TOTAL": 10}
    assert len(report["records"]) == 7
    assert all(record["status"] == "BLOCKED" for record in report["records"])
    assert all(record["unblock_status"] == "EXTERNAL_EVIDENCE_AND_OWNER_ACTION_PENDING" for record in report["records"])
    assert all(record["local_software_evidence_does_not_unlock"] is True for record in report["records"])
    assert report["unblock_authorized"] is False
    assert report["ready_for_external_review"] is False
    assert report["external_transmission_performed"] is False
    assert report["runtime_mutation_performed"] is False
    assert report["authorization_promoted"] is False
    assert report["production_ready"] is False
    print("[P4 Blockers Gate] seven blockers, unlock conditions and locked boundary: PASSED")

    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory) / "p4-blocked-gates.json"
        exported = export_p4_readiness(output=output)
        assert exported["decision"] == "P4_BLOCKED_GATE_UNBLOCK_READINESS_RECONCILED"
        assert exported["redaction_verified"] is True
        assert exported["external_submission_allowed"] is False
        assert json.loads(output.read_text(encoding="utf-8")) == exported
    print("[P4 Blockers Gate] exporter round-trip and redaction: PASSED")

    serialized = json.dumps(report, ensure_ascii=True, sort_keys=True).lower()
    for marker in ("hn-", "an-", "mrn", "patient_id", "patient_token", "private key", "bearer ", "password", "api_key", "@"):
        assert marker not in serialized
    source = "\n".join(target.read_text(encoding="utf-8") for target in TARGETS)
    assert '"ready_for_external_review": False' in source
    assert '"unblock_authorized": False' in source
    assert '"production_ready": False' in source
    assert '"external_transmission_performed": False' in source
    assert '"runtime_mutation_performed": False' in source
    assert '"authorization_promoted": False' in source
    assert '"production_authorized": True' not in source
    assert '"clinical_validation_authorized": True' not in source
    for marker in PRIVATE_KEY_MARKERS:
        assert marker not in source
    print("[P4 Blockers Gate] redaction, no-self-unblock and private-key scan: PASSED")

    diff_check = subprocess.run(["git", "diff", "--check"], cwd=ROOT, capture_output=True, text=True)
    assert diff_check.returncode == 0, diff_check.stdout + diff_check.stderr
    print("[P4 Blockers Gate] git diff --check: PASSED")
    print("P4_BLOCKED_GATE_UNBLOCK_READINESS_PHASE_END_HARDENING_GATE_PASSED")


if __name__ == "__main__":
    run()
