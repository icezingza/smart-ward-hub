from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
import logging
import re
import sqlite3
from threading import RLock
from typing import Any, Callable

logger = logging.getLogger(__name__)


class DurableWorkerStoreError(ValueError):
    pass


class DurableWorkerPolicyError(DurableWorkerStoreError):
    pass


class DurableWorkerStateError(DurableWorkerStoreError):
    pass


class DurableWorkerIdempotencyConflict(DurableWorkerStoreError):
    pass


JOB_TYPES = {"BACKUP_REPORT", "EVIDENCE_REPORT"}
ALLOWED_ROLES = {"reliability_operator", "control_room_coordinator", "security_auditor"}
RECOVERY_ROLES = {"reliability_operator", "control_room_coordinator"}
SAFE_ARGUMENT_KEYS = {"report_kind", "format", "scope_ref"}
MAX_ATTEMPTS = 3
MAX_LEASE_SECONDS = 300
OPAQUE_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{2,127}")
FORBIDDEN_MARKERS = re.compile(
    r"(?i)(patient[_ -]?id|patient[_ -]?token|patient[_ -]?name|hospital[_ -]?number|\bhn\b|\bmrn\b|national[_ -]?id|bearer|private[_ -]?key|secret|password|api[_ -]?key)"
)


class DurableWorkerStore:
    """SQLite-backed software fixture for durable worker-control semantics.

    This class is deliberately limited to ``mode='software_fixture'``. It
    proves local transactional/restart behavior with SQLite WAL and FULL
    synchronous mode, but it does not claim encryption-at-rest, backup custody,
    distributed locking, production scheduling, external delivery, or clinical
    authorization.
    """

    SCHEMA_VERSION = "p2-005-durable-worker-v1"

    def __init__(
        self,
        db_path: str,
        *,
        mode: str = "software_fixture",
        lease_seconds: int = 60,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if mode != "software_fixture":
            raise DurableWorkerPolicyError("production durable mode is not implemented or approved")
        if isinstance(lease_seconds, bool) or not isinstance(lease_seconds, int) or not 0 < lease_seconds <= MAX_LEASE_SECONDS:
            raise DurableWorkerPolicyError("lease_seconds out of bounded range")
        self.db_path = db_path
        self.lease_seconds = lease_seconds
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._lock = RLock()
        self._connection = sqlite3.connect(db_path, timeout=5.0, isolation_level=None, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._configure()
        self._initialize_schema()

    def _configure(self) -> None:
        connection = self._connection
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA synchronous=FULL")
        journal_mode = str(connection.execute("PRAGMA journal_mode=WAL").fetchone()[0]).lower()
        if journal_mode != "wal":
            raise DurableWorkerPolicyError("SQLite WAL mode is required")
        synchronous = connection.execute("PRAGMA synchronous").fetchone()[0]
        if int(synchronous) != 2:
            raise DurableWorkerPolicyError("SQLite synchronous=FULL is required")

    def _initialize_schema(self) -> None:
        with self._lock:
            self._connection.executescript(
                """
                    CREATE TABLE IF NOT EXISTS worker_store_meta (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS worker_jobs (
                        job_id TEXT PRIMARY KEY,
                        job_type TEXT NOT NULL,
                        args_json TEXT NOT NULL,
                        idempotency_key TEXT NOT NULL UNIQUE,
                        fingerprint TEXT NOT NULL,
                        requester_role TEXT NOT NULL,
                        approver_role TEXT NOT NULL,
                        approval_ref TEXT NOT NULL,
                        max_attempts INTEGER NOT NULL,
                        attempt_count INTEGER NOT NULL,
                        status TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        lease_owner TEXT,
                        lease_expires_at TEXT,
                        last_error TEXT,
                        result_json TEXT
                    );
                    CREATE TABLE IF NOT EXISTS worker_audit (
                        event_seq INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        actor_role TEXT NOT NULL,
                        action TEXT NOT NULL,
                        job_id TEXT NOT NULL,
                        result TEXT NOT NULL,
                        details_json TEXT NOT NULL,
                        previous_event_hash TEXT,
                        event_hash TEXT NOT NULL UNIQUE
                    );
                    INSERT INTO worker_store_meta(key, value)
                    VALUES ('schema_version', 'p2-005-durable-worker-v1')
                    ON CONFLICT(key) DO UPDATE SET value=excluded.value;
                """
            )

    @staticmethod
    def _now(value: datetime | None, clock: Callable[[], datetime]) -> datetime:
        current = value if value is not None else clock()
        if not isinstance(current, datetime) or current.tzinfo is None or current.utcoffset() is None:
            raise DurableWorkerStoreError("timestamp must be timezone-aware")
        return current.astimezone(timezone.utc)

    @staticmethod
    def _iso(value: datetime) -> str:
        return value.astimezone(timezone.utc).isoformat()

    @classmethod
    def _opaque(cls, value: Any, field: str) -> str:
        if not isinstance(value, str) or not OPAQUE_RE.fullmatch(value) or FORBIDDEN_MARKERS.search(value):
            raise DurableWorkerStoreError(f"{field} must be opaque")
        return value

    @classmethod
    def _safe_json(cls, value: Any, *, field: str, depth: int = 0) -> None:
        if depth > 5:
            raise DurableWorkerStoreError(f"{field} exceeds bounded nesting")
        if value is None or isinstance(value, (bool, int, float)):
            return
        if isinstance(value, str):
            if FORBIDDEN_MARKERS.search(value):
                raise DurableWorkerStoreError(f"{field} contains forbidden marker")
            return
        if isinstance(value, list):
            if len(value) > 32:
                raise DurableWorkerStoreError(f"{field} exceeds bounded list size")
            for item in value:
                cls._safe_json(item, field=field, depth=depth + 1)
            return
        if isinstance(value, dict):
            if len(value) > 32:
                raise DurableWorkerStoreError(f"{field} exceeds bounded object size")
            for key, item in value.items():
                if not isinstance(key, str) or FORBIDDEN_MARKERS.search(key):
                    raise DurableWorkerStoreError(f"{field} contains unsafe key")
                cls._safe_json(item, field=field, depth=depth + 1)
            return
        raise DurableWorkerStoreError(f"{field} contains unsupported value type")

    @classmethod
    def _fingerprint(cls, payload: dict[str, Any]) -> str:
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def _audit(self, *, actor_role: str, action: str, job_id: str, result: str, now: datetime, details: dict[str, Any] | None = None) -> None:
        previous = self._connection.execute(
            "SELECT event_hash FROM worker_audit ORDER BY event_seq DESC LIMIT 1"
        ).fetchone()
        previous_hash = previous[0] if previous else None
        next_seq = self._connection.execute("SELECT COALESCE(MAX(event_seq), 0) + 1 FROM worker_audit").fetchone()[0]
        payload = {
            "event_seq": int(next_seq),
            "timestamp": self._iso(now),
            "actor_role": actor_role,
            "action": action,
            "job_id": job_id,
            "result": result,
            "details": details or {},
            "previous_event_hash": previous_hash,
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
        event_hash = hashlib.sha256(encoded).hexdigest()
        self._connection.execute(
            """
            INSERT INTO worker_audit(event_seq, timestamp, actor_role, action, job_id, result, details_json, previous_event_hash, event_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload["event_seq"],
                payload["timestamp"],
                payload["actor_role"],
                payload["action"],
                payload["job_id"],
                payload["result"],
                json.dumps(payload["details"], sort_keys=True, separators=(",", ":"), ensure_ascii=True),
                previous_hash,
                event_hash,
            ),
        )

    @staticmethod
    def _row_to_job(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "job_id": row["job_id"],
            "job_type": row["job_type"],
            "args": json.loads(row["args_json"]),
            "idempotency_key": row["idempotency_key"],
            "fingerprint": row["fingerprint"],
            "requester_role": row["requester_role"],
            "approver_role": row["approver_role"],
            "approval_ref": row["approval_ref"],
            "max_attempts": int(row["max_attempts"]),
            "attempts": int(row["attempt_count"]),
            "status": row["status"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "lease_owner": row["lease_owner"],
            "lease_expires_at": row["lease_expires_at"],
            "last_error": row["last_error"],
            "result": json.loads(row["result_json"]) if row["result_json"] is not None else None,
        }

    def _fetch(self, job_id: str) -> sqlite3.Row:
        row = self._connection.execute("SELECT * FROM worker_jobs WHERE job_id = ?", (job_id,)).fetchone()
        if row is None:
            raise DurableWorkerStateError("unknown job")
        return row

    def submit(
        self,
        *,
        job_id: str,
        job_type: str,
        args: dict[str, Any],
        idempotency_key: str,
        requester_role: str,
        approver_role: str,
        approval_ref: str,
        max_attempts: int = 3,
        external_side_effects_allowed: bool = False,
        clinical_state_mutation: bool = False,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        current = self._now(now, self._clock)
        job_id = self._opaque(job_id, "job_id")
        idempotency_key = self._opaque(idempotency_key, "idempotency_key")
        approval_ref = self._opaque(approval_ref, "approval_ref")
        if job_type not in JOB_TYPES:
            raise DurableWorkerStoreError("job_type is not allowlisted")
        if not isinstance(args, dict) or set(args) - SAFE_ARGUMENT_KEYS:
            raise DurableWorkerStoreError("args contain unknown fields")
        self._safe_json(args, field="args")
        if requester_role not in ALLOWED_ROLES or approver_role not in ALLOWED_ROLES:
            raise DurableWorkerStoreError("role is not allowlisted")
        if requester_role == approver_role:
            raise DurableWorkerStoreError("requester and approver must be distinct")
        if isinstance(max_attempts, bool) or not isinstance(max_attempts, int) or not 1 <= max_attempts <= MAX_ATTEMPTS:
            raise DurableWorkerStoreError("max_attempts out of bounded range")
        if external_side_effects_allowed or clinical_state_mutation:
            raise DurableWorkerStoreError("job crosses forbidden boundary")
        payload = {
            "job_id": job_id,
            "job_type": job_type,
            "args": args,
            "idempotency_key": idempotency_key,
            "requester_role": requester_role,
            "approver_role": approver_role,
            "approval_ref": approval_ref,
            "max_attempts": max_attempts,
        }
        fingerprint = self._fingerprint(payload)
        with self._lock:
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                existing = self._connection.execute(
                    "SELECT * FROM worker_jobs WHERE idempotency_key = ?", (idempotency_key,)
                ).fetchone()
                if existing is not None:
                    if existing["fingerprint"] != fingerprint:
                        raise DurableWorkerIdempotencyConflict("idempotency key conflict")
                    self._connection.execute("COMMIT")
                    return self._row_to_job(existing)
                if self._connection.execute("SELECT 1 FROM worker_jobs WHERE job_id = ?", (job_id,)).fetchone() is not None:
                    raise DurableWorkerIdempotencyConflict("job_id conflict")
                timestamp = self._iso(current)
                self._connection.execute(
                    """
                    INSERT INTO worker_jobs(job_id, job_type, args_json, idempotency_key, fingerprint, requester_role, approver_role, approval_ref, max_attempts, attempt_count, status, created_at, updated_at, lease_owner, lease_expires_at, last_error, result_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 'QUEUED', ?, ?, NULL, NULL, NULL, NULL)
                    """,
                    (job_id, job_type, json.dumps(args, sort_keys=True, separators=(",", ":"), ensure_ascii=True), idempotency_key, fingerprint, requester_role, approver_role, approval_ref, max_attempts, timestamp, timestamp),
                )
                self._audit(actor_role=requester_role, action="SUBMIT", job_id=job_id, result="QUEUED", now=current)
                row = self._fetch(job_id)
                self._connection.execute("COMMIT")
                return self._row_to_job(row)
            except Exception as exc:
                logger.warning("Failed to submit worker job %s: %s", job_id, exc, exc_info=True)
                self._connection.execute("ROLLBACK")
                raise

    def claim(self, *, job_id: str, worker_id: str, now: datetime | None = None) -> dict[str, Any]:
        current = self._now(now, self._clock)
        worker_id = self._opaque(worker_id, "worker_id")
        with self._lock:
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                row = self._fetch(job_id)
                if row["status"] != "QUEUED":
                    raise DurableWorkerStateError("job is not claimable")
                expires = self._iso(current + timedelta(seconds=self.lease_seconds))
                self._connection.execute(
                    "UPDATE worker_jobs SET status='RUNNING', attempt_count=attempt_count+1, updated_at=?, lease_owner=?, lease_expires_at=? WHERE job_id=? AND status='QUEUED'",
                    (self._iso(current), worker_id, expires, job_id),
                )
                self._audit(actor_role="worker", action="CLAIM", job_id=job_id, result="RUNNING", now=current, details={"worker_id": worker_id})
                result = self._row_to_job(self._fetch(job_id))
                self._connection.execute("COMMIT")
                return result
            except Exception as exc:
                logger.warning("Failed to claim worker job %s: %s", job_id, exc, exc_info=True)
                self._connection.execute("ROLLBACK")
                raise

    def _require_active_lease(self, row: sqlite3.Row, *, worker_id: str, current: datetime) -> None:
        if row["status"] != "RUNNING" or row["lease_owner"] != worker_id:
            raise DurableWorkerStateError("worker does not own an active lease")
        if row["lease_expires_at"] is None:
            raise DurableWorkerStateError("running job has no lease")
        if datetime.fromisoformat(row["lease_expires_at"]) <= current:
            raise DurableWorkerStateError("lease expired; reconciliation required")

    def complete(self, *, job_id: str, worker_id: str, result: dict[str, Any], now: datetime | None = None) -> dict[str, Any]:
        current = self._now(now, self._clock)
        worker_id = self._opaque(worker_id, "worker_id")
        if not isinstance(result, dict):
            raise DurableWorkerStoreError("result must be an object")
        self._safe_json(result, field="result")
        with self._lock:
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                row = self._fetch(job_id)
                if row["status"] == "RUNNING" and row["lease_expires_at"] and datetime.fromisoformat(row["lease_expires_at"]) <= current:
                    self._connection.execute("UPDATE worker_jobs SET status='BLOCKED', updated_at=?, lease_owner=NULL, lease_expires_at=NULL, last_error='LEASE_EXPIRED_REQUIRES_RECONCILIATION' WHERE job_id=?", (self._iso(current), job_id))
                    self._audit(actor_role="worker", action="LEASE_EXPIRED", job_id=job_id, result="BLOCKED", now=current)
                    self._connection.execute("COMMIT")
                    raise DurableWorkerStateError("lease expired; reconciliation required")
                self._require_active_lease(row, worker_id=worker_id, current=current)
                self._connection.execute("UPDATE worker_jobs SET status='SUCCEEDED', updated_at=?, lease_owner=NULL, lease_expires_at=NULL, result_json=?, last_error=NULL WHERE job_id=?", (self._iso(current), json.dumps(result, sort_keys=True, separators=(",", ":"), ensure_ascii=True), job_id))
                self._audit(actor_role="worker", action="COMPLETE", job_id=job_id, result="SUCCEEDED", now=current)
                result_row = self._row_to_job(self._fetch(job_id))
                self._connection.execute("COMMIT")
                return result_row
            except Exception as exc:
                logger.warning("Failed to complete worker job %s: %s", job_id, exc, exc_info=True)
                try:
                    self._connection.execute("ROLLBACK")
                except sqlite3.OperationalError:
                    pass
                raise

    def fail(self, *, job_id: str, worker_id: str, retryable: bool, now: datetime | None = None) -> dict[str, Any]:
        current = self._now(now, self._clock)
        worker_id = self._opaque(worker_id, "worker_id")
        if not isinstance(retryable, bool):
            raise DurableWorkerStoreError("retryable must be boolean")
        with self._lock:
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                row = self._fetch(job_id)
                self._require_active_lease(row, worker_id=worker_id, current=current)
                attempts = int(row["attempt_count"])
                should_retry = retryable and attempts < int(row["max_attempts"])
                status = "QUEUED" if should_retry else "FAILED"
                error = "RETRYABLE_FAILURE" if should_retry else ("RETRY_LIMIT_EXCEEDED" if retryable else "TERMINAL_FAILURE")
                self._connection.execute("UPDATE worker_jobs SET status=?, updated_at=?, lease_owner=NULL, lease_expires_at=NULL, last_error=? WHERE job_id=?", (status, self._iso(current), error, job_id))
                self._audit(actor_role="worker", action="RETRY" if should_retry else "FAIL", job_id=job_id, result=status, now=current)
                result = self._row_to_job(self._fetch(job_id))
                self._connection.execute("COMMIT")
                return result
            except Exception as exc:
                logger.warning("Failed to mark worker job %s failure: %s", job_id, exc, exc_info=True)
                self._connection.execute("ROLLBACK")
                raise

    def recover_expired_leases(self, *, actor_role: str, reconciliation_ref: str, now: datetime | None = None) -> list[str]:
        current = self._now(now, self._clock)
        if actor_role not in RECOVERY_ROLES:
            raise DurableWorkerStoreError("actor is not an approved recovery role")
        self._opaque(reconciliation_ref, "reconciliation_ref")
        with self._lock:
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                rows = self._connection.execute("SELECT job_id FROM worker_jobs WHERE status='RUNNING' AND lease_expires_at IS NOT NULL AND lease_expires_at <= ? ORDER BY job_id", (self._iso(current),)).fetchall()
                job_ids = [row["job_id"] for row in rows]
                for job_id in job_ids:
                    self._connection.execute("UPDATE worker_jobs SET status='BLOCKED', updated_at=?, lease_owner=NULL, lease_expires_at=NULL, last_error='LEASE_EXPIRED_REQUIRES_RECONCILIATION' WHERE job_id=?", (self._iso(current), job_id))
                    self._audit(actor_role=actor_role, action="LEASE_RECOVERY_BLOCK", job_id=job_id, result="BLOCKED", now=current, details={"reconciliation_ref": reconciliation_ref})
                self._connection.execute("COMMIT")
                return job_ids
            except Exception as exc:
                logger.warning("Failed to recover expired leases: %s", exc, exc_info=True)
                self._connection.execute("ROLLBACK")
                raise

    def reconcile(self, *, job_id: str, decision: str, actor_role: str, reconciliation_ref: str, now: datetime | None = None) -> dict[str, Any]:
        current = self._now(now, self._clock)
        if actor_role not in RECOVERY_ROLES:
            raise DurableWorkerStoreError("actor is not an approved recovery role")
        self._opaque(reconciliation_ref, "reconciliation_ref")
        if decision not in {"REQUEUE", "FAIL"}:
            raise DurableWorkerStoreError("decision is not allowlisted")
        with self._lock:
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                row = self._fetch(job_id)
                if row["status"] != "BLOCKED" or row["last_error"] != "LEASE_EXPIRED_REQUIRES_RECONCILIATION":
                    raise DurableWorkerStateError("job is not awaiting lease reconciliation")
                if actor_role == row["approver_role"]:
                    raise DurableWorkerStoreError("recovery actor conflicts with original approver")
                if decision == "REQUEUE" and int(row["attempt_count"]) >= int(row["max_attempts"]):
                    raise DurableWorkerStateError("retry limit exhausted")
                status = "QUEUED" if decision == "REQUEUE" else "FAILED"
                error = None if status == "QUEUED" else "LEASE_RECOVERY_FAILED_CLOSED"
                self._connection.execute("UPDATE worker_jobs SET status=?, updated_at=?, last_error=? WHERE job_id=?", (status, self._iso(current), error, job_id))
                self._audit(actor_role=actor_role, action="RECONCILE", job_id=job_id, result=status, now=current, details={"decision": decision, "reconciliation_ref": reconciliation_ref})
                result = self._row_to_job(self._fetch(job_id))
                self._connection.execute("COMMIT")
                return result
            except Exception as exc:
                logger.warning("Failed to reconcile worker job %s: %s", job_id, exc, exc_info=True)
                self._connection.execute("ROLLBACK")
                raise

    def get(self, job_id: str) -> dict[str, Any]:
        with self._lock:
            return deepcopy(self._row_to_job(self._fetch(job_id)))

    def verify_audit_chain(self) -> bool:
        with self._lock:
            previous: str | None = None
            rows = self._connection.execute("SELECT * FROM worker_audit ORDER BY event_seq").fetchall()
            for expected_seq, row in enumerate(rows, start=1):
                try:
                    details = json.loads(row["details_json"])
                except (TypeError, json.JSONDecodeError):
                    return False
                payload = {
                    "event_seq": expected_seq,
                    "timestamp": row["timestamp"],
                    "actor_role": row["actor_role"],
                    "action": row["action"],
                    "job_id": row["job_id"],
                    "result": row["result"],
                    "details": details,
                    "previous_event_hash": previous,
                }
                encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
                if row["event_seq"] != expected_seq or row["previous_event_hash"] != previous or row["event_hash"] != hashlib.sha256(encoded).hexdigest():
                    return False
                previous = row["event_hash"]
            return True

    def audit_snapshot(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._connection.execute("SELECT * FROM worker_audit ORDER BY event_seq").fetchall()
            return [
                {
                    "event_seq": row["event_seq"],
                    "timestamp": row["timestamp"],
                    "actor_role": row["actor_role"],
                    "action": row["action"],
                    "job_id": row["job_id"],
                    "result": row["result"],
                    "details": json.loads(row["details_json"]),
                    "previous_event_hash": row["previous_event_hash"],
                    "event_hash": row["event_hash"],
                }
                for row in rows
            ]

    def health(self) -> dict[str, Any]:
        with self._lock:
            journal = str(self._connection.execute("PRAGMA journal_mode").fetchone()[0]).lower()
            synchronous = int(self._connection.execute("PRAGMA synchronous").fetchone()[0])
            integrity = str(self._connection.execute("PRAGMA integrity_check").fetchone()[0]).lower()
            return {
                "schema_version": self.SCHEMA_VERSION,
                "mode": "software_fixture",
                "journal_mode": journal,
                "synchronous": synchronous,
                "integrity_check": integrity,
                "audit_chain_valid": self.verify_audit_chain(),
            }

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def __enter__(self) -> "DurableWorkerStore":
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.close()
