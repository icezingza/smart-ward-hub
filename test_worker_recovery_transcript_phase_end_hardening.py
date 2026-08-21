"""Phase-end hardening gate for operator worker recovery transcript."""

from __future__ import annotations

import ast
import json
from pathlib import Path
import os
import subprocess
import sys
import tempfile

from export_worker_recovery_transcript import export_evidence
from worker_recovery_transcript import build_worker_recovery_transcript


ROOT = Path(__file__).resolve().parent
TARGETS = (
    ROOT / "worker_recovery_transcript.py",
    ROOT / "export_worker_recovery_transcript.py",
)
FOCUSED = ROOT / "test_worker_recovery_transcript.py"
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
    assert completed.returncode == 0, f"focused transcript suite failed:\n{completed.stdout}\n{completed.stderr}"
    print("[WorkerTranscript GATE] focused/adversarial suite: PASSED")

    imported: set[str] = set()
    for target in TARGETS:
        tree = ast.parse(target.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".", 1)[0])
    assert not imported.intersection(FORBIDDEN_IMPORTS), imported.intersection(FORBIDDEN_IMPORTS)
    print("[WorkerTranscript GATE] no network/provider/scheduler imports: PASSED")

    report = build_worker_recovery_transcript()
    assert report["transcript_integrity_valid"] is True
    assert report["read_only"] is True
    assert report["execution_performed"] is False
    assert report["replay_executed"] is False
    assert report["production_authorized"] is False
    assert report["clinical_validation_authorized"] is False
    assert report["external_authority"] == "NONE"
    assert report["runtime_authority"] == "NONE"
    assert len(report["transcript"]) == 5
    assert report["transcript"][0]["event_type"] == "LEASE_EXPIRY_OBSERVED"
    assert report["transcript"][-1]["event_type"] == "QUEUE_BACKUP_BINDING_VERIFIED"
    print("[WorkerTranscript GATE] lifecycle, lease/reconciliation and queue binding: PASSED")

    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory) / "worker-recovery-transcript.json"
        evidence = export_evidence(output=output, project_root=ROOT)
        saved = json.loads(output.read_text(encoding="utf-8"))
        assert saved == evidence
        assert evidence["transcript_integrity_valid"] is True
        assert evidence["redaction_verified"] is True
        assert evidence["read_only"] is True
        assert evidence["execution_performed"] is False
        assert evidence["replay_executed"] is False
        assert evidence["raw_worker_identifiers_exported"] is False
    print("[WorkerTranscript GATE] redacted exporter and hash-chain: PASSED")

    source = "\n".join(target.read_text(encoding="utf-8") for target in TARGETS)
    assert '"production_authorized": True' not in source
    assert '"clinical_validation_authorized": True' not in source
    assert '"external_authority": "NONE"' in source
    assert '"runtime_authority": "NONE"' in source
    assert '"execution_performed": False' in source
    assert '"replay_executed": False' in source
    for marker in PRIVATE_KEY_MARKERS:
        assert marker not in source
    serialized = json.dumps(evidence, ensure_ascii=True)
    for marker in (
        "HN-",
        "AN-",
        "patient_id",
        "patient_token",
        "worker-opaque-a",
        "job-lease-opaque-001",
        "reconcile-opaque-lease-001",
        "PRIVATE KEY",
        "@",
    ):
        assert marker not in serialized
    print("[WorkerTranscript GATE] no-self-authorization, redaction and private-key scan: PASSED")

    diff_check = subprocess.run(["git", "diff", "--check"], cwd=ROOT, capture_output=True, text=True)
    assert diff_check.returncode == 0, diff_check.stdout + diff_check.stderr
    print("[WorkerTranscript GATE] git diff --check: PASSED")
    print("WORKER_RECOVERY_TRANSCRIPT_PHASE_END_HARDENING_GATE_PASSED")


if __name__ == "__main__":
    run()
