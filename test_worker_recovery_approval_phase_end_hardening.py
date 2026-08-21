"""Phase-end hardening gate for worker recovery approval/read-back."""

from __future__ import annotations

import ast
import json
from pathlib import Path
import os
import subprocess
import sys
import tempfile

from export_worker_recovery_approval import export_evidence
from worker_recovery_approval import build_approval_readback


ROOT = Path(__file__).resolve().parent
TARGETS = (
    ROOT / "worker_recovery_approval.py",
    ROOT / "export_worker_recovery_approval.py",
)
FOCUSED = ROOT / "test_worker_recovery_approval.py"
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
    assert completed.returncode == 0, f"focused approval suite failed:\n{completed.stdout}\n{completed.stderr}"
    print("[WorkerApproval GATE] focused/adversarial suite: PASSED")

    imported: set[str] = set()
    for target in TARGETS:
        tree = ast.parse(target.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".", 1)[0])
    assert not imported.intersection(FORBIDDEN_IMPORTS), imported.intersection(FORBIDDEN_IMPORTS)
    print("[WorkerApproval GATE] no network/provider/scheduler imports: PASSED")

    report = build_approval_readback()
    approval = report["approval"]
    validation = report["validation"]
    assert approval["decision"] == "APPROVED_FOR_SOFTWARE_REHEARSAL"
    assert approval["scope"] == "SOFTWARE_REHEARSAL_ONLY"
    assert approval["replay_execution_requested"] is False
    assert approval["replay_executed"] is False
    assert validation["actor_separation_valid"] is True
    assert validation["transcript_binding_valid"] is True
    assert validation["queue_binding_format_valid"] is True
    assert validation["authorization_promoted"] is False
    assert validation["external_execution_authorized"] is False
    assert validation["production_authorized"] is False
    assert validation["clinical_validation_authorized"] is False
    print("[WorkerApproval GATE] actor separation, transcript/queue binding and execution lock: PASSED")

    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory) / "worker-recovery-approval.json"
        evidence = export_evidence(output=output, project_root=ROOT)
        saved = json.loads(output.read_text(encoding="utf-8"))
        assert saved == evidence
        assert evidence["transcript_integrity_valid"] is True
        assert evidence["redaction_verified"] is True
        assert evidence["read_only"] is True
        assert evidence["replay_executed"] is False
        assert evidence["approval"]["replay_execution_requested"] is False
    print("[WorkerApproval GATE] redacted exporter and round-trip: PASSED")

    source = "\n".join(target.read_text(encoding="utf-8") for target in TARGETS)
    assert '"production_authorized": True' not in source
    assert '"clinical_validation_authorized": True' not in source
    assert '"external_execution_authorized": False' in source
    assert '"replay_executed": False' in source
    assert '"runtime_authority": "NONE"' in source
    for marker in PRIVATE_KEY_MARKERS:
        assert marker not in source
    serialized = json.dumps(evidence, ensure_ascii=True)
    for marker in (
        "HN-",
        "AN-",
        "patient_id",
        "patient_token",
        "job-lease-opaque-001",
        "worker-opaque-a",
        "reconcile-opaque-lease-001",
        "PRIVATE KEY",
        "@",
    ):
        assert marker not in serialized
    print("[WorkerApproval GATE] no-self-authorization, redaction and private-key scan: PASSED")

    diff_check = subprocess.run(["git", "diff", "--check"], cwd=ROOT, capture_output=True, text=True)
    assert diff_check.returncode == 0, diff_check.stdout + diff_check.stderr
    print("[WorkerApproval GATE] git diff --check: PASSED")
    print("WORKER_RECOVERY_APPROVAL_PHASE_END_HARDENING_GATE_PASSED")


if __name__ == "__main__":
    run()
