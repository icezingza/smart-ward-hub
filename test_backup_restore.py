from __future__ import annotations

from contextlib import closing
import json
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch

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
        with closing(sqlite3.connect(source_db)) as connection:
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
        with closing(sqlite3.connect(restored_db)) as connection:
            assert connection.execute("SELECT value FROM probe WHERE id=1").fetchone()[0] == "durable-fixture"
        assert restored_checkpoint.read_text(encoding="utf-8").startswith("{\"state_version\"")
        print("[P1-001] Separate-target restore and row verification: PASSED")

        interrupted_db = root / "interrupted-target.db"
        interrupted_checkpoint = root / "interrupted-target-checkpoint.json"
        with closing(sqlite3.connect(interrupted_db)) as connection:
            connection.execute("CREATE TABLE probe (id INTEGER PRIMARY KEY, value TEXT NOT NULL)")
            connection.execute("INSERT INTO probe(value) VALUES (?)", ("pre-restore-state",))
            connection.commit()
        interrupted_checkpoint.write_text('{"state_version":1,"buffers":{"before":true}}\n', encoding="utf-8")
        original_replace = Path.replace

        def fail_checkpoint_promotion(source: Path, target: Path):
            if source == interrupted_checkpoint.with_suffix(interrupted_checkpoint.suffix + ".restore-tmp") and target == interrupted_checkpoint:
                raise OSError("simulated interrupted checkpoint promotion")
            return original_replace(source, target)

        try:
            with patch.object(Path, "replace", new=fail_checkpoint_promotion):
                restore_backup_bundle(
                    bundle_dir=bundle,
                    target_database=interrupted_db,
                    target_checkpoint=interrupted_checkpoint,
                    confirmation=RESTORE_CONFIRMATION,
                )
        except OSError as exc:
            assert str(exc) == "simulated interrupted checkpoint promotion"
        else:
            raise AssertionError("interrupted checkpoint promotion was accepted")
        with closing(sqlite3.connect(interrupted_db)) as connection:
            assert connection.execute("SELECT value FROM probe WHERE id=1").fetchone()[0] == "pre-restore-state"
        assert interrupted_checkpoint.read_text(encoding="utf-8") == '{"state_version":1,"buffers":{"before":true}}\n'
        assert not interrupted_db.with_suffix(interrupted_db.suffix + ".restore-tmp").exists()
        assert not interrupted_db.with_suffix(interrupted_db.suffix + ".restore-prev").exists()
        assert not interrupted_checkpoint.with_suffix(interrupted_checkpoint.suffix + ".restore-tmp").exists()
        assert not interrupted_checkpoint.with_suffix(interrupted_checkpoint.suffix + ".restore-prev").exists()
        print("[P1-001] Interrupted checkpoint promotion restores previous targets and cleans staging: PASSED")

        manifest_path = bundle / "manifest.json"
        original_manifest_text = manifest_path.read_text(encoding="utf-8")

        def reject_manifest(mutator, expected: str) -> None:
            mutated = json.loads(original_manifest_text)
            mutator(mutated)
            manifest_path.write_text(json.dumps(mutated, indent=2) + "\n", encoding="utf-8")
            try:
                restore_backup_bundle(
                    bundle_dir=bundle,
                    target_database=root / f"rejected-{expected}.db",
                    confirmation=RESTORE_CONFIRMATION,
                )
            except BackupRestoreError as exc:
                assert str(exc).startswith(expected), str(exc)
            else:
                raise AssertionError(f"manifest mutation accepted: {expected}")
            finally:
                manifest_path.write_text(original_manifest_text, encoding="utf-8")

        reject_manifest(lambda value: value.update({"unexpected": True}), "manifest_unknown_field")
        reject_manifest(lambda value: value["artifacts"].pop("database"), "manifest_artifacts_invalid")
        reject_manifest(lambda value: value["artifacts"]["database"].update({"size_bytes": 0}), "artifact_size_failed:")
        reject_manifest(lambda value: value["artifacts"]["database"].update({"path": "other.sqlite3"}), "manifest_database_binding_invalid")
        reject_manifest(lambda value: value.update({"created_at_utc": "2026-08-20T12:00:00"}), "manifest_timestamp_not_timezone_aware")
        print("[P1-001] Strict backup manifest mutations fail closed: PASSED")

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
            assert str(exc).startswith(("artifact_size_failed:", "artifact_checksum_failed:"))
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
