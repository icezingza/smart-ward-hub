from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import tempfile

from backup_restore import RESTORE_CONFIRMATION
from durable_worker_store import DurableWorkerStore
from worker_queue_backup import (
    WorkerQueueBackupError,
    create_worker_queue_backup,
    restore_worker_queue_backup,
)


def expect_error(callback) -> None:
    try:
        callback()
    except WorkerQueueBackupError:
        return
    raise AssertionError("expected WorkerQueueBackupError")


def create_store(path: Path) -> None:
    store = DurableWorkerStore(str(path), lease_seconds=10)
    store.submit(
        job_id="backup-job-001",
        job_type="BACKUP_REPORT",
        args={"report_kind": "daily"},
        idempotency_key="backup-idem-001",
        requester_role="reliability_operator",
        approver_role="security_auditor",
        approval_ref="backup-approval-001",
    )
    store.close()


def run() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        source = root / "worker.db"
        create_store(source)
        bundle = create_worker_queue_backup(database_path=source, output_dir=root / "backups", source_revision="fixture-revision-001")
        binding = json.loads((bundle / "worker_queue_binding.json").read_text(encoding="utf-8"))
        assert binding["mode"] == "software_fixture"
        assert binding["external_authority"] is False
        restored_path = root / "restored-worker.db"
        restored = restore_worker_queue_backup(bundle_dir=bundle, target_database=restored_path, confirmation=RESTORE_CONFIRMATION)
        assert restored["worker_queue_restore_status"] == "SOFTWARE_RESTORE_VERIFIED"
        assert restored["binding_verified"] is True
        reopened = DurableWorkerStore(str(restored_path), lease_seconds=10)
        assert reopened.get("backup-job-001")["status"] == "QUEUED"
        reopened.close()
        print("[Worker Backup] SQLite backup binding and separate-target restore: PASSED")

        expect_error(lambda: restore_worker_queue_backup(bundle_dir=bundle, target_database=root / "blocked.db", confirmation="WRONG"))
        binding_path = bundle / "worker_queue_binding.json"
        original = binding_path.read_text(encoding="utf-8")
        mutated = json.loads(original)
        mutated["source_revision"] = "tampered-revision"
        binding_path.write_text(json.dumps(mutated, indent=2) + "\n", encoding="utf-8")
        expect_error(lambda: restore_worker_queue_backup(bundle_dir=bundle, target_database=root / "tampered-binding.db", confirmation=RESTORE_CONFIRMATION))
        binding_path.write_text(original, encoding="utf-8")

        database_artifact = bundle / "database.sqlite3"
        original_bytes = database_artifact.read_bytes()
        database_artifact.write_bytes(original_bytes + b"tamper")
        expect_error(lambda: restore_worker_queue_backup(bundle_dir=bundle, target_database=root / "tampered-db.db", confirmation=RESTORE_CONFIRMATION))
        database_artifact.write_bytes(original_bytes)
        print("[Worker Backup] Confirmation, binding hash and database tamper rejection: PASSED")

        with sqlite3.connect(source) as connection:
            assert connection.execute("SELECT value FROM worker_store_meta WHERE key='schema_version'").fetchone()[0] == "p2-005-durable-worker-v1"
    print("WORKER_QUEUE_BACKUP_TESTS_PASSED")


if __name__ == "__main__":
    run()
