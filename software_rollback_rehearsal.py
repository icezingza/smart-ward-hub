from __future__ import annotations

import argparse
from contextlib import closing
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import tempfile
from typing import Any
from unittest.mock import patch

from backup_restore import RESTORE_CONFIRMATION, create_backup_bundle, restore_backup_bundle
from durable_worker_store import DurableWorkerStore
from edge_controls import AuditSink, FileAnchorStore, reset_request_id, set_request_id
from edge_runtime import EdgeTelemetryStore
from operational_thresholds import evaluate_thresholds
from worker_queue_backup import create_worker_queue_backup, restore_worker_queue_backup


SCHEMA_VERSION = "smart-ward-software-rollback-v1"
REHEARSAL_REVISION = "rollback-rehearsal-fixture-revision"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sample(sequence: int) -> dict[str, Any]:
    return {
        "sequence": sequence,
        "ppg": 72.0 + sequence,
        "accel_x": 0.0,
        "accel_y": 0.0,
        "accel_z": 1.0,
        "battery_pct": 88.0,
    }


def _seed_database(path: Path) -> None:
    with closing(sqlite3.connect(path)) as connection, connection:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA user_version=7")
        connection.execute("CREATE TABLE ward_state (id INTEGER PRIMARY KEY, opaque_state TEXT NOT NULL)")
        connection.execute("INSERT INTO ward_state(id, opaque_state) VALUES (1, 'baseline-state')")
        connection.commit()


def _seed_checkpoint(path: Path) -> None:
    store = EdgeTelemetryStore(max_samples=4, state_path=path, checkpoint_every=1)
    assert store.append("device-rehearsal", _sample(1), 1).accepted
    assert store.append("device-rehearsal", _sample(2), 2).accepted
    store.persist()


def _seed_audit(path: Path) -> None:
    token = set_request_id("rollback-rehearsal-request")
    try:
        sink = AuditSink(path)
        sink.record(
            "ROLLBACK_REHEARSAL_SEED",
            "SUCCESS",
            actor={"role": "reliability_operator", "subject": "opaque-operator"},
            resource_type="rehearsal",
            resource_id="rollback-rehearsal-001",
            details={"source_revision": REHEARSAL_REVISION, "patient_data_used": False},
        )
    finally:
        reset_request_id(token)


def _seed_anchor(path: Path, source_root: Path) -> dict[str, Any]:
    store = FileAnchorStore(path=path, source_root=source_root)
    receipt = store.anchor_with_receipt(block_hash="1" * 64, chain_tip="2" * 64, package_id=1)
    assert receipt is not None
    assert store.verify_receipt(receipt)
    return receipt


def _seed_worker(path: Path) -> None:
    store = DurableWorkerStore(str(path), lease_seconds=10)
    common = {
        "job_type": "BACKUP_REPORT",
        "args": {"report_kind": "daily", "format": "json", "scope_ref": "ward-04"},
        "requester_role": "reliability_operator",
        "approver_role": "security_auditor",
        "approval_ref": "rollback-approval-001",
    }
    store.submit(job_id="rollback-worker-001", idempotency_key="rollback-worker-idem-001", **common)
    store.submit(job_id="rollback-worker-stale", idempotency_key="rollback-worker-idem-stale", **common)
    claimed = store.claim(job_id="rollback-worker-stale", worker_id="worker-pre-restore")
    assert claimed["status"] == "RUNNING"
    assert store.health()["audit_chain_valid"] is True
    store.close()


def _verify_database(path: Path) -> dict[str, Any]:
    with closing(sqlite3.connect(f"file:{path}?mode=ro", uri=True)) as connection:
        integrity = str(connection.execute("PRAGMA integrity_check").fetchone()[0]).lower()
        value = connection.execute("SELECT opaque_state FROM ward_state WHERE id=1").fetchone()
        journal_mode = str(connection.execute("PRAGMA journal_mode").fetchone()[0]).lower()
        user_version = int(connection.execute("PRAGMA user_version").fetchone()[0])
    return {
        "integrity_check": integrity,
        "opaque_state_matches": value == ("baseline-state",),
        "journal_mode": journal_mode,
        "user_version": user_version,
        "schema_revision_matches": user_version == 7,
        "passed": integrity == "ok" and value == ("baseline-state",) and journal_mode == "wal" and user_version == 7,
    }


def _verify_checkpoint(path: Path) -> dict[str, Any]:
    store = EdgeTelemetryStore(max_samples=4, state_path=path, checkpoint_every=1)
    last_sequence = store.last_sequence("device-rehearsal")
    return {"last_sequence": last_sequence, "sequence_matches": last_sequence == 2, "passed": last_sequence == 2}


def _verify_audit(path: Path, expected_hash: str) -> dict[str, Any]:
    actual_hash = _sha256(path)
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    parsed = [json.loads(line) for line in lines]
    redacted = all("subject" not in item.get("actor", {}) and "subject_hash" in item.get("actor", {}) for item in parsed)
    return {
        "hash_matches_export": actual_hash == expected_hash,
        "line_count": len(parsed),
        "redaction_shape_valid": redacted,
        "passed": actual_hash == expected_hash and bool(parsed),
    }


def _verify_anchor(path: Path, receipt: dict[str, Any], source_root: Path) -> dict[str, Any]:
    store = FileAnchorStore(path=path, source_root=source_root)
    return {"receipt_readback_valid": store.verify_receipt(receipt), "passed": store.verify_receipt(receipt)}


def _verify_worker(path: Path) -> dict[str, Any]:
    store = DurableWorkerStore(str(path), lease_seconds=10)
    job = store.get("rollback-worker-001")
    stale_job = store.get("rollback-worker-stale")
    health = store.health()
    result = {
        "status": job["status"],
        "stale_status_before_reconciliation": stale_job["status"],
        "audit_chain_valid": health["audit_chain_valid"],
    }
    result["passed"] = job["status"] == "QUEUED" and stale_job["status"] == "RUNNING" and health["audit_chain_valid"] is True
    store.close()
    return result


def _recover_worker_stale_lease(path: Path) -> dict[str, Any]:
    store = DurableWorkerStore(str(path), lease_seconds=10)
    stale_job = store.get("rollback-worker-stale")
    assert stale_job["lease_expires_at"] is not None
    expired_at = datetime.fromisoformat(stale_job["lease_expires_at"]) + timedelta(seconds=1)
    blocked = store.recover_expired_leases(
        actor_role="control_room_coordinator",
        reconciliation_ref="rollback-stale-lease-001",
        now=expired_at,
    )
    assert blocked == ["rollback-worker-stale"]
    reconciled = store.reconcile(
        job_id="rollback-worker-stale",
        decision="FAIL",
        actor_role="control_room_coordinator",
        reconciliation_ref="rollback-stale-lease-002",
        now=expired_at,
    )
    result = {
        "blocked_jobs": blocked,
        "reconciled_status": reconciled["status"],
        "audit_chain_valid": store.health()["audit_chain_valid"],
    }
    result["passed"] = blocked == ["rollback-worker-stale"] and reconciled["status"] == "FAILED" and result["audit_chain_valid"] is True
    store.close()
    return result


def _probe_interrupted_checkpoint_promotion(bundle: Path, target_root: Path) -> dict[str, Any]:
    target_root.mkdir(parents=True, exist_ok=True)
    target_db = target_root / "interrupted.db"
    target_checkpoint = target_root / "interrupted-checkpoint.json"
    with closing(sqlite3.connect(target_db)) as connection, connection:
        connection.execute("CREATE TABLE ward_state (id INTEGER PRIMARY KEY, opaque_state TEXT NOT NULL)")
        connection.execute("INSERT INTO ward_state(id, opaque_state) VALUES (1, 'pre-restore-state')")
        connection.commit()
    target_checkpoint.write_text('{"state_version":1,"buffers":{"before":true}}\n', encoding="utf-8")
    original_db = _sha256(target_db)
    original_checkpoint = target_checkpoint.read_text(encoding="utf-8")
    try:
        with patch("backup_restore.shutil.copy2", side_effect=OSError("simulated interrupted checkpoint promotion")):
            restore_backup_bundle(
                bundle_dir=bundle,
                target_database=target_db,
                target_checkpoint=target_checkpoint,
                confirmation=RESTORE_CONFIRMATION,
            )
    except OSError as exc:
        assert str(exc) == "simulated interrupted checkpoint promotion"
    else:
        raise AssertionError("interrupted checkpoint promotion was accepted")
    with closing(sqlite3.connect(target_db)) as connection:
        preserved = connection.execute("SELECT opaque_state FROM ward_state WHERE id=1").fetchone() == ("pre-restore-state",)
    clean = not any(target_root.glob("interrupted*restore-tmp")) and not any(target_root.glob("interrupted*restore-prev"))
    return {
        "passed": preserved and _sha256(target_db) == original_db and target_checkpoint.read_text(encoding="utf-8") == original_checkpoint and clean,
        "resume_permitted": False,
        "recovery_decision": "RECONCILIATION_REQUIRED",
    }


def _probe_partial_audit_write(audit_path: Path, root: Path) -> dict[str, Any]:
    root.mkdir(parents=True, exist_ok=True)
    partial = root / "partial-audit.jsonl"
    shutil.copyfile(audit_path, partial)
    with partial.open("a", encoding="utf-8") as handle:
        handle.write('{"event_type":"PARTIAL')
    valid_lines = 0
    invalid_lines = 0
    for line in partial.read_text(encoding="utf-8").splitlines():
        try:
            json.loads(line)
            valid_lines += 1
        except json.JSONDecodeError:
            invalid_lines += 1
    return {
        "passed": valid_lines >= 1 and invalid_lines == 1,
        "partial_write_detected": invalid_lines == 1,
        "resume_permitted": False,
        "recovery_decision": "RECONCILIATION_REQUIRED",
    }


def _probe_backup_freshness_breach() -> dict[str, Any]:
    snapshot = {
        "preflight_status": "PASS",
        "runtime": {
            "database": {"status": "PASS"},
            "checkpoint": {"status": "PRESENT", "age_seconds": 10},
            "backup": {"status": "PRESENT", "age_seconds": 86_401},
            "audit": {"status": "PRESENT", "age_seconds": 10},
            "anchor": {"status": "PRESENT", "age_seconds": 10},
            "disk": {"status": "PASS", "free_ratio": 0.90},
        },
    }
    evaluated = evaluate_thresholds(snapshot, metrics={"sync_backlog": 0, "worker_queue_backlog": 0, "unresolved_alerts": 0})
    return {
        "passed": evaluated["status"] == "BLOCKED_REQUIRES_RECONCILIATION" and "BACKUP_STALE" in evaluated["remediation_codes"],
        "remediation_codes": evaluated["remediation_codes"],
        "resume_permitted": evaluated["resume_permitted"],
        "recovery_decision": "RECONCILIATION_REQUIRED",
    }


def _probe_schema_mismatch(database: Path, root: Path) -> dict[str, Any]:
    root.mkdir(parents=True, exist_ok=True)
    mismatch = root / "schema-mismatch.db"
    shutil.copy2(database, mismatch)
    with closing(sqlite3.connect(mismatch)) as connection, connection:
        connection.execute("PRAGMA user_version=8")
        connection.commit()
    verification = _verify_database(mismatch)
    return {
        "passed": verification["schema_revision_matches"] is False and verification["passed"] is False,
        "observed_user_version": verification["user_version"],
        "resume_permitted": False,
        "recovery_decision": "RECONCILIATION_REQUIRED",
    }


def run_rehearsal(output: Path | None = None) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="smart-ward-software-rollback-") as directory:
        root = Path(directory)
        source_root = root / "source"
        source_root.mkdir()
        source_db = source_root / "ward_hub.db"
        source_checkpoint = source_root / "edge_telemetry_state.json"
        source_audit = source_root / "audit_events.jsonl"
        source_anchor = root / "external-anchor.jsonl"
        source_forensic = source_root / "forensic_manifest.json"
        source_worker = source_root / "worker_queue.db"
        _seed_database(source_db)
        _seed_checkpoint(source_checkpoint)
        _seed_audit(source_audit)
        receipt = _seed_anchor(source_anchor, source_root)
        source_forensic.write_text(
            json.dumps(
                {
                    "schema": "rollback-forensic-fixture-v1",
                    "chain_tip": receipt["chain_tip"],
                    "anchor_id": receipt["anchor_id"],
                    "patient_data_used": False,
                    "raw_frames_recorded": False,
                },
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        _seed_worker(source_worker)
        audit_export = root / "audit-export.jsonl"
        shutil.copyfile(source_audit, audit_export)
        audit_export_hash = _sha256(audit_export)
        anchor_export = root / "anchor-export.jsonl"
        shutil.copyfile(source_anchor, anchor_export)
        anchor_export_hash = _sha256(anchor_export)

        main_bundle = create_backup_bundle(
            database_path=source_db,
            output_dir=root / "main-backups",
            checkpoint_path=source_checkpoint,
            forensic_manifest_path=source_forensic,
            source_revision=REHEARSAL_REVISION,
        )
        worker_bundle = create_worker_queue_backup(
            database_path=source_worker,
            output_dir=root / "worker-backups",
            source_revision=REHEARSAL_REVISION,
        )

        with closing(sqlite3.connect(source_db)) as connection, connection:
            connection.execute("UPDATE ward_state SET opaque_state='drifted-live-state' WHERE id=1")
            connection.commit()
        live_checkpoint = EdgeTelemetryStore(max_samples=4, state_path=source_checkpoint, checkpoint_every=1)
        assert live_checkpoint.append("device-rehearsal", _sample(3), 3).accepted
        token = set_request_id("rollback-drift-request")
        try:
            AuditSink(source_audit).record("LIVE_DRIFT_AFTER_BACKUP", "OBSERVED", actor={"role": "reliability_operator"}, details={"patient_data_used": False})
        finally:
            reset_request_id(token)
        with DurableWorkerStore(str(source_worker), lease_seconds=10) as live_worker:
            live_worker.claim(job_id="rollback-worker-001", worker_id="worker-drift")

        target_root = root / "rollback-target"
        target_root.mkdir()
        target_db = target_root / "ward_hub.db"
        target_checkpoint = target_root / "edge_telemetry_state.json"
        target_worker = target_root / "worker_queue.db"
        restored = restore_backup_bundle(
            bundle_dir=main_bundle,
            target_database=target_db,
            target_checkpoint=target_checkpoint,
            confirmation=RESTORE_CONFIRMATION,
        )
        worker_restored = restore_worker_queue_backup(
            bundle_dir=worker_bundle,
            target_database=target_worker,
            confirmation=RESTORE_CONFIRMATION,
        )
        shutil.copyfile(audit_export, target_root / "audit-export.jsonl")
        shutil.copyfile(anchor_export, target_root / "external-anchor.jsonl")
        checks = {
            "database": _verify_database(target_db),
            "checkpoint": _verify_checkpoint(target_checkpoint),
            "audit_export": _verify_audit(target_root / "audit-export.jsonl", audit_export_hash),
            "anchor": _verify_anchor(target_root / "external-anchor.jsonl", receipt, target_root / "source"),
            "anchor_export_hash_matches": _sha256(target_root / "external-anchor.jsonl") == anchor_export_hash,
            "worker_queue": _verify_worker(target_worker),
            "worker_stale_lease_recovery": _recover_worker_stale_lease(target_worker),
            "restore_status": restored["restore_status"] == "SOFTWARE_RESTORE_VERIFIED",
            "worker_restore_status": worker_restored["worker_queue_restore_status"] == "SOFTWARE_RESTORE_VERIFIED",
        }
        fault_injection_results = {
            "interrupted_checkpoint_promotion": _probe_interrupted_checkpoint_promotion(main_bundle, root / "fault-probes"),
            "partial_audit_write": _probe_partial_audit_write(source_audit, root / "fault-probes"),
            "backup_freshness_breach": _probe_backup_freshness_breach(),
            "schema_migration_mismatch": _probe_schema_mismatch(target_db, root / "fault-probes"),
        }
        checks["all_post_restore_checks_passed"] = all(
            item is True if isinstance(item, bool) else item.get("passed") is True
            for item in checks.values()
        )
        checks["resume_permitted_in_software_rehearsal"] = checks["all_post_restore_checks_passed"]
        checks["production_resume_permitted"] = False
        checks["external_resume_permitted"] = False

        report = {
            "schema_version": SCHEMA_VERSION,
            "rehearsal": "software_rollback_rehearsal",
            "mode": "isolated_nonproduction_targets",
            "evidence_class": "LOCAL_SOFTWARE_SIMULATION",
            "source_revision": REHEARSAL_REVISION,
            "drift_simulated_after_backup": True,
            "audit_exported_before_restore": True,
            "anchor_exported_before_restore": True,
            "checks": checks,
            "fault_injection_results": fault_injection_results,
            "decision": "ROLLBACK_VERIFIED_IN_ISOLATED_TARGET" if checks["all_post_restore_checks_passed"] else "ROLLBACK_BLOCKED_RECONCILIATION_REQUIRED",
            "patient_data_used": False,
            "raw_frames_recorded": False,
            "physical_power_cut": "UNVERIFIED",
            "target_host_validation": "UNVERIFIED",
            "external_authority": "NONE",
            "clinical_validation_authorized": False,
            "production_authorized": False,
            "pilot_gate_status": "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION",
        }
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Run isolated software rollback rehearsal")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    report = run_rehearsal(args.output)
    print(json.dumps(report, ensure_ascii=True, sort_keys=True))
    print("SOFTWARE_ROLLBACK_REHEARSAL_PASSED" if report["decision"] == "ROLLBACK_VERIFIED_IN_ISOLATED_TARGET" else "SOFTWARE_ROLLBACK_REHEARSAL_BLOCKED")
    return 0 if report["decision"] == "ROLLBACK_VERIFIED_IN_ISOLATED_TARGET" else 1


if __name__ == "__main__":
    raise SystemExit(main())
