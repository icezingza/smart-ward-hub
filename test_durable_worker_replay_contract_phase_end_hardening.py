"""Phase-end hardening gate for durable worker replay contract."""

from __future__ import annotations

import ast
import json
from pathlib import Path
import os
import subprocess
import sys

from durable_worker_replay_contract import run_rehearsal


ROOT = Path(__file__).resolve().parent
TARGETS = (ROOT / "durable_worker_replay_contract.py",)
FOCUSED = ROOT / "test_durable_worker_replay_contract.py"
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
    assert completed.returncode == 0, f"focused worker replay suite failed:\n{completed.stdout}\n{completed.stderr}"
    print("[WorkerReplay GATE] focused/adversarial suite: PASSED")

    imported: set[str] = set()
    for target in TARGETS:
        tree = ast.parse(target.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".", 1)[0])
    assert not imported.intersection(FORBIDDEN_IMPORTS), imported.intersection(FORBIDDEN_IMPORTS)
    print("[WorkerReplay GATE] no network/provider/scheduler imports: PASSED")

    report = run_rehearsal()
    assert report["mode"] == "SOFTWARE_FIXTURE"
    assert report["read_only_external_boundary"] is True
    assert report["external_transmission_performed"] is False
    assert report["clinical_state_mutation_performed"] is False
    assert report["runtime_replay_executed"] is False
    assert report["authorization_boundary"] == {
        "external_authority": False,
        "production_authorized": False,
        "runtime_authority": "NONE",
    }
    assert report["lease_recovery"]["blocked_classification"] == "LEASE_EXPIRED_REQUIRES_RECONCILIATION"
    assert report["lease_recovery"]["requeued_status"] == "QUEUED"
    assert report["dead_letter"]["confirmation_required"]["replay_executed"] is False
    assert report["dead_letter"]["replay_eligible"]["replay_executed"] is False
    assert report["backup_restore"]["restore_result"]["binding_verified"] is True
    assert report["backup_restore"]["restored_health"]["audit_chain_valid"] is True
    assert report["backup_restore"]["restored_health"]["journal_mode"] == "wal"
    assert report["backup_restore"]["restored_health"]["synchronous"] == 2
    print("[WorkerReplay GATE] lease/restart/dead-letter/backup boundary: PASSED")

    source = "\n".join(target.read_text(encoding="utf-8") for target in TARGETS)
    assert '"production_authorized": True' not in source
    assert '"external_authority": True' not in source
    assert '"runtime_authority": "WORKER"' not in source
    assert "replay_executed" in source and "replay_executed=False" in source
    assert '"external_transmission_performed": False' in source
    for marker in PRIVATE_KEY_MARKERS:
        assert marker not in source
    serialized = json.dumps(report, ensure_ascii=True)
    for marker in ("HN-", "AN-", "patient_id", "patient_token", "PRIVATE KEY", "@"):
        assert marker not in serialized
    print("[WorkerReplay GATE] no-self-authorization, redaction and private-key scan: PASSED")

    diff_check = subprocess.run(["git", "diff", "--check"], cwd=ROOT, capture_output=True, text=True)
    assert diff_check.returncode == 0, diff_check.stdout + diff_check.stderr
    print("[WorkerReplay GATE] git diff --check: PASSED")
    print("DURABLE_WORKER_REPLAY_CONTRACT_PHASE_END_HARDENING_GATE_PASSED")


if __name__ == "__main__":
    run()
