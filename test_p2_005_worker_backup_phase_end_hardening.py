from __future__ import annotations

import ast
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from durable_worker_store import DurableWorkerStore
from worker_queue_backup import create_worker_queue_backup, restore_worker_queue_backup
from backup_restore import RESTORE_CONFIRMATION


ROOT = Path(__file__).resolve().parent
FOCUSED_TESTS = ("test_worker_queue_backup.py",)
FORBIDDEN_IMPORTS = {"requests", "httpx", "socket", "subprocess", "celery", "apscheduler", "schedule"}
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
    for script in FOCUSED_TESTS:
        completed = subprocess.run(
            [sys.executable, str(ROOT / script)],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
        )
        assert completed.returncode == 0, f"{script} failed:\n{completed.stdout}\n{completed.stderr}"
        print(f"[P2-005 BACKUP GATE] {script}: PASSED")

    worker_source = ast.parse((ROOT / "worker_queue_backup.py").read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(worker_source):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".", 1)[0])
    assert not imported.intersection(FORBIDDEN_IMPORTS), imported.intersection(FORBIDDEN_IMPORTS)
    print("[P2-005 BACKUP GATE] No network/subprocess/scheduler import: PASSED")

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        source = root / "worker.db"
        store = DurableWorkerStore(str(source), lease_seconds=10)
        store.submit(
            job_id="gate-backup-job-001",
            job_type="BACKUP_REPORT",
            args={"report_kind": "gate"},
            idempotency_key="gate-backup-idem-001",
            requester_role="reliability_operator",
            approver_role="security_auditor",
            approval_ref="gate-backup-approval-001",
        )
        store.close()
        bundle = create_worker_queue_backup(database_path=source, output_dir=root / "backups", source_revision="gate-revision")
        result = restore_worker_queue_backup(bundle_dir=bundle, target_database=root / "restored.db", confirmation=RESTORE_CONFIRMATION)
        assert result["binding_verified"] is True
        assert result["external_authority"] is False
        assert result["physical_storage_validation"] == "UNVERIFIED"
    print("[P2-005 BACKUP GATE] Separate-target restore and no-authorization binding: PASSED")

    gate_path = Path(__file__).resolve()
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.resolve() == gate_path or ".git" in path.parts:
            continue
        if path.suffix.lower() not in {".py", ".md", ".json", ".yaml", ".yml", ".env", ".example"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        assert not any(marker in text for marker in PRIVATE_KEY_MARKERS), f"private-key marker found in {path}"
    print("[P2-005 BACKUP GATE] Private-key block scan: PASSED")

    diff_check = subprocess.run(["git", "diff", "--check"], cwd=ROOT, capture_output=True, text=True)
    assert diff_check.returncode == 0, diff_check.stdout + diff_check.stderr
    print("[P2-005 BACKUP GATE] git diff --check: PASSED")
    print("P2_005_WORKER_BACKUP_PHASE_END_HARDENING_GATE_PASSED")


if __name__ == "__main__":
    run()
