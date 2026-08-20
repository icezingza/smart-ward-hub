from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import copy
import hashlib
import json
import re
from threading import RLock
from typing import Any, Callable


class WorkerControlPlaneError(ValueError):
    """Base error for fail-closed worker-control validation."""


class WorkerValidationError(WorkerControlPlaneError):
    pass


class WorkerStateError(WorkerControlPlaneError):
    pass


class WorkerIdempotencyConflict(WorkerControlPlaneError):
    pass


class RetryableWorkerError(Exception):
    """Handler signal for a bounded retry without exposing error details."""


class TerminalWorkerError(Exception):
    """Handler signal for a non-retryable failure."""


@dataclass(frozen=True)
class JobRecord:
    job_id: str
    job_type: str
    handler: str
    args: dict[str, Any]
    idempotency_key: str
    requester_role: str
    approver_role: str
    approval_ref: str
    max_attempts: int
    status: str
    attempts: int
    created_at: str
    updated_at: str
    lease_owner: str | None
    lease_expires_at: str | None
    last_error: str | None
    result: dict[str, Any] | None
    fingerprint: str


class WorkerControlPlane:
    """Deterministic, in-process control plane for non-clinical worker jobs.

    This component intentionally does not start threads, schedulers, network
    clients, subprocesses, or external side effects. It controls authorization,
    idempotency, leases, retry bounds, stale-lease reconciliation, and an
    append-only hash-chained audit stream. A separate approved operator must
    reconcile an expired lease before a job can be requeued.
    """

    JOB_TYPES = {"BACKUP_REPORT", "EVIDENCE_REPORT"}
    HANDLERS = {"backup.report", "evidence.report"}
    HANDLER_BY_JOB_TYPE = {
        "BACKUP_REPORT": "backup.report",
        "EVIDENCE_REPORT": "evidence.report",
    }
    ALLOWED_ROLES = {"reliability_operator", "control_room_coordinator", "security_auditor"}
    RECOVERY_ROLES = {"reliability_operator", "control_room_coordinator"}
    TERMINAL_STATES = {"SUCCEEDED", "FAILED", "CANCELLED"}
    MAX_ATTEMPTS = 3
    MAX_LEASE_SECONDS = 300
    SAFE_ARGUMENT_KEYS = {"report_kind", "format", "scope_ref"}
    FORBIDDEN_MARKERS = re.compile(
        r"(?i)(patient[_ -]?id|patient[_ -]?token|patient[_ -]?name|hospital[_ -]?number|\bhn\b|\bmrn\b|national[_ -]?id|private[_ -]?key|secret|bearer|authorization|password|api[_ -]?key)"
    )
    OPAQUE_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{2,127}")

    def __init__(
        self,
        handlers: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] | None = None,
        *,
        lease_seconds: int = 60,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if isinstance(lease_seconds, bool) or not isinstance(lease_seconds, int):
            raise WorkerValidationError("lease_seconds must be an integer")
        if lease_seconds <= 0 or lease_seconds > self.MAX_LEASE_SECONDS:
            raise WorkerValidationError("lease_seconds out of bounded range")
        self.lease_seconds = lease_seconds
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._handlers = dict(handlers or {})
        if not set(self._handlers).issubset(self.HANDLERS):
            raise WorkerValidationError("handler is not allowlisted")
        self._jobs: dict[str, JobRecord] = {}
        self._idempotency: dict[str, str] = {}
        self._audit: list[dict[str, Any]] = []
        self._lock = RLock()

    @staticmethod
    def _now(value: datetime | None, clock: Callable[[], datetime]) -> datetime:
        current = value if value is not None else clock()
        if not isinstance(current, datetime) or current.tzinfo is None or current.utcoffset() is None:
            raise WorkerValidationError("timestamp must be timezone-aware")
        return current.astimezone(timezone.utc)

    @staticmethod
    def _iso(value: datetime) -> str:
        return value.astimezone(timezone.utc).isoformat()

    @classmethod
    def _opaque(cls, value: Any, field: str) -> str:
        if not isinstance(value, str) or not cls.OPAQUE_RE.fullmatch(value):
            raise WorkerValidationError(f"{field} must be opaque")
        if cls.FORBIDDEN_MARKERS.search(value):
            raise WorkerValidationError(f"{field} contains forbidden marker")
        return value

    @classmethod
    def _safe_json(cls, value: Any, *, field: str, depth: int = 0) -> None:
        if depth > 5:
            raise WorkerValidationError(f"{field} exceeds bounded nesting")
        if value is None or isinstance(value, (str, int, float, bool)):
            if isinstance(value, str) and cls.FORBIDDEN_MARKERS.search(value):
                raise WorkerValidationError(f"{field} contains forbidden marker")
            return
        if isinstance(value, list):
            if len(value) > 32:
                raise WorkerValidationError(f"{field} exceeds bounded list size")
            for item in value:
                cls._safe_json(item, field=field, depth=depth + 1)
            return
        if isinstance(value, dict):
            if len(value) > 32:
                raise WorkerValidationError(f"{field} exceeds bounded object size")
            for key, item in value.items():
                if not isinstance(key, str) or cls.FORBIDDEN_MARKERS.search(key):
                    raise WorkerValidationError(f"{field} contains unsafe key")
                cls._safe_json(item, field=field, depth=depth + 1)
            return
        raise WorkerValidationError(f"{field} contains unsupported value type")

    @classmethod
    def _canonical_fingerprint(cls, payload: dict[str, Any]) -> str:
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
        return hashlib.sha256(encoded).hexdigest()

    def _audit_event(self, *, actor_role: str, action: str, job_id: str, result: str, now: datetime, details: dict[str, Any] | None = None) -> None:
        payload = {
            "event_seq": len(self._audit) + 1,
            "timestamp": self._iso(now),
            "actor_role": actor_role,
            "action": action,
            "job_id": job_id,
            "result": result,
            "details": details or {},
            "previous_event_hash": self._audit[-1]["event_hash"] if self._audit else None,
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
        payload["event_hash"] = hashlib.sha256(encoded).hexdigest()
        self._audit.append(payload)

    @staticmethod
    def _copy_job(job: JobRecord) -> dict[str, Any]:
        return {
            "job_id": job.job_id,
            "job_type": job.job_type,
            "handler": job.handler,
            "args": copy.deepcopy(job.args),
            "idempotency_key": job.idempotency_key,
            "requester_role": job.requester_role,
            "approver_role": job.approver_role,
            "approval_ref": job.approval_ref,
            "max_attempts": job.max_attempts,
            "status": job.status,
            "attempts": job.attempts,
            "created_at": job.created_at,
            "updated_at": job.updated_at,
            "lease_owner": job.lease_owner,
            "lease_expires_at": job.lease_expires_at,
            "last_error": job.last_error,
            "result": copy.deepcopy(job.result) if job.result is not None else None,
            "fingerprint": job.fingerprint,
        }

    def _replace(self, job: JobRecord, **changes: Any) -> JobRecord:
        updated = job.__dict__ | changes
        return JobRecord(**updated)

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
        if job_type not in self.JOB_TYPES:
            raise WorkerValidationError("job_type is not allowlisted")
        if not isinstance(args, dict):
            raise WorkerValidationError("args must be an object")
        if set(args) - self.SAFE_ARGUMENT_KEYS:
            raise WorkerValidationError("args contain unknown fields")
        self._safe_json(args, field="args")
        if self.HANDLER_BY_JOB_TYPE[job_type] not in self._handlers:
            raise WorkerValidationError("job handler is not registered")
        if requester_role not in self.ALLOWED_ROLES or approver_role not in self.ALLOWED_ROLES:
            raise WorkerValidationError("role is not allowlisted")
        if requester_role == approver_role:
            raise WorkerValidationError("requester and approver must be distinct")
        if isinstance(max_attempts, bool) or not isinstance(max_attempts, int) or not 1 <= max_attempts <= self.MAX_ATTEMPTS:
            raise WorkerValidationError("max_attempts exceeds bounded policy")
        if external_side_effects_allowed or clinical_state_mutation:
            raise WorkerValidationError("worker job crosses forbidden boundary")
        fingerprint_payload = {
            "job_id": job_id,
            "job_type": job_type,
            "handler": self.HANDLER_BY_JOB_TYPE[job_type],
            "args": args,
            "idempotency_key": idempotency_key,
            "requester_role": requester_role,
            "approver_role": approver_role,
            "approval_ref": approval_ref,
            "max_attempts": max_attempts,
        }
        fingerprint = self._canonical_fingerprint(fingerprint_payload)
        with self._lock:
            existing_id = self._idempotency.get(idempotency_key)
            if existing_id is not None:
                existing = self._jobs[existing_id]
                if existing.fingerprint != fingerprint:
                    raise WorkerIdempotencyConflict("idempotency key conflicts with existing job")
                return self._copy_job(existing)
            existing_job = self._jobs.get(job_id)
            if existing_job is not None:
                raise WorkerIdempotencyConflict("job_id conflicts with existing job")
            job = JobRecord(
                job_id=job_id,
                job_type=job_type,
                handler=self.HANDLER_BY_JOB_TYPE[job_type],
                args=copy.deepcopy(args),
                idempotency_key=idempotency_key,
                requester_role=requester_role,
                approver_role=approver_role,
                approval_ref=approval_ref,
                max_attempts=max_attempts,
                status="QUEUED",
                attempts=0,
                created_at=self._iso(current),
                updated_at=self._iso(current),
                lease_owner=None,
                lease_expires_at=None,
                last_error=None,
                result=None,
                fingerprint=fingerprint,
            )
            self._jobs[job_id] = job
            self._idempotency[idempotency_key] = job_id
            self._audit_event(actor_role=requester_role, action="SUBMIT", job_id=job_id, result="QUEUED", now=current)
            return self._copy_job(job)

    def claim(self, *, job_id: str, worker_id: str, now: datetime | None = None) -> str:
        current = self._now(now, self._clock)
        worker_id = self._opaque(worker_id, "worker_id")
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise WorkerStateError("unknown job")
            if job.status != "QUEUED":
                raise WorkerStateError("job is not claimable")
            lease_token = hashlib.sha256(f"{job_id}:{worker_id}:{len(self._audit) + 1}".encode()).hexdigest()[:24]
            expires = current + timedelta(seconds=self.lease_seconds)
            job = self._replace(
                job,
                status="RUNNING",
                attempts=job.attempts + 1,
                updated_at=self._iso(current),
                lease_owner=worker_id,
                lease_expires_at=self._iso(expires),
            )
            self._jobs[job_id] = job
            self._audit_event(actor_role="worker", action="CLAIM", job_id=job_id, result="RUNNING", now=current, details={"worker_id": worker_id})
            return lease_token

    def run_once(self, *, job_id: str, worker_id: str, now: datetime | None = None) -> dict[str, Any]:
        current = self._now(now, self._clock)
        self.claim(job_id=job_id, worker_id=worker_id, now=current)
        with self._lock:
            job = self._jobs[job_id]
            handler = self._handlers[job.handler]
            args = copy.deepcopy(job.args)
        try:
            result = handler(args)
            self._safe_json(result, field="handler result")
            if not isinstance(result, dict):
                raise WorkerValidationError("handler result must be an object")
        except RetryableWorkerError:
            with self._lock:
                job = self._jobs[job_id]
                if job.attempts < job.max_attempts:
                    job = self._replace(job, status="QUEUED", updated_at=self._iso(current), lease_owner=None, lease_expires_at=None, last_error="RETRYABLE_FAILURE")
                    self._jobs[job_id] = job
                    self._audit_event(actor_role="worker", action="RETRY_SCHEDULED", job_id=job_id, result="QUEUED", now=current)
                else:
                    job = self._replace(job, status="FAILED", updated_at=self._iso(current), lease_owner=None, lease_expires_at=None, last_error="RETRY_LIMIT_EXCEEDED")
                    self._jobs[job_id] = job
                    self._audit_event(actor_role="worker", action="FAIL", job_id=job_id, result="FAILED", now=current)
                return self._copy_job(job)
        except (TerminalWorkerError, WorkerValidationError):
            with self._lock:
                job = self._replace(self._jobs[job_id], status="FAILED", updated_at=self._iso(current), lease_owner=None, lease_expires_at=None, last_error="TERMINAL_FAILURE")
                self._jobs[job_id] = job
                self._audit_event(actor_role="worker", action="FAIL", job_id=job_id, result="FAILED", now=current)
                return self._copy_job(job)
        except Exception:
            with self._lock:
                job = self._replace(self._jobs[job_id], status="FAILED", updated_at=self._iso(current), lease_owner=None, lease_expires_at=None, last_error="UNEXPECTED_HANDLER_FAILURE")
                self._jobs[job_id] = job
                self._audit_event(actor_role="worker", action="FAIL", job_id=job_id, result="FAILED", now=current)
                return self._copy_job(job)
        with self._lock:
            job = self._replace(self._jobs[job_id], status="SUCCEEDED", updated_at=self._iso(current), lease_owner=None, lease_expires_at=None, result=copy.deepcopy(result))
            self._jobs[job_id] = job
            self._audit_event(actor_role="worker", action="COMPLETE", job_id=job_id, result="SUCCEEDED", now=current)
            return self._copy_job(job)

    def recover_stale_leases(self, *, actor_role: str, reconciliation_ref: str, now: datetime | None = None) -> list[str]:
        current = self._now(now, self._clock)
        if actor_role not in self.RECOVERY_ROLES:
            raise WorkerValidationError("actor is not an approved recovery role")
        self._opaque(reconciliation_ref, "reconciliation_ref")
        blocked: list[str] = []
        with self._lock:
            for job_id, job in list(self._jobs.items()):
                if job.status != "RUNNING" or not job.lease_expires_at:
                    continue
                expires = datetime.fromisoformat(job.lease_expires_at)
                if expires > current:
                    continue
                job = self._replace(job, status="BLOCKED", updated_at=self._iso(current), lease_owner=None, lease_expires_at=None, last_error="STALE_LEASE_REQUIRES_RECONCILIATION")
                self._jobs[job_id] = job
                self._audit_event(actor_role=actor_role, action="STALE_LEASE_BLOCK", job_id=job_id, result="BLOCKED", now=current, details={"reconciliation_ref": reconciliation_ref})
                blocked.append(job_id)
        return blocked

    def reconcile(self, *, job_id: str, decision: str, actor_role: str, reconciliation_ref: str, now: datetime | None = None) -> dict[str, Any]:
        current = self._now(now, self._clock)
        if actor_role not in self.RECOVERY_ROLES:
            raise WorkerValidationError("actor is not an approved recovery role")
        self._opaque(reconciliation_ref, "reconciliation_ref")
        if decision not in {"REQUEUE", "FAIL"}:
            raise WorkerValidationError("decision is not allowlisted")
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None or job.status != "BLOCKED" or job.last_error != "STALE_LEASE_REQUIRES_RECONCILIATION":
                raise WorkerStateError("job is not awaiting stale-lease reconciliation")
            if actor_role == job.approver_role:
                raise WorkerValidationError("recovery approver must be distinct from original approver")
            if decision == "REQUEUE" and job.attempts >= job.max_attempts:
                raise WorkerStateError("retry limit already exhausted")
            status = "QUEUED" if decision == "REQUEUE" else "FAILED"
            last_error = None if status == "QUEUED" else "STALE_LEASE_FAILED_CLOSED"
            job = self._replace(job, status=status, updated_at=self._iso(current), last_error=last_error)
            self._jobs[job_id] = job
            self._audit_event(actor_role=actor_role, action="RECONCILE", job_id=job_id, result=status, now=current, details={"decision": decision, "reconciliation_ref": reconciliation_ref})
            return self._copy_job(job)

    def get(self, job_id: str) -> dict[str, Any]:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise WorkerStateError("unknown job")
            return self._copy_job(job)

    def verify_audit_chain(self) -> bool:
        with self._lock:
            previous: str | None = None
            for index, event in enumerate(self._audit, start=1):
                if event.get("event_seq") != index or event.get("previous_event_hash") != previous:
                    return False
                payload = dict(event)
                expected = payload.pop("event_hash", None)
                encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
                if expected != hashlib.sha256(encoded).hexdigest():
                    return False
                previous = expected
            return True

    def audit_snapshot(self) -> list[dict[str, Any]]:
        with self._lock:
            return copy.deepcopy(self._audit)
