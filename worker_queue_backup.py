from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import sqlite3
from typing import Any

from backup_restore import RESTORE_CONFIRMATION, BackupRestoreError, create_backup_bundle, restore_backup_bundle


WORKER_QUEUE_BACKUP_SCHEMA = "smart-ward-worker-queue-backup-v1"
STORE_SCHEMA_VERSION = "p2-005-durable-worker-v1"
_HEX64 = re.compile(r"^[a-f0-9]{64}$")


class WorkerQueueBackupError(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _binding_hash(binding: dict[str, Any]) -> str:
    payload = dict(binding)
    payload.pop("binding_sha256", None)
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _read_binding(bundle: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    binding_path = bundle / "worker_queue_binding.json"
    if not binding_path.is_file():
        raise WorkerQueueBackupError("worker_queue_binding_missing")
    try:
        binding = json.loads(binding_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise WorkerQueueBackupError("worker_queue_binding_invalid") from exc
    if not isinstance(binding, dict):
        raise WorkerQueueBackupError("worker_queue_binding_invalid")
    allowed = {
        "schema",
        "backup_id",
        "source_revision",
        "database_artifact_sha256",
        "store_schema_version",
        "mode",
        "external_authority",
        "clinical_state_allowed",
        "binding_sha256",
    }
    if set(binding) != allowed:
        raise WorkerQueueBackupError("worker_queue_binding_schema_invalid")
    if binding["schema"] != WORKER_QUEUE_BACKUP_SCHEMA:
        raise WorkerQueueBackupError("worker_queue_binding_schema_invalid")
    if binding["backup_id"] != bundle.name or binding["backup_id"] != manifest.get("backup_id"):
        raise WorkerQueueBackupError("worker_queue_binding_backup_id_mismatch")
    if not isinstance(binding["source_revision"], str) or not binding["source_revision"].strip():
        raise WorkerQueueBackupError("worker_queue_binding_source_revision_invalid")
    if not isinstance(binding["database_artifact_sha256"], str) or _HEX64.fullmatch(binding["database_artifact_sha256"]) is None:
        raise WorkerQueueBackupError("worker_queue_binding_database_hash_invalid")
    if binding["store_schema_version"] != STORE_SCHEMA_VERSION:
        raise WorkerQueueBackupError("worker_queue_binding_store_schema_invalid")
    if binding["mode"] != "software_fixture":
        raise WorkerQueueBackupError("worker_queue_binding_mode_invalid")
    if binding["external_authority"] is not False or binding["clinical_state_allowed"] is not False:
        raise WorkerQueueBackupError("worker_queue_binding_authorization_invalid")
    if not isinstance(binding["binding_sha256"], str) or _HEX64.fullmatch(binding["binding_sha256"]) is None:
        raise WorkerQueueBackupError("worker_queue_binding_hash_invalid")
    if _binding_hash(binding) != binding["binding_sha256"]:
        raise WorkerQueueBackupError("worker_queue_binding_checksum_failed")
    database_artifact = manifest.get("artifacts", {}).get("database", {})
    if database_artifact.get("sha256") != binding["database_artifact_sha256"]:
        raise WorkerQueueBackupError("worker_queue_binding_database_hash_mismatch")
    if _sha256(bundle / str(database_artifact.get("path"))) != binding["database_artifact_sha256"]:
        raise WorkerQueueBackupError("worker_queue_binding_database_checksum_failed")
    return binding


def _assert_worker_store_database(path: Path) -> None:
    try:
        with sqlite3.connect(path) as connection:
            schema = connection.execute("SELECT value FROM worker_store_meta WHERE key='schema_version'").fetchone()
            integrity = str(connection.execute("PRAGMA integrity_check").fetchone()[0]).lower()
    except sqlite3.Error as exc:
        raise WorkerQueueBackupError(f"worker_store_database_invalid:{type(exc).__name__}") from exc
    if schema is None or schema[0] != STORE_SCHEMA_VERSION:
        raise WorkerQueueBackupError("worker_store_schema_version_mismatch")
    if integrity != "ok":
        raise WorkerQueueBackupError("worker_store_integrity_failed")


def create_worker_queue_backup(*, database_path: Path, output_dir: Path, source_revision: str) -> Path:
    database_path = database_path.expanduser().resolve()
    if not database_path.is_file():
        raise WorkerQueueBackupError("worker_store_database_not_found")
    if not isinstance(source_revision, str) or not source_revision.strip():
        raise WorkerQueueBackupError("source_revision_required")
    _assert_worker_store_database(database_path)
    bundle = create_backup_bundle(
        database_path=database_path,
        output_dir=output_dir,
        source_revision=source_revision,
    )
    try:
        manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
        database_hash = manifest["artifacts"]["database"]["sha256"]
        binding: dict[str, Any] = {
            "schema": WORKER_QUEUE_BACKUP_SCHEMA,
            "backup_id": bundle.name,
            "source_revision": source_revision,
            "database_artifact_sha256": database_hash,
            "store_schema_version": STORE_SCHEMA_VERSION,
            "mode": "software_fixture",
            "external_authority": False,
            "clinical_state_allowed": False,
        }
        binding["binding_sha256"] = _binding_hash(binding)
        (bundle / "worker_queue_binding.json").write_text(json.dumps(binding, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return bundle
    except Exception:
        import shutil

        shutil.rmtree(bundle, ignore_errors=True)
        raise


def restore_worker_queue_backup(*, bundle_dir: Path, target_database: Path, confirmation: str) -> dict[str, Any]:
    bundle = bundle_dir.expanduser().resolve()
    target_database = target_database.expanduser().resolve()
    if confirmation != RESTORE_CONFIRMATION:
        raise WorkerQueueBackupError("restore_confirmation_required")
    if not bundle.is_dir():
        raise WorkerQueueBackupError("worker_queue_bundle_not_found")
    manifest_path = bundle / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise WorkerQueueBackupError("worker_queue_manifest_invalid") from exc
    try:
        binding = _read_binding(bundle, manifest)
        temporary_target = target_database.with_suffix(target_database.suffix + ".worker-restore-tmp")
        temporary_target.unlink(missing_ok=True)
        restored = restore_backup_bundle(
            bundle_dir=bundle,
            target_database=temporary_target,
            confirmation=confirmation,
        )
        _assert_worker_store_database(temporary_target)
        temporary_target.replace(target_database)
        return {
            "worker_queue_restore_status": "SOFTWARE_RESTORE_VERIFIED",
            "restore_status": restored["restore_status"],
            "source_backup_id": binding["backup_id"],
            "source_revision": binding["source_revision"],
            "worker_store_schema_version": binding["store_schema_version"],
            "binding_verified": True,
            "patient_data_used": False,
            "secret_material_restored": False,
            "physical_storage_validation": "UNVERIFIED",
            "external_authority": False,
        }
    except BackupRestoreError as exc:
        raise WorkerQueueBackupError(f"worker_queue_restore_rejected:{exc}") from exc
    finally:
        temporary_target = target_database.with_suffix(target_database.suffix + ".worker-restore-tmp")
        temporary_target.unlink(missing_ok=True)
