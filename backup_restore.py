from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import secrets
import shutil
import sqlite3
from typing import Any


RESTORE_CONFIRMATION = "I_UNDERSTAND_RESTORE_TO_NONPRODUCTION_TARGET"
_SECRET_NAME = re.compile(r"(^|[._-])(env|key|pem|p12|pfx|crt|secret|credential)([._-]|$)", re.IGNORECASE)
_HEX64 = re.compile(r"^[a-f0-9]{64}$")
_ALLOWED_ARTIFACTS = {"database", "telemetry_checkpoint", "forensic_manifest"}
_ALLOWED_MANIFEST_FIELDS = {
    "schema",
    "backup_id",
    "created_at_utc",
    "source_revision",
    "source_database",
    "secret_material_included",
    "artifacts",
    "restore_status",
    "physical_storage_validation",
}


class BackupRestoreError(RuntimeError):
    pass


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _assert_safe_artifact(path: Path) -> None:
    if _SECRET_NAME.search(path.name):
        raise BackupRestoreError(f"secret_like_artifact_rejected:{path.name}")
    if path.suffix.lower() in {".env", ".key", ".pem", ".p12", ".pfx", ".crt"}:
        raise BackupRestoreError(f"secret_like_artifact_rejected:{path.name}")
    if not path.is_file():
        raise BackupRestoreError(f"artifact_not_found:{path}")


def _sqlite_metadata(path: Path) -> dict[str, Any]:
    try:
        with sqlite3.connect(path) as connection:
            journal_mode = str(connection.execute("PRAGMA journal_mode").fetchone()[0]).lower()
            synchronous = connection.execute("PRAGMA synchronous").fetchone()[0]
            integrity = str(connection.execute("PRAGMA integrity_check").fetchone()[0])
            user_version = int(connection.execute("PRAGMA user_version").fetchone()[0])
            alembic_revision = None
            tables = {
                row[0]
                for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            }
            if "alembic_version" in tables:
                alembic_revision = connection.execute("SELECT version_num FROM alembic_version LIMIT 1").fetchone()[0]
            return {
                "journal_mode": journal_mode,
                "synchronous": synchronous,
                "integrity_check": integrity,
                "user_version": user_version,
                "alembic_revision": alembic_revision,
            }
    except sqlite3.Error as exc:
        raise BackupRestoreError(f"sqlite_metadata_failed:{type(exc).__name__}") from exc


def _sqlite_backup(source: Path, destination: Path) -> dict[str, Any]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        # SQLite's backup API reads a consistent snapshot and includes WAL state;
        # do not copy the .db file or checkpoint a read-only connection here.
        with sqlite3.connect(source) as source_connection:
            source_connection.execute("PRAGMA busy_timeout=5000")
            with sqlite3.connect(destination) as destination_connection:
                source_connection.backup(destination_connection)
                destination_connection.execute("PRAGMA synchronous=FULL")
                destination_connection.commit()
        metadata = _sqlite_metadata(destination)
        if metadata["integrity_check"] != "ok":
            raise BackupRestoreError("backup_integrity_check_failed")
        return metadata
    except sqlite3.Error as exc:
        raise BackupRestoreError(f"sqlite_backup_failed:{type(exc).__name__}") from exc


def _copy_artifact(source: Path, destination: Path) -> dict[str, Any]:
    _assert_safe_artifact(source)
    shutil.copy2(source, destination)
    return {
        "path": destination.name,
        "size_bytes": destination.stat().st_size,
        "sha256": _sha256(destination),
    }


def create_backup_bundle(
    *,
    database_path: Path,
    output_dir: Path,
    checkpoint_path: Path | None = None,
    forensic_manifest_path: Path | None = None,
    source_revision: str = "unknown",
) -> Path:
    database_path = database_path.expanduser().resolve()
    output_dir = output_dir.expanduser().resolve()
    if not database_path.is_file():
        raise BackupRestoreError(f"database_not_found:{database_path}")
    output_dir.mkdir(parents=True, exist_ok=True)
    bundle = output_dir / f"backup-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{secrets.token_hex(4)}"
    bundle.mkdir()
    try:
        db_target = bundle / "database.sqlite3"
        sqlite_metadata = _sqlite_backup(database_path, db_target)
        artifacts: dict[str, dict[str, Any]] = {
            "database": {
                "path": db_target.name,
                "size_bytes": db_target.stat().st_size,
                "sha256": _sha256(db_target),
                "sqlite": sqlite_metadata,
            }
        }
        optional = {
            "telemetry_checkpoint": checkpoint_path,
            "forensic_manifest": forensic_manifest_path,
        }
        for kind, source in optional.items():
            if source is None:
                continue
            source = source.expanduser().resolve()
            target = bundle / source.name
            artifacts[kind] = _copy_artifact(source, target)
        manifest = {
            "schema": "smart-ward-backup-manifest-v1",
            "backup_id": bundle.name,
            "created_at_utc": _utc_now(),
            "source_revision": source_revision,
            "source_database": str(database_path),
            "secret_material_included": False,
            "artifacts": artifacts,
            "restore_status": "UNVERIFIED",
            "physical_storage_validation": "UNVERIFIED",
        }
        manifest_path = bundle / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
        return bundle
    except Exception:
        shutil.rmtree(bundle, ignore_errors=True)
        raise


def _read_and_verify_manifest(bundle: Path) -> dict[str, Any]:
    manifest_path = bundle / "manifest.json"
    if not manifest_path.is_file():
        raise BackupRestoreError("manifest_not_found")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BackupRestoreError("manifest_invalid") from exc
    if not isinstance(manifest, dict):
        raise BackupRestoreError("manifest_invalid")
    if set(manifest) - _ALLOWED_MANIFEST_FIELDS:
        raise BackupRestoreError("manifest_unknown_field")
    required = _ALLOWED_MANIFEST_FIELDS
    if not required.issubset(manifest):
        raise BackupRestoreError("manifest_required_field_missing")
    if manifest.get("schema") != "smart-ward-backup-manifest-v1":
        raise BackupRestoreError("manifest_schema_invalid")
    if manifest.get("backup_id") != bundle.name:
        raise BackupRestoreError("manifest_backup_id_mismatch")
    created_at = manifest.get("created_at_utc")
    if not isinstance(created_at, str):
        raise BackupRestoreError("manifest_timestamp_invalid")
    try:
        parsed_created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise BackupRestoreError("manifest_timestamp_invalid") from exc
    if parsed_created_at.tzinfo is None:
        raise BackupRestoreError("manifest_timestamp_not_timezone_aware")
    if not isinstance(manifest.get("source_revision"), str) or not manifest["source_revision"].strip():
        raise BackupRestoreError("manifest_source_revision_invalid")
    if manifest.get("secret_material_included") is not False:
        raise BackupRestoreError("manifest_secret_boundary_invalid")
    if manifest.get("restore_status") != "UNVERIFIED":
        raise BackupRestoreError("manifest_restore_status_invalid")
    if manifest.get("physical_storage_validation") != "UNVERIFIED":
        raise BackupRestoreError("manifest_physical_validation_invalid")

    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict) or "database" not in artifacts:
        raise BackupRestoreError("manifest_artifacts_invalid")
    if set(artifacts) - _ALLOWED_ARTIFACTS:
        raise BackupRestoreError("manifest_artifact_kind_invalid")
    seen_paths: set[Path] = set()
    for kind, artifact in artifacts.items():
        if not isinstance(artifact, dict):
            raise BackupRestoreError("manifest_artifact_invalid")
        allowed_fields = {"path", "size_bytes", "sha256"} | ({"sqlite"} if kind == "database" else set())
        if set(artifact) - allowed_fields or not {"path", "size_bytes", "sha256"}.issubset(artifact):
            raise BackupRestoreError("manifest_artifact_schema_invalid")
        raw_relative = artifact.get("path")
        if not isinstance(raw_relative, str) or not raw_relative or "\\" in raw_relative:
            raise BackupRestoreError("manifest_path_invalid")
        relative = Path(raw_relative)
        if relative.is_absolute() or ".." in relative.parts or relative in seen_paths:
            raise BackupRestoreError("manifest_path_traversal")
        if relative.name == "manifest.json" or _SECRET_NAME.search(relative.name) or relative.suffix.lower() in {".env", ".key", ".pem", ".p12", ".pfx", ".crt"}:
            raise BackupRestoreError("manifest_secret_like_artifact")
        if kind == "database" and relative != Path("database.sqlite3"):
            raise BackupRestoreError("manifest_database_binding_invalid")
        size_bytes = artifact.get("size_bytes")
        if not isinstance(size_bytes, int) or isinstance(size_bytes, bool) or size_bytes < 0:
            raise BackupRestoreError("manifest_artifact_size_invalid")
        digest = artifact.get("sha256")
        if not isinstance(digest, str) or _HEX64.fullmatch(digest) is None:
            raise BackupRestoreError("manifest_artifact_hash_invalid")
        artifact_path = bundle / relative
        if not artifact_path.is_file():
            raise BackupRestoreError(f"artifact_not_found:{relative.name}")
        if artifact_path.stat().st_size != size_bytes:
            raise BackupRestoreError(f"artifact_size_failed:{relative.name}")
        if _sha256(artifact_path) != digest:
            raise BackupRestoreError(f"artifact_checksum_failed:{relative.name}")
        if kind == "database":
            sqlite_metadata = artifact.get("sqlite")
            if not isinstance(sqlite_metadata, dict) or sqlite_metadata.get("integrity_check") != "ok":
                raise BackupRestoreError("manifest_database_metadata_invalid")
        seen_paths.add(relative)
    return manifest


def restore_backup_bundle(
    *,
    bundle_dir: Path,
    target_database: Path,
    confirmation: str,
    target_checkpoint: Path | None = None,
) -> dict[str, Any]:
    if confirmation != RESTORE_CONFIRMATION:
        raise BackupRestoreError("restore_confirmation_required")
    bundle = bundle_dir.expanduser().resolve()
    target_database = target_database.expanduser().resolve()
    if not bundle.is_dir():
        raise BackupRestoreError("bundle_not_found")
    if target_database == bundle / "database.sqlite3":
        raise BackupRestoreError("restore_target_must_be_separate")
    manifest = _read_and_verify_manifest(bundle)
    database_artifact = manifest.get("artifacts", {}).get("database", {})
    source_database = bundle / str(database_artifact.get("path"))
    target_database.parent.mkdir(parents=True, exist_ok=True)
    temporary_target = target_database.with_suffix(target_database.suffix + ".restore-tmp")
    if temporary_target.exists():
        temporary_target.unlink()
    metadata = _sqlite_backup(source_database, temporary_target)
    if metadata["integrity_check"] != "ok":
        temporary_target.unlink(missing_ok=True)
        raise BackupRestoreError("restore_integrity_check_failed")
    temporary_target.replace(target_database)
    restored_checkpoint = None
    if target_checkpoint is not None:
        checkpoint_artifact = manifest.get("artifacts", {}).get("telemetry_checkpoint")
        if not checkpoint_artifact:
            raise BackupRestoreError("checkpoint_artifact_missing")
        source_checkpoint = bundle / str(checkpoint_artifact["path"])
        target_checkpoint = target_checkpoint.expanduser().resolve()
        target_checkpoint.parent.mkdir(parents=True, exist_ok=True)
        temporary_checkpoint = target_checkpoint.with_suffix(target_checkpoint.suffix + ".restore-tmp")
        shutil.copy2(source_checkpoint, temporary_checkpoint)
        temporary_checkpoint.replace(target_checkpoint)
        restored_checkpoint = str(target_checkpoint)
    return {
        "restore_status": "SOFTWARE_RESTORE_VERIFIED",
        "target_database": str(target_database),
        "target_checkpoint": restored_checkpoint,
        "database_integrity_check": metadata["integrity_check"],
        "physical_storage_validation": "UNVERIFIED",
        "source_backup_id": manifest["backup_id"],
        "patient_data_used": False,
        "secret_material_restored": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Safe SQLite Edge backup/restore utility")
    subparsers = parser.add_subparsers(dest="command", required=True)
    backup = subparsers.add_parser("backup")
    backup.add_argument("--database", type=Path, required=True)
    backup.add_argument("--output-dir", type=Path, required=True)
    backup.add_argument("--checkpoint", type=Path)
    backup.add_argument("--forensic-manifest", type=Path)
    backup.add_argument("--source-revision", default="unknown")
    restore = subparsers.add_parser("restore")
    restore.add_argument("--bundle", type=Path, required=True)
    restore.add_argument("--target-database", type=Path, required=True)
    restore.add_argument("--target-checkpoint", type=Path)
    restore.add_argument("--confirm", required=True)
    args = parser.parse_args()
    if args.command == "backup":
        bundle = create_backup_bundle(
            database_path=args.database,
            output_dir=args.output_dir,
            checkpoint_path=args.checkpoint,
            forensic_manifest_path=args.forensic_manifest,
            source_revision=args.source_revision,
        )
        print(json.dumps({"backup_status": "SOFTWARE_BACKUP_CREATED", "bundle": str(bundle)}, sort_keys=True))
        return 0
    result = restore_backup_bundle(
        bundle_dir=args.bundle,
        target_database=args.target_database,
        target_checkpoint=args.target_checkpoint,
        confirmation=args.confirm,
    )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
