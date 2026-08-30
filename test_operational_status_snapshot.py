from __future__ import annotations

from contextlib import closing
import json
from pathlib import Path
import sqlite3
import tempfile

from operational_status_snapshot import SCHEMA_VERSION, collect_operational_snapshot
from test_internal_foundation_readiness import valid_environment


ROOT = Path(__file__).resolve().parent


def _configure_environment(runtime_root: Path) -> dict[str, str]:
    env = valid_environment(ROOT)
    env.update(
        {
            "SW_DATABASE_PATH": str(runtime_root / "ward_hub.db"),
            "SW_TELEMETRY_STATE_PATH": str(runtime_root / "edge_telemetry_state.json"),
            "SW_AUDIT_LOG_PATH": str(runtime_root / "audit_events.jsonl"),
            "SW_FORENSIC_ANCHOR_PATH": str(runtime_root / "forensic_anchors.jsonl"),
            "SW_BACKUP_BUNDLE_PATH": str(runtime_root / "backup-bundle"),
            "SW_SYNC_BACKLOG": "0",
            "SW_WORKER_QUEUE_BACKLOG": "0",
            "SW_UNRESOLVED_ALERTS": "0",
            # Keep this host-dependent test deterministic without changing the 10% default.
            "SW_MIN_DISK_FREE_RATIO": "0.05",
        }
    )
    return env


def run() -> None:
    with tempfile.TemporaryDirectory() as directory:
        runtime_root = Path(directory)
        env = _configure_environment(runtime_root)
        snapshot = collect_operational_snapshot(env, project_root=ROOT, now=2_000_000_000)
        assert snapshot["schema_version"] == SCHEMA_VERSION
        assert snapshot["snapshot_kind"] == "OPERATIONAL_STATUS"
        assert snapshot["evidence_class"] == "LOCAL_SOFTWARE_SNAPSHOT"
        assert snapshot["preflight_status"] == "PASS"
        assert snapshot["software_only"] is True
        assert snapshot["physical_validation"] == "UNVERIFIED"
        assert snapshot["clinical_validation"] == "PENDING"
        assert snapshot["runtime"]["database"]["status"] == "NOT_PRESENT_UNVERIFIED"
        assert snapshot["runtime"]["backup"]["status"] == "NOT_PRESENT_UNVERIFIED"
        assert snapshot["threshold_evaluation"]["status"] == "BLOCKED_REQUIRES_RECONCILIATION"
        assert snapshot["threshold_evaluation"]["resume_permitted"] is False
        assert "DATABASE_NOT_VERIFIED" in snapshot["threshold_evaluation"]["remediation_codes"]
        redaction_env = dict(env)
        redaction_env["SW_AUTH_TOKENS_JSON"] = '{"secret-token":["admin"]}'
        redacted_snapshot = collect_operational_snapshot(redaction_env, project_root=ROOT, now=2_000_000_000)
        encoded = json.dumps(redacted_snapshot, ensure_ascii=True)
        assert "secret-token" not in encoded
        assert snapshot["authorization_boundary"]["external_authority"] == "NONE"
        assert snapshot["authorization_boundary"]["production_authorized"] is False
        print("[Operational] redaction, preflight and locked authorization boundary: PASSED")

        database = runtime_root / "ward_hub.db"
        with closing(sqlite3.connect(database)) as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("CREATE TABLE fixture (id INTEGER PRIMARY KEY, value TEXT NOT NULL)")
            connection.execute("INSERT INTO fixture(value) VALUES ('opaque')")
            connection.commit()
        checkpoint = runtime_root / "edge_telemetry_state.json"
        checkpoint.write_text('{"state_version":1,"buffers":{}}\n', encoding="utf-8")
        audit = runtime_root / "audit_events.jsonl"
        audit.write_text('{"event_type":"health","outcome":"success"}\n', encoding="utf-8")
        anchor = runtime_root / "forensic_anchors.jsonl"
        anchor.write_text('{"anchor_type":"local_append_only_adapter"}\n', encoding="utf-8")
        backup = runtime_root / "backup-bundle"
        backup.mkdir()
        (backup / "manifest.json").write_text('{"schema":"smart-ward-backup-manifest-v1"}\n', encoding="utf-8")

        snapshot = collect_operational_snapshot(env, project_root=ROOT, now=database.stat().st_mtime + 10)
        assert snapshot["preflight_status"] == "PASS"
        assert snapshot["runtime"]["database"]["status"] == "PASS"
        assert snapshot["runtime"]["database"]["journal_mode"] == "wal"
        assert snapshot["runtime"]["database"]["integrity_check"] == "ok"
        assert snapshot["runtime"]["database"]["foreign_keys"] == 1
        assert snapshot["runtime"]["checkpoint"]["status"] == "PRESENT"
        assert snapshot["runtime"]["audit"]["status"] == "PRESENT"
        assert snapshot["runtime"]["anchor"]["status"] == "PRESENT"
        assert snapshot["runtime"]["backup"]["status"] == "PRESENT"
        assert snapshot["threshold_evaluation"]["status"] == "PASS", snapshot["threshold_evaluation"]
        assert snapshot["threshold_evaluation"]["resume_permitted"] is True
        assert snapshot["threshold_evaluation"]["remediation_codes"] == []
        assert snapshot["rollback"]["source_revision_available"] is True
        print("[Operational] WAL, integrity, checkpoint/audit/anchor/backup status: PASSED")

        unsafe = dict(env)
        unsafe["SW_ALLOWED_HOSTS"] = "*"
        snapshot = collect_operational_snapshot(unsafe, project_root=ROOT)
        assert snapshot["preflight_status"] == "FAIL"
        assert snapshot["runtime"]["database"]["status"] == "PASS"
        print("[Operational] unsafe preflight remains FAIL despite healthy database: PASSED")

    print("OPERATIONAL_STATUS_SNAPSHOT_TESTS_PASSED")


if __name__ == "__main__":
    run()
