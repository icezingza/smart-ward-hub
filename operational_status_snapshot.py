from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
from typing import Mapping

from internal_foundation_readiness import AUTHORIZATION_BOUNDARY, evaluate_internal_foundation
from operational_thresholds import collect_optional_metrics, evaluate_thresholds, load_thresholds


SCHEMA_VERSION = "smart-ward-operational-status-v1"
SECRET_NAME_MARKERS = ("TOKEN", "SECRET", "PASSWORD", "PRIVATE", "KEY", "CREDENTIAL")


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _source_revision(project_root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(project_root), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return "UNAVAILABLE"
    revision = result.stdout.strip().lower()
    return revision if len(revision) == 40 and all(char in "0123456789abcdef" for char in revision) else "UNAVAILABLE"


def _safe_config_digest(env: Mapping[str, str]) -> str:
    safe_pairs = []
    for key, value in sorted(env.items()):
        if not key.startswith("SW_"):
            continue
        if any(marker in key.upper() for marker in SECRET_NAME_MARKERS):
            safe_pairs.append((key, "[REDACTED]"))
        else:
            safe_pairs.append((key, value))
    return _sha256_text(json.dumps(safe_pairs, ensure_ascii=True, separators=(",", ":")))


def _file_status(path: Path | None, *, now: float) -> dict[str, object]:
    if path is None:
        return {"status": "NOT_CONFIGURED", "path_present": False}
    resolved = path.expanduser().resolve()
    if not resolved.exists():
        return {"status": "NOT_PRESENT_UNVERIFIED", "path_present": False}
    if not resolved.is_file() and not resolved.is_dir():
        return {"status": "NOT_A_FILE_OR_DIRECTORY", "path_present": True}
    try:
        stat = resolved.stat()
        entry_count = len(list(resolved.iterdir())) if resolved.is_dir() else None
    except OSError:
        return {"status": "STAT_FAILED", "path_present": True}
    age_seconds = max(0.0, now - stat.st_mtime)
    result: dict[str, object] = {
        "status": "PRESENT",
        "path_present": True,
        "age_seconds": round(age_seconds, 3),
        "is_directory": resolved.is_dir(),
    }
    if resolved.is_file():
        result["size_bytes"] = stat.st_size
    if entry_count is not None:
        result["entry_count"] = entry_count
    return result


def _sqlite_status(path: Path | None) -> dict[str, object]:
    if path is None:
        return {"status": "NOT_CONFIGURED"}
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        return {"status": "NOT_PRESENT_UNVERIFIED"}
    try:
        with sqlite3.connect(f"file:{resolved}?mode=ro", uri=True) as connection:
            connection.execute("PRAGMA foreign_keys=ON")
            journal_mode = str(connection.execute("PRAGMA journal_mode").fetchone()[0]).lower()
            integrity = str(connection.execute("PRAGMA integrity_check").fetchone()[0]).lower()
            foreign_keys = int(connection.execute("PRAGMA foreign_keys").fetchone()[0])
            synchronous = int(connection.execute("PRAGMA synchronous").fetchone()[0])
    except (OSError, sqlite3.Error) as exc:
        return {"status": "READ_FAILED", "error_type": type(exc).__name__}
    return {
        "status": "PASS" if journal_mode == "wal" and integrity == "ok" and foreign_keys == 1 else "FAIL",
        "journal_mode": journal_mode,
        "integrity_check": integrity,
        "foreign_keys": foreign_keys,
        "synchronous": synchronous,
    }


def _disk_status(path: Path) -> dict[str, object]:
    try:
        usage = shutil.disk_usage(path)
    except OSError as exc:
        return {"status": "READ_FAILED", "error_type": type(exc).__name__}
    free_ratio = usage.free / usage.total if usage.total else 0.0
    return {
        "status": "PASS" if free_ratio >= 0.10 else "ADVISORY",
        "free_bytes": usage.free,
        "total_bytes": usage.total,
        "free_ratio": round(free_ratio, 6),
    }


def collect_operational_snapshot(
    env: Mapping[str, str],
    *,
    project_root: Path,
    database_path: Path | None = None,
    checkpoint_path: Path | None = None,
    audit_path: Path | None = None,
    anchor_path: Path | None = None,
    backup_path: Path | None = None,
    now: float | None = None,
) -> dict[str, object]:
    root = project_root.resolve()
    current_time = datetime.now(timezone.utc).timestamp() if now is None else now
    preflight = evaluate_internal_foundation(env, project_root=root)
    if database_path is None and env.get("SW_DATABASE_PATH"):
        database_path = Path(env["SW_DATABASE_PATH"])
    if checkpoint_path is None and env.get("SW_TELEMETRY_STATE_PATH"):
        checkpoint_path = Path(env["SW_TELEMETRY_STATE_PATH"])
    if audit_path is None and env.get("SW_AUDIT_LOG_PATH"):
        audit_path = Path(env["SW_AUDIT_LOG_PATH"])
    if anchor_path is None and env.get("SW_FORENSIC_ANCHOR_PATH"):
        anchor_path = Path(env["SW_FORENSIC_ANCHOR_PATH"])
    if backup_path is None and env.get("SW_BACKUP_BUNDLE_PATH"):
        backup_path = Path(env["SW_BACKUP_BUNDLE_PATH"])

    snapshot = {
        "schema_version": SCHEMA_VERSION,
        "snapshot_kind": "OPERATIONAL_STATUS",
        "evidence_class": "LOCAL_SOFTWARE_SNAPSHOT",
        "source_revision": _source_revision(root),
        "config_digest": _safe_config_digest(env),
        "preflight_status": preflight["status"],
        "software_only": True,
        "physical_validation": "UNVERIFIED",
        "clinical_validation": "PENDING",
        "runtime": {
            "database": _sqlite_status(database_path),
            "checkpoint": _file_status(checkpoint_path, now=current_time),
            "audit": _file_status(audit_path, now=current_time),
            "anchor": _file_status(anchor_path, now=current_time),
            "backup": _file_status(backup_path, now=current_time),
            "disk": _disk_status(root),
        },
        "rollback": {
            "source_revision_available": _source_revision(root) != "UNAVAILABLE",
            "rollback_command_required": True,
            "operator_confirmation_required": True,
        },
        "authorization_boundary": dict(AUTHORIZATION_BOUNDARY),
        "pilot_gate_status": AUTHORIZATION_BOUNDARY["pilot_gate_status"],
        "optional_metrics": collect_optional_metrics(env),
        "next_action": "Review FAIL/ADVISORY or NOT_PRESENT_UNVERIFIED components; reconcile before resuming runtime. Obtain physical and external evidence separately.",
    }
    snapshot["threshold_evaluation"] = evaluate_thresholds(
        snapshot,
        metrics=snapshot["optional_metrics"],
        thresholds=load_thresholds(env),
    )
    return snapshot


def main() -> int:
    parser = argparse.ArgumentParser(description="Export a redacted local Smart Ward Hub operational status snapshot")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    snapshot = collect_operational_snapshot(dict(os.environ), project_root=args.project_root.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(snapshot, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "snapshot_kind": snapshot["snapshot_kind"],
                "preflight_status": snapshot["preflight_status"],
                "evidence_class": snapshot["evidence_class"],
                "pilot_gate_status": snapshot["pilot_gate_status"],
                "output": str(args.output),
            },
            sort_keys=True,
        )
    )
    return 0 if snapshot["preflight_status"] != "FAIL" else 2


if __name__ == "__main__":
    raise SystemExit(main())
