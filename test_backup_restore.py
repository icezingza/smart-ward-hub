from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path

from backup_restore import (
    RESTORE_CONFIRMATION,
    BackupRestoreError,
    create_backup_bundle,
    restore_backup_bundle,
)


def run() -> None:
    with tempfile.TemporaryDirectory(prefix="smart-ward-backup-test-") as directory:
        root = Path(directory)
        source_db = root / "source.db"
        checkpoint = root / "checkpoint.json"
        backup_root = root / "backups"
        restored_db = root / "restored.db"
        restored_checkpoint = root / "restored-checkpoint.json"
        with sqlite3.connect(source_db) as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA synchronous=FULL")
            connection.execute("CREATE TABLE probe (id INTEGER PRIMARY KEY, value TEXT NOT NULL)")
            connection.execute("INSERT INTO probe(value) VALUES (?)", ("durable-fixture",))
            connection.commit()
        checkpoint.write_text('{"state_version":1,"buffers":{}}\n', encoding="utf-8")

        bundle = create_backup_bundle(
            database_path=source_db,
            output_dir=backup_root,
            checkpoint_path=checkpoint,
            source_revision="test-revision",
        )
        manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
        assert manifest["secret_material_included"] is False
        assert manifest["restore_status"] == "UNVERIFIED"
        assert manifest["artifacts"]["database"]["sqlite"]["integrity_check"] == "ok"
        print("[P1-001] SQLite backup API creates manifest and integrity evidence: PASSED")

        restored = restore_backup_bundle(
            bundle_dir=bundle,
            target_database=restored_db,
            target_checkpoint=restored_checkpoint,
            confirmation=RESTORE_CONFIRMATION,
        )
        assert restored["restore_status"] == "SOFTWARE_RESTORE_VERIFIED"
        assert restored["database_integrity_check"] == "ok"
        with sqlite3.connect(restored_db) as connection:
            assert connection.execute("SELECT value FROM probe WHERE id=1").fetchone()[0] == "durable-fixture"
        assert restored_checkpoint.read_text(encoding="utf-8").startswith("{\"state_version\"")
        print("[P1-001] Separate-target restore and row verification: PASSED")

        try:
            restore_backup_bundle(
                bundle_dir=bundle,
                target_database=root / "blocked.db",
                confirmation="WRONG_CONFIRMATION",
            )
        except BackupRestoreError as exc:
            assert str(exc) == "restore_confirmation_required"
        else:
            raise AssertionError("restore proceeded without explicit confirmation")
        print("[P1-001] Restore blocks without exact non-production confirmation: PASSED")

        tampered = bundle / "checkpoint.json"
        tampered.write_text('{"state_version":1,"buffers":{"tampered":true}}\n', encoding="utf-8")
        try:
            restore_backup_bundle(
                bundle_dir=bundle,
                target_database=root / "tampered.db",
                confirmation=RESTORE_CONFIRMATION,
            )
        except BackupRestoreError as exc:
            assert str(exc).startswith("artifact_checksum_failed:")
        else:
            raise AssertionError("tampered artifact was accepted")
        print("[P1-001] Manifest checksum rejects tampered artifact: PASSED")

        secret_like = root / "private.key"
        secret_like.write_text("not-a-real-key", encoding="utf-8")
        try:
            create_backup_bundle(
                database_path=source_db,
                output_dir=root / "secret-rejected",
                checkpoint_path=secret_like,
            )
        except BackupRestoreError as exc:
            assert str(exc).startswith("secret_like_artifact_rejected:")
        else:
            raise AssertionError("secret-like artifact was included")
        print("[P1-001] Secret-like artifact is excluded from backup bundle: PASSED")

    print("BACKUP_RESTORE_REGRESSION_TESTS_PASSED")


if __name__ == "__main__":
    run()
