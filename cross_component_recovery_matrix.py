from __future__ import annotations

from contextlib import closing
import argparse
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
from typing import Any, Callable
from unittest.mock import patch

from backup_restore import BackupRestoreError, create_backup_bundle, restore_backup_bundle
from durable_worker_store import DurableWorkerStore
from edge_controls import FileAnchorStore
from edge_runtime import EdgeTelemetryStore
from worker_queue_backup import WorkerQueueBackupError, create_worker_queue_backup, restore_worker_queue_backup


SCHEMA_VERSION = "smart-ward-recovery-matrix-v1"
RESTORE_CONFIRMATION = "I_UNDERSTAND_RESTORE_TO_NONPRODUCTION_TARGET"


def _sample(sequence: int) -> dict[str, Any]:
    return {
        "sequence": sequence,
        "ppg": 70.0 + sequence,
        "accel_x": 0.0,
        "accel_y": 0.0,
        "accel_z": 1.0,
        "battery_pct": 90.0,
    }


def _create_database(path: Path) -> None:
    with closing(sqlite3.connect(path)) as connection:
        connection.execute("CREATE TABLE recovery_fixture (id INTEGER PRIMARY KEY, value TEXT NOT NULL)")
        connection.execute("INSERT INTO recovery_fixture(value) VALUES (?)", ("opaque-recovery-fixture",))
        connection.commit()


def _create_checkpoint(path: Path) -> None:
    store = EdgeTelemetryStore(max_samples=4, state_path=path, checkpoint_every=1)
    assert store.append("device-recovery", _sample(1), 1).accepted
    assert store.append("device-recovery", _sample(2), 2).accepted
    store.persist()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class FixedClock:
    def __init__(self) -> None:
        self.value = datetime(2026, 8, 22, 12, 0, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.value

    def advance(self, seconds: int) -> None:
        self.value += timedelta(seconds=seconds)


def _submit_worker(store: DurableWorkerStore, job_id: str, idempotency_key: str) -> dict[str, Any]:
    return store.submit(
        job_id=job_id,
        job_type="BACKUP_REPORT",
        args={"report_kind": "daily", "format": "json", "scope_ref": "ward-04"},
        idempotency_key=idempotency_key,
        requester_role="reliability_operator",
        approver_role="security_auditor",
        approval_ref="approval-ref-001",
        max_attempts=3,
    )


def _create_forensic_manifest(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "schema": "local-forensic-fixture-v1",
                "chain_tip": "a" * 64,
                "patient_data_used": False,
                "raw_frames_recorded": False,
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def _create_bundle(root: Path, name: str) -> Path:
    source_db = root / f"{name}-source.sqlite3"
    checkpoint = root / f"{name}-checkpoint.json"
    forensic = root / f"{name}-forensic.json"
    _create_database(source_db)
    _create_checkpoint(checkpoint)
    _create_forensic_manifest(forensic)
    return create_backup_bundle(
        database_path=source_db,
        output_dir=root / f"{name}-backups",
        checkpoint_path=checkpoint,
        forensic_manifest_path=forensic,
        source_revision="recovery-matrix-fixture-revision",
    )


def _case_backup_restore_roundtrip(root: Path) -> dict[str, Any]:
    bundle = _create_bundle(root, "roundtrip")
    target_db = root / "roundtrip-restored.sqlite3"
    target_checkpoint = root / "roundtrip-restored-checkpoint.json"
    result = restore_backup_bundle(
        bundle_dir=bundle,
        target_database=target_db,
        target_checkpoint=target_checkpoint,
        confirmation=RESTORE_CONFIRMATION,
    )
    with closing(sqlite3.connect(target_db)) as connection:
        row = connection.execute("SELECT value FROM recovery_fixture WHERE id=1").fetchone()
    recovered = EdgeTelemetryStore(max_samples=4, state_path=target_checkpoint, checkpoint_every=1)
    assert row == ("opaque-recovery-fixture",)
    assert recovered.last_sequence("device-recovery") == 2
    assert result["restore_status"] == "SOFTWARE_RESTORE_VERIFIED"
    return {
        "scenario": "backup_restore_roundtrip",
        "status": "PASS",
        "normal_resume_after_integrity_checks": True,
        "physical_validation": "UNVERIFIED",
    }


def _case_database_tamper_fails_closed(root: Path) -> dict[str, Any]:
    bundle = _create_bundle(root, "database-tamper")
    database_artifact = bundle / "database.sqlite3"
    database_artifact.write_bytes(database_artifact.read_bytes() + b"tamper")
    target = root / "database-tamper-target.sqlite3"
    try:
        restore_backup_bundle(
            bundle_dir=bundle,
            target_database=target,
            confirmation=RESTORE_CONFIRMATION,
        )
    except BackupRestoreError as exc:
        assert str(exc) in {"artifact_size_failed:database.sqlite3", "artifact_checksum_failed:database.sqlite3"}
    else:
        raise AssertionError("tampered database artifact was restored")
    assert not target.exists()
    return {"scenario": "database_tamper_fails_closed", "status": "PASS", "recovery_decision": "RECONCILIATION_REQUIRED"}


def _case_checkpoint_tamper_fails_closed(root: Path) -> dict[str, Any]:
    bundle = _create_bundle(root, "checkpoint-tamper")
    checkpoint_artifact = next(path for path in bundle.iterdir() if path.name.endswith("-checkpoint.json"))
    checkpoint_artifact.write_text(checkpoint_artifact.read_text(encoding="utf-8") + "tamper", encoding="utf-8")
    target_db = root / "checkpoint-tamper-target.sqlite3"
    target_checkpoint = root / "checkpoint-tamper-target.json"
    try:
        restore_backup_bundle(
            bundle_dir=bundle,
            target_database=target_db,
            target_checkpoint=target_checkpoint,
            confirmation=RESTORE_CONFIRMATION,
        )
    except BackupRestoreError as exc:
        assert str(exc).startswith(("artifact_size_failed:", "artifact_checksum_failed:"))
    else:
        raise AssertionError("tampered checkpoint artifact was restored")
    assert not target_checkpoint.exists()
    return {"scenario": "checkpoint_tamper_fails_closed", "status": "PASS", "recovery_decision": "RECONCILIATION_REQUIRED"}


def _case_anchor_tamper_requires_reconciliation(root: Path) -> dict[str, Any]:
    anchor_path = root / "anchor.jsonl"
    store = FileAnchorStore(path=anchor_path, source_root=root / "source")
    receipt = store.anchor_with_receipt(block_hash="b" * 64, chain_tip="c" * 64, package_id=1)
    assert receipt is not None
    tampered = deepcopy(receipt)
    tampered["chain_tip"] = "d" * 64
    anchor_path.write_text(json.dumps(tampered, sort_keys=True) + "\n", encoding="utf-8")
    assert store.read_records() == []
    assert store.verify_receipt(receipt) is False
    return {"scenario": "anchor_tamper_requires_reconciliation", "status": "PASS", "recovery_decision": "RECONCILIATION_REQUIRED"}


def _case_checkpoint_corruption_isolated(root: Path) -> dict[str, Any]:
    checkpoint = root / "corrupt-checkpoint.json"
    checkpoint.write_text('{"state_version":1,"buffers":', encoding="utf-8")
    recovered = EdgeTelemetryStore(max_samples=4, state_path=checkpoint, checkpoint_every=1)
    assert recovered.stats()["buffered_samples"] == 0
    assert recovered.last_sequence("device-recovery") is None
    return {"scenario": "checkpoint_corruption_isolated", "status": "PASS", "recovery_decision": "RECONCILIATION_REQUIRED"}


def _case_combined_faults_block_resume(root: Path) -> dict[str, Any]:
    bundle = _create_bundle(root, "combined")
    (bundle / "database.sqlite3").write_bytes((bundle / "database.sqlite3").read_bytes() + b"tamper")
    anchor_path = root / "combined-anchor.jsonl"
    anchor = FileAnchorStore(path=anchor_path, source_root=root / "source")
    receipt = anchor.anchor_with_receipt(block_hash="e" * 64, chain_tip="f" * 64, package_id=2)
    assert receipt is not None
    anchor_path.write_text(anchor_path.read_text(encoding="utf-8").replace("\"chain_tip\":\"" + "f" * 64, "\"chain_tip\":\"" + "0" * 64), encoding="utf-8")
    assert anchor.verify_receipt(receipt) is False
    try:
        restore_backup_bundle(
            bundle_dir=bundle,
            target_database=root / "combined-target.sqlite3",
            confirmation=RESTORE_CONFIRMATION,
        )
    except BackupRestoreError:
        restore_failed = True
    else:
        restore_failed = False
    assert restore_failed
    return {
        "scenario": "combined_faults_block_resume",
        "status": "PASS",
        "resume_permitted": False,
        "recovery_decision": "RECONCILIATION_REQUIRED",
    }


def _case_worker_restart_stale_lease_reconcile(root: Path) -> dict[str, Any]:
    clock = FixedClock()
    database = root / "worker-restart.db"
    store = DurableWorkerStore(str(database), lease_seconds=10, clock=clock)
    first = _submit_worker(store, "worker-recovery-001", "worker-idem-001")
    store.close()

    reopened = DurableWorkerStore(str(database), lease_seconds=10, clock=clock)
    replay = _submit_worker(reopened, "worker-recovery-001", "worker-idem-001")
    assert replay["fingerprint"] == first["fingerprint"]
    claimed = reopened.claim(job_id="worker-recovery-001", worker_id="worker-a", now=clock())
    assert claimed["status"] == "RUNNING"
    clock.advance(11)
    blocked = reopened.recover_expired_leases(
        actor_role="control_room_coordinator",
        reconciliation_ref="worker-reconcile-001",
        now=clock(),
    )
    assert blocked == ["worker-recovery-001"]
    reopened.close()

    restarted = DurableWorkerStore(str(database), lease_seconds=10, clock=clock)
    assert restarted.get("worker-recovery-001")["status"] == "BLOCKED"
    failed = restarted.reconcile(
        job_id="worker-recovery-001",
        decision="FAIL",
        actor_role="control_room_coordinator",
        reconciliation_ref="worker-reconcile-002",
        now=clock(),
    )
    assert failed["status"] == "FAILED"
    assert restarted.health()["audit_chain_valid"] is True
    restarted.close()
    return {
        "scenario": "worker_restart_stale_lease_reconcile",
        "status": "PASS",
        "recovery_decision": "RECONCILIATION_REQUIRED",
        "idempotency_replay_preserved": True,
    }


def _case_worker_audit_corruption_fails_closed(root: Path) -> dict[str, Any]:
    database = root / "worker-audit-corrupt.db"
    store = DurableWorkerStore(str(database), clock=FixedClock())
    _submit_worker(store, "worker-audit-001", "worker-audit-idem-001")
    store.close()
    with closing(sqlite3.connect(database)) as connection:
        connection.execute("UPDATE worker_audit SET details_json = '{broken' WHERE event_seq = 1")
        connection.commit()
    reopened = DurableWorkerStore(str(database), clock=FixedClock())
    assert reopened.verify_audit_chain() is False
    assert reopened.health()["audit_chain_valid"] is False
    reopened.close()
    return {"scenario": "worker_audit_corruption_fails_closed", "status": "PASS", "recovery_decision": "RECONCILIATION_REQUIRED"}


def _case_worker_queue_schema_binding_mismatch(root: Path) -> dict[str, Any]:
    database = root / "worker-queue.db"
    store = DurableWorkerStore(str(database), clock=FixedClock())
    _submit_worker(store, "worker-queue-001", "worker-queue-idem-001")
    store.close()
    bundle = create_worker_queue_backup(database_path=database, output_dir=root / "worker-queue-backups", source_revision="worker-queue-revision")
    binding_path = bundle / "worker_queue_binding.json"
    original = binding_path.read_text(encoding="utf-8")
    binding = json.loads(original)
    binding["store_schema_version"] = "unknown-worker-schema"
    binding_path.write_text(json.dumps(binding, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    try:
        restore_worker_queue_backup(
            bundle_dir=bundle,
            target_database=root / "worker-queue-restored.db",
            confirmation=RESTORE_CONFIRMATION,
        )
    except WorkerQueueBackupError as exc:
        assert str(exc) in {"worker_queue_binding_store_schema_invalid", "worker_queue_binding_checksum_failed"}
    else:
        raise AssertionError("schema-mismatched worker queue was restored")
    binding_path.write_text(original, encoding="utf-8")
    return {"scenario": "worker_queue_schema_binding_mismatch", "status": "PASS", "recovery_decision": "RECONCILIATION_REQUIRED"}


def _case_wal_busy_locked_fails_closed(root: Path) -> dict[str, Any]:
    database = root / "wal-busy.db"
    with closing(sqlite3.connect(database, timeout=1.0)) as owner:
        owner.execute("PRAGMA journal_mode=WAL")
        owner.execute("CREATE TABLE lock_fixture (id INTEGER PRIMARY KEY, value TEXT)")
        owner.commit()
        owner.execute("BEGIN IMMEDIATE")
        owner.execute("INSERT INTO lock_fixture(value) VALUES ('owner')")
        with closing(sqlite3.connect(database, timeout=0.05)) as contender:
            contender.execute("PRAGMA busy_timeout=50")
            try:
                contender.execute("INSERT INTO lock_fixture(value) VALUES ('contender')")
                contender.commit()
            except sqlite3.OperationalError as exc:
                assert "locked" in str(exc).lower()
            else:
                raise AssertionError("contender write bypassed WAL lock boundary")
        owner.rollback()
    return {"scenario": "wal_busy_locked_fails_closed", "status": "PASS", "recovery_decision": "RECONCILIATION_REQUIRED"}


def _case_checkpoint_disk_full_rolls_back(root: Path) -> dict[str, Any]:
    checkpoint = root / "disk-full-checkpoint.json"
    store = EdgeTelemetryStore(max_samples=4, state_path=checkpoint, checkpoint_every=1)
    with patch.object(store, "_persist_locked", side_effect=OSError(28, "simulated disk full")):
        result = store.append("device-disk-full", _sample(1), 1)
    assert result.accepted is False
    assert result.reason == "checkpoint_persist_failed"
    assert store.snapshot("device-disk-full") == []
    assert store.last_sequence("device-disk-full") is None
    return {"scenario": "checkpoint_disk_full_rolls_back", "status": "PASS", "recovery_decision": "RECONCILIATION_REQUIRED"}


def run_matrix(output: Path | None = None) -> dict[str, Any]:
    cases: tuple[Callable[[Path], dict[str, Any]], ...] = (
        _case_backup_restore_roundtrip,
        _case_database_tamper_fails_closed,
        _case_checkpoint_tamper_fails_closed,
        _case_anchor_tamper_requires_reconciliation,
        _case_checkpoint_corruption_isolated,
        _case_combined_faults_block_resume,
        _case_worker_restart_stale_lease_reconcile,
        _case_worker_audit_corruption_fails_closed,
        _case_worker_queue_schema_binding_mismatch,
        _case_wal_busy_locked_fails_closed,
        _case_checkpoint_disk_full_rolls_back,
    )
    with tempfile.TemporaryDirectory(prefix="smart-ward-recovery-matrix-") as directory:
        root = Path(directory)
        results = [case(root) for case in cases]
    report = {
        "schema_version": SCHEMA_VERSION,
        "suite": "smart-ward-cross-component-recovery-matrix",
        "mode": "software_fault_injection",
        "evidence_class": "LOCAL_SOFTWARE_SIMULATION",
        "results": results,
        "scenario_count": len(results),
        "component_coverage": ["sqlite_wal", "telemetry_checkpoint", "backup_restore", "forensic_anchor", "durable_worker", "worker_queue_backup", "audit_chain"],
        "all_passed": all(item["status"] == "PASS" for item in results),
        "normal_resume_after_verified_roundtrip": next(item for item in results if item["scenario"] == "backup_restore_roundtrip")["normal_resume_after_integrity_checks"],
        "resume_permitted_after_unresolved_fault": False,
        "recovery_decision_on_unverified_component": "RECONCILIATION_REQUIRED",
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
    parser = argparse.ArgumentParser(description="Run safe cross-component Edge recovery fault scenarios")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    report = run_matrix(args.output)
    print(json.dumps(report, ensure_ascii=True, sort_keys=True))
    print("CROSS_COMPONENT_RECOVERY_MATRIX_PASSED")
    return 0 if report["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
