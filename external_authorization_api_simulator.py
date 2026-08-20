from __future__ import annotations

import copy
import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import RLock
from typing import Any, Callable


UTC = timezone.utc
SHA256_RE = re.compile(r"[0-9a-f]{64}")
RAW_IDENTITY_RE = re.compile(r"(?i)(?<![A-Z0-9])(?:HN|AN|MRN|NATIONAL[_ -]?ID)(?:[:#\s-]+)[A-Z0-9][A-Z0-9_-]{2,}(?![A-Z0-9])")
FORBIDDEN_CLAIM_RE = re.compile(r"(?i)(clinical[-_ ]?ready|production[-_ ]?ready|tamper[-_ ]?proof|authorized[_ -]?by[_ -]?external[_ -]?owner|clinical[_ -]?validated)")
CONTRACT_VERSION = "external-auth-sim-v2"
SNAPSHOT_VERSION = "external-auth-sim-snapshot-v1"
SUBMITTER_ROLES = {"evidence_custodian", "local_submitter"}
REVIEWER_ROLES = {"independent_reviewer"}
SEVERITIES = {"CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"}
RETRYABLE_FAULT_CLASSES = {"TRANSIENT_TIMEOUT", "CONNECTION_RESET", "COMMIT_UNKNOWN"}
MAX_RETRY_ATTEMPTS = 3
MAX_RETRY_AFTER_SECONDS = 30
MAX_CHUNKS = 128
MAX_CHUNK_PAYLOAD_BYTES = 64 * 1024
AUDIT_PAYLOAD_KEYS = {
    "submit": {"submission_id", "request_hash"},
    "reconcile": {"submission_id", "request_hash"},
    "poll": {"submission_id", "status", "revision"},
    "review_start": {"submission_id"},
    "clarification_resolved": {"submission_id"},
    "decision_pending": {"submission_id", "decision_id", "expires_at"},
    "decision_expired": {"submission_id", "decision_id"},
    "decision_revoked": {"submission_id", "decision_id", "reason_hash"},
    "finding_issued": {"submission_id", "finding_id", "severity"},
    "reopen": {"submission_id", "reason_hash"},
    "delivery_retry_advised": {"idempotency_key_hash", "attempt", "fault_class", "action"},
    "chunk_manifest_validated": {"artifact_count", "chunk_count", "manifest_hash"},
}
STATUSES = {
    "RECEIVED_FOR_SIMULATION",
    "IN_SIMULATED_REVIEW",
    "REQUIRES_CLARIFICATION",
    "DECISION_PENDING_EXTERNAL_VERIFICATION",
    "SUBMISSION_RECONCILIATION_REQUIRED",
    "DECISION_EXPIRED",
    "DECISION_REVOKED",
    "RESUBMISSION_REQUIRED",
    "BLOCKED_SIMULATION",
    "REOPENED_WITH_REASON",
}
TRANSITIONS = {
    "RECEIVED_FOR_SIMULATION": {"IN_SIMULATED_REVIEW", "SUBMISSION_RECONCILIATION_REQUIRED", "BLOCKED_SIMULATION"},
    "IN_SIMULATED_REVIEW": {"REQUIRES_CLARIFICATION", "DECISION_PENDING_EXTERNAL_VERIFICATION", "BLOCKED_SIMULATION"},
    "REQUIRES_CLARIFICATION": {"IN_SIMULATED_REVIEW", "BLOCKED_SIMULATION"},
    "DECISION_PENDING_EXTERNAL_VERIFICATION": {"REQUIRES_CLARIFICATION", "DECISION_EXPIRED", "DECISION_REVOKED", "BLOCKED_SIMULATION"},
    "SUBMISSION_RECONCILIATION_REQUIRED": {"RECEIVED_FOR_SIMULATION", "BLOCKED_SIMULATION"},
    "DECISION_EXPIRED": {"RESUBMISSION_REQUIRED", "BLOCKED_SIMULATION"},
    "DECISION_REVOKED": {"RESUBMISSION_REQUIRED", "BLOCKED_SIMULATION"},
    "RESUBMISSION_REQUIRED": {"RECEIVED_FOR_SIMULATION"},
    "BLOCKED_SIMULATION": {"REOPENED_WITH_REASON"},
    "REOPENED_WITH_REASON": {"RECEIVED_FOR_SIMULATION", "IN_SIMULATED_REVIEW", "BLOCKED_SIMULATION"},
}


class SimulationApiError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


class AppendOnlyAuditStore:
    """Private append-only event store used by the offline simulator."""

    def __init__(self, events: list[dict[str, Any]] | None = None):
        self._events = copy.deepcopy(events or [])

    def __len__(self) -> int:
        return len(self._events)

    def __getitem__(self, index: int) -> dict[str, Any]:
        return self._events[index]

    def __iter__(self):
        return iter(self._events)

    def latest_hash(self) -> str | None:
        return self._events[-1]["event_hash"] if self._events else None

    def next_sequence(self) -> int:
        return len(self._events) + 1

    def append(self, event: dict[str, Any]) -> None:
        if event.get("previous_event_hash") != self.latest_hash():
            raise SimulationApiError("AUDIT_INTEGRITY_FAILURE", "append-only audit predecessor mismatch")
        self._events.append(copy.deepcopy(event))

    def snapshot(self) -> list[dict[str, Any]]:
        return copy.deepcopy(self._events)

    def tamper_for_test(self, index: int, field: str, value: Any) -> None:
        if index < 0 or index >= len(self._events):
            raise SimulationApiError("REJECTED_INVALID_TAMPER_TARGET", "audit event index is invalid")
        self._events[index][field] = value


@dataclass
class Submission:
    submission_id: str
    request_hash: str
    idempotency_key: str
    package_id: str
    manifest_version: int
    manifest_sha256: str
    scope_id: str
    window_id: str
    artifact_refs: tuple[str, ...] = field(default_factory=tuple)
    status: str = "RECEIVED_FOR_SIMULATION"
    revision: int = 0
    findings: list[dict[str, Any]] = field(default_factory=list)
    decision: dict[str, Any] | None = None
    last_event_hash: str | None = None
    last_server_observed_at: str | None = None


class SimulatedExternalAuthorizationApi:
    """Offline-only API simulator; it never grants external authorization."""

    MAX_ARTIFACT_REFS = 128
    MAX_REF_LENGTH = 512
    MAX_FIELD_LENGTH = 1024
    MAX_EVENT_PAYLOAD_BYTES = 16_384

    def __init__(
        self,
        package: dict[str, Any],
        *,
        clock: Callable[[], datetime] | None = None,
        allowed_clock_skew: timedelta | None = None,
    ):
        freeze = package["freeze"]
        self.package_id = package.get("package_id") or package["validation"]["package_id"]
        self.manifest_version = int(freeze["manifest_version"])
        self.manifest_sha256 = str(freeze["manifest_sha256"])
        self.scope_id = str(freeze["scope_id"])
        self.window_id = str(freeze["window_id"])
        self._validate_package_binding(package)
        self._submissions: dict[str, Submission] = {}
        self._idempotency: dict[str, tuple[str, str]] = {}
        self._audit_store = AppendOnlyAuditStore()
        self._finding_ids: set[str] = set()
        self._lock = RLock()
        self._integrity_failed = False
        self._incident: dict[str, Any] | None = None
        self._clock = clock or (lambda: datetime.now(UTC))
        self._allowed_clock_skew = allowed_clock_skew
        self._cache_version = 0
        self._recovery_epoch = 0

    @property
    def submissions(self) -> dict[str, dict[str, Any]]:
        """Return defensive snapshots; callers cannot mutate internal state."""
        with self._lock:
            return {key: self._submission_snapshot(value) for key, value in self._submissions.items()}

    @property
    def audit_events(self) -> tuple[dict[str, Any], ...]:
        """Return immutable-by-convention defensive copies of audit events."""
        with self._lock:
            return tuple(self._audit_store.snapshot())

    @property
    def service_status(self) -> dict[str, Any]:
        with self._lock:
            return copy.deepcopy({
                "state": "AUDIT_INTEGRITY_FAILURE" if self._incident else "OPERATIONAL",
                "incident": self._incident,
                "cache_version": self._cache_version,
                "recovery_epoch": self._recovery_epoch,
                "simulation": True,
                "external_authority": "NONE",
                "clinical_validation_authorized": False,
                "production_authorized": False,
                "runtime_authority": "NONE",
                "pilot_gate_status": "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION",
                "contract_version": CONTRACT_VERSION,
            })

    @staticmethod
    def _aware(value: str) -> datetime:
        if not isinstance(value, str):
            raise SimulationApiError("REJECTED_TIMEZONE_REQUIRED", "timestamp must be an ISO string")
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise SimulationApiError("REJECTED_TIMESTAMP_INVALID", "timestamp is invalid") from exc
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise SimulationApiError("REJECTED_TIMEZONE_REQUIRED", "timestamp must be timezone-aware")
        return parsed

    def _server_now(self) -> datetime:
        now = self._clock()
        if now.tzinfo is None or now.utcoffset() is None:
            raise SimulationApiError("CLOCK_UNTRUSTED", "simulator clock must be timezone-aware")
        return now

    def _validate_client_time(self, value: str) -> datetime:
        parsed = self._aware(value)
        if self._allowed_clock_skew is not None:
            delta = abs(self._server_now() - parsed)
            if delta > self._allowed_clock_skew:
                raise SimulationApiError("CLOCK_SKEW_EXCEEDED", "client timestamp exceeds allowed clock skew")
        return parsed

    @staticmethod
    def _canonical(value: Any) -> bytes:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode()

    @classmethod
    def _hash(cls, value: Any) -> str:
        return hashlib.sha256(cls._canonical(value)).hexdigest()

    @staticmethod
    def _scan_text(value: Any, field_name: str) -> None:
        if isinstance(value, str):
            if len(value) > SimulatedExternalAuthorizationApi.MAX_FIELD_LENGTH:
                raise SimulationApiError("REJECTED_FIELD_TOO_LARGE", f"{field_name} exceeds maximum length")
            if RAW_IDENTITY_RE.search(value):
                raise SimulationApiError("REJECTED_RAW_IDENTITY", f"{field_name} contains raw identity")
            if FORBIDDEN_CLAIM_RE.search(value):
                raise SimulationApiError("REJECTED_FORBIDDEN_CLAIM", f"{field_name} contains forbidden claim")
        elif isinstance(value, dict):
            for key, item in value.items():
                SimulatedExternalAuthorizationApi._scan_text(key, f"{field_name}.key")
                SimulatedExternalAuthorizationApi._scan_text(item, f"{field_name}.{key}")
        elif isinstance(value, (tuple, list)):
            for item in value:
                SimulatedExternalAuthorizationApi._scan_text(item, field_name)

    @staticmethod
    def _require_dict(value: Any, field_name: str) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise SimulationApiError("REJECTED_INVALID_PAYLOAD", f"{field_name} must be an object")
        return value

    @staticmethod
    def _validate_package_binding(package: dict[str, Any]) -> None:
        if not isinstance(package, dict):
            raise SimulationApiError("REJECTED_INVALID_GOVERNANCE_PACKAGE", "governance package must be an object")
        required = {"governance_state", "freeze", "validation", "external_authority", "clinical_validation_authorized", "production_authorized", "runtime_authority", "pilot_gate_status"}
        if not required.issubset(package) or not (package.get("package_id") or package.get("validation", {}).get("package_id")):
            raise SimulationApiError("REJECTED_INCOMPLETE_GOVERNANCE_PACKAGE", "governance package is incomplete")
        if package["governance_state"] != "GOVERNANCE_PACKAGE_READY_FOR_EXTERNAL_REVIEW":
            raise SimulationApiError("REJECTED_GOVERNANCE_STATE", "governance package is not frozen for external review")
        if package["external_authority"] != "NONE" or package["clinical_validation_authorized"] is not False or package["production_authorized"] is not False or package["runtime_authority"] != "NONE":
            raise SimulationApiError("REJECTED_AUTHORIZATION_ESCALATION", "governance package authorization boundary is not locked")
        if package["pilot_gate_status"] != "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION":
            raise SimulationApiError("REJECTED_PILOT_GATE_STATE", "governance package is outside the blocked external-review boundary")
        validation = package["validation"]
        if not isinstance(validation, dict) or validation.get("state") != package["governance_state"] or validation.get("checks", {}).get("local_ready_for_external_review") is not True or validation.get("checks", {}).get("external_verification_pending") is not True:
            raise SimulationApiError("REJECTED_GOVERNANCE_VALIDATION", "governance validation is not ready or is already externally verified")
        freeze = package["freeze"]
        if not isinstance(freeze, dict) or freeze.get("external_authority") != "NONE" or freeze.get("external_verification_required") is not True:
            raise SimulationApiError("REJECTED_FREEZE_BINDING", "freeze record is not bound to external verification")

    def _activate_incident(self, reason_code: str, details: list[str] | None = None) -> None:
        details = details or []
        incident_id = f"sim-incident-{self._hash({'reason_code': reason_code, 'details': details})[:16]}"
        self._incident = {
            "incident_id": incident_id,
            "reason_code": reason_code,
            "details": tuple(details[:8]),
            "recovery_required": True,
            "simulation": True,
            "external_authority": "NONE",
        }
        self._integrity_failed = True

    def _assert_integrity(self) -> None:
        if self._incident or self._integrity_failed:
            raise SimulationApiError("AUDIT_INTEGRITY_FAILURE", "audit integrity failure is active; state-changing commands are blocked")
        result = self._audit_locked()
        if not result["chain_valid"]:
            self._activate_incident("AUDIT_CHAIN_INVALID", result["errors"])
            raise SimulationApiError("AUDIT_INTEGRITY_FAILURE", "audit chain verification failed")

    def _build_event(self, action: str, actor_ref: str, payload: dict[str, Any], occurred_at: str) -> dict[str, Any]:
        self._validate_client_time(occurred_at)
        self._scan_text(actor_ref, "actor_ref")
        event_payload = copy.deepcopy(payload)
        allowed_payload_keys = AUDIT_PAYLOAD_KEYS.get(action)
        if allowed_payload_keys is None or not set(event_payload).issubset(allowed_payload_keys):
            raise SimulationApiError("REJECTED_AUDIT_PAYLOAD_SCHEMA", "audit payload contains a non-allowlisted field")
        if len(self._canonical(event_payload)) > self.MAX_EVENT_PAYLOAD_BYTES:
            raise SimulationApiError("REJECTED_EVENT_TOO_LARGE", "audit payload exceeds maximum size")
        previous = self._audit_store.latest_hash()
        event = {
            "audit_event_id": f"sim-audit-{self._audit_store.next_sequence():04d}",
            "sequence": self._audit_store.next_sequence(),
            "occurred_at": occurred_at,
            "server_observed_at": self._server_now().isoformat(),
            "actor_ref": actor_ref,
            "action": action,
            "payload": event_payload,
            "previous_event_hash": previous,
            "simulation": True,
            "external_authority": "NONE",
        }
        event["event_hash"] = self._hash(event)
        return event

    def _commit(self, submission: Submission | None, candidate: Submission | None, event: dict[str, Any]) -> None:
        # The caller must build and validate both candidate state and event before this point.
        if submission is not None and candidate is None:
            raise SimulationApiError("REJECTED_INTERNAL_TRANSACTION", "candidate state is required")
        if event["previous_event_hash"] != self._audit_store.latest_hash():
            self._activate_incident("AUDIT_PREDECESSOR_CHANGED")
            raise SimulationApiError("AUDIT_INTEGRITY_FAILURE", "audit chain changed before commit")
        if candidate is not None:
            candidate.revision = (submission.revision + 1) if submission is not None else candidate.revision
            candidate.last_event_hash = event["event_hash"]
            candidate.last_server_observed_at = event["server_observed_at"]
            self._cache_version += 1
            if candidate.decision is not None:
                candidate.decision["decision_revision"] = candidate.revision
                candidate.decision["cache_version"] = self._cache_version
            self._submissions[candidate.submission_id] = candidate
        self._audit_store.append(event)

    @staticmethod
    def _submission_snapshot(submission: Submission) -> dict[str, Any]:
        return {
            "submission_id": submission.submission_id,
            "request_hash": submission.request_hash,
            "idempotency_key": submission.idempotency_key,
            "package_id": submission.package_id,
            "manifest_version": submission.manifest_version,
            "manifest_sha256": submission.manifest_sha256,
            "scope_id": submission.scope_id,
            "window_id": submission.window_id,
            "artifact_ref_count": len(submission.artifact_refs),
            "status": submission.status,
            "revision": submission.revision,
            "finding_count": len(submission.findings),
            "decision": copy.deepcopy(submission.decision),
            "last_event_hash": submission.last_event_hash,
            "last_server_observed_at": submission.last_server_observed_at,
        }

    def _response(self, submission: Submission, audit_event_id: str | None = None, *, reconciled: bool = False, stale: bool = False) -> dict[str, Any]:
        decision = copy.deepcopy(submission.decision)
        return {
            "contract_version": CONTRACT_VERSION,
            "submission_id": submission.submission_id,
            "status": submission.status,
            "finding_count": len(submission.findings),
            "revision": submission.revision,
            "source_event_hash": submission.last_event_hash,
            "server_observed_at": submission.last_server_observed_at,
            "decision": decision,
            "cache_version": self._cache_version,
            "incident_state": "AUDIT_INTEGRITY_FAILURE" if self._incident else "OPERATIONAL",
            "simulation": True,
            "reconciled": reconciled,
            "stale": stale,
            "external_authority": "NONE",
            "clinical_validation_authorized": False,
            "production_authorized": False,
            "runtime_authority": "NONE",
            "pilot_gate_status": "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION",
            "audit_event_id": audit_event_id,
        }

    def _validate_submit_request(self, request: Any) -> tuple[dict[str, Any], str, str]:
        request = self._require_dict(request, "request")
        required = {
            "submission_idempotency_key",
            "package_id",
            "manifest_version",
            "manifest_sha256",
            "scope_id",
            "window_id",
            "artifact_refs",
            "submitted_by_role",
            "claim_boundary",
            "external_verification_required",
            "submitted_at",
        }
        missing = sorted(required - set(request))
        if missing:
            raise SimulationApiError("REJECTED_MISSING_FIELD", f"missing fields: {','.join(missing)}")
        allowed = required | {"clinical_validation_authorized", "production_authorized", "contract_version", "request_correlation_id"}
        unknown = sorted(set(request) - allowed)
        if unknown:
            raise SimulationApiError("REJECTED_UNKNOWN_FIELD", f"unknown fields: {','.join(unknown)}")
        if request.get("contract_version", "external-auth-sim-v2") != "external-auth-sim-v2":
            raise SimulationApiError("REJECTED_UNSUPPORTED_CONTRACT", "unsupported contract version")
        for field_name in ("submission_idempotency_key", "package_id", "scope_id", "window_id", "submitted_by_role", "claim_boundary"):
            if not isinstance(request[field_name], str) or not request[field_name].strip():
                raise SimulationApiError("REJECTED_INVALID_PAYLOAD", f"{field_name} must be a non-empty string")
            self._scan_text(request[field_name], field_name)
        if request["submitted_by_role"] not in SUBMITTER_ROLES:
            raise SimulationApiError("REJECTED_ROLE_NOT_ALLOWED", "submitted_by_role is not allowed")
        if not isinstance(request["manifest_version"], int) or isinstance(request["manifest_version"], bool) or request["manifest_version"] < 1:
            raise SimulationApiError("REJECTED_INVALID_MANIFEST_VERSION", "manifest_version must be a positive integer")
        if not isinstance(request["manifest_sha256"], str) or not SHA256_RE.fullmatch(request["manifest_sha256"]):
            raise SimulationApiError("REJECTED_INVALID_MANIFEST_HASH", "manifest_sha256 must be lowercase SHA-256")
        refs = request["artifact_refs"]
        if not isinstance(refs, list) or not refs or len(refs) > self.MAX_ARTIFACT_REFS:
            raise SimulationApiError("REJECTED_INVALID_ARTIFACT_REFS", "artifact_refs must be a bounded non-empty list")
        for ref in refs:
            if not isinstance(ref, str) or not ref.strip() or len(ref) > self.MAX_REF_LENGTH:
                raise SimulationApiError("REJECTED_INVALID_ARTIFACT_REFS", "artifact_refs contain an invalid reference")
            self._scan_text(ref, "artifact_refs")
        if request["external_verification_required"] is not True:
            raise SimulationApiError("REJECTED_VERIFICATION_BYPASS", "external_verification_required must be true")
        if request.get("clinical_validation_authorized") is True or request.get("production_authorized") is True:
            raise SimulationApiError("REJECTED_AUTHORIZATION_ESCALATION", "local submitter cannot self-authorize")
        if "request_correlation_id" in request and (not isinstance(request["request_correlation_id"], str) or not request["request_correlation_id"].strip()):
            raise SimulationApiError("REJECTED_INVALID_PAYLOAD", "request_correlation_id must be a non-empty string")
        self._validate_client_time(request["submitted_at"])
        request_hash = self._hash(request)
        return request, request_hash, request["submission_idempotency_key"]

    def submit(self, request: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            self._assert_integrity()
            request, request_hash, key = self._validate_submit_request(request)
            if key in self._idempotency:
                existing_id, existing_hash = self._idempotency[key]
                if existing_hash != request_hash:
                    raise SimulationApiError("REJECTED_IDEMPOTENCY_CONFLICT", "idempotency key reused with different payload")
                return self._response(self._submissions[existing_id], reconciled=True)
            if request["package_id"] != self.package_id:
                raise SimulationApiError("REJECTED_PACKAGE_MISMATCH", "package_id does not match frozen package")
            if request["manifest_version"] != self.manifest_version or request["manifest_sha256"] != self.manifest_sha256:
                raise SimulationApiError("REJECTED_MANIFEST_MISMATCH", "manifest does not match frozen package")
            if request["scope_id"] != self.scope_id or request["window_id"] != self.window_id:
                raise SimulationApiError("REJECTED_SCOPE_WINDOW_MISMATCH", "scope/window does not match freeze")
            submission_id = f"sim-submission-{request_hash[:16]}"
            candidate = Submission(
                submission_id=submission_id,
                request_hash=request_hash,
                idempotency_key=key,
                package_id=self.package_id,
                manifest_version=self.manifest_version,
                manifest_sha256=self.manifest_sha256,
                scope_id=self.scope_id,
                window_id=self.window_id,
                artifact_refs=tuple(request["artifact_refs"]),
            )
            event = self._build_event("submit", request["submitted_by_role"], {"submission_id": submission_id, "request_hash": request_hash}, request["submitted_at"])
            self._commit(None, candidate, event)
            self._idempotency[key] = (submission_id, request_hash)
            return self._response(self._submissions[submission_id], event["audit_event_id"])

    def submit_with_delivery_fault(self, request: dict[str, Any], fault: str) -> dict[str, Any]:
        if fault != "AFTER_COMMIT_BEFORE_RESPONSE":
            raise SimulationApiError("REJECTED_UNKNOWN_FAULT", "unsupported delivery fault")
        response = self.submit(request)
        raise SimulationApiError("COMMIT_UNKNOWN", json.dumps({"submission_id": response["submission_id"], "request_hash": self._submissions[response["submission_id"]].request_hash}))

    def negotiate_contract_version(self, requested_version: str) -> dict[str, Any]:
        if not isinstance(requested_version, str) or not requested_version.strip():
            raise SimulationApiError("REJECTED_INVALID_CONTRACT_VERSION", "contract version is required")
        if requested_version != CONTRACT_VERSION:
            raise SimulationApiError("REJECTED_UNSUPPORTED_CONTRACT", "requested contract version is unsupported")
        return {
            "contract_version": CONTRACT_VERSION,
            "compatibility": "EXACT_MATCH",
            "simulation": True,
            "external_authority": "NONE",
            "clinical_validation_authorized": False,
            "production_authorized": False,
            "runtime_authority": "NONE",
            "pilot_gate_status": "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION",
        }

    def verify_external_response_contract(self, response: dict[str, Any]) -> dict[str, Any]:
        response = self._require_dict(response, "external_response")
        if response.get("contract_version") != CONTRACT_VERSION:
            raise SimulationApiError("REJECTED_UNSUPPORTED_CONTRACT", "external response contract version is unsupported")
        if response.get("simulation") is not True or response.get("external_authority") != "NONE" or response.get("clinical_validation_authorized") is not False or response.get("production_authorized") is not False or response.get("runtime_authority") != "NONE":
            raise SimulationApiError("REJECTED_RESPONSE_AUTHORITY", "simulator cannot accept an externally authorized response")
        return {
            "verification_status": "SIMULATION_ONLY",
            "trusted": False,
            "action": "BLOCK_UNTIL_EXTERNAL_SIGNATURE_AND_READBACK",
            "response_hash": self._hash(response),
            "simulation": True,
            "external_authority": "NONE",
            "clinical_validation_authorized": False,
            "production_authorized": False,
            "runtime_authority": "NONE",
            "pilot_gate_status": "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION",
        }

    def retry_advice(self, fault_class: str, attempt: int) -> dict[str, Any]:
        if fault_class not in RETRYABLE_FAULT_CLASSES:
            raise SimulationApiError("REJECTED_NON_RETRYABLE_FAULT", "fault class is not retryable")
        if not isinstance(attempt, int) or isinstance(attempt, bool) or attempt < 1:
            raise SimulationApiError("REJECTED_INVALID_RETRY_ATTEMPT", "attempt must be a positive integer")
        if attempt > MAX_RETRY_ATTEMPTS:
            raise SimulationApiError("RETRY_BUDGET_EXHAUSTED", "bounded retry budget is exhausted")
        action = "RECONCILE" if fault_class == "COMMIT_UNKNOWN" else ("RETRY" if attempt < MAX_RETRY_ATTEMPTS else "STOP")
        return {
            "fault_class": fault_class,
            "attempt": attempt,
            "max_attempts": MAX_RETRY_ATTEMPTS,
            "retry_after_seconds": min(2 ** (attempt - 1), MAX_RETRY_AFTER_SECONDS),
            "action": action,
            "simulation": True,
            "external_authority": "NONE",
            "clinical_validation_authorized": False,
            "production_authorized": False,
            "runtime_authority": "NONE",
            "pilot_gate_status": "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION",
            "contract_version": CONTRACT_VERSION,
        }

    def validate_chunk_manifest(self, manifest: dict[str, Any], occurred_at: str) -> dict[str, Any]:
        with self._lock:
            self._assert_integrity()
            self._validate_client_time(occurred_at)
            manifest = self._require_dict(manifest, "chunk_manifest")
            required = {"artifact_id", "artifact_sha256", "chunks", "manifest_sha256"}
            if set(manifest) != required:
                raise SimulationApiError("REJECTED_CHUNK_MANIFEST_SCHEMA", "chunk manifest fields are incomplete or unknown")
            self._scan_text(manifest, "chunk_manifest")
            if not isinstance(manifest["artifact_id"], str) or not manifest["artifact_id"].strip():
                raise SimulationApiError("REJECTED_CHUNK_MANIFEST_SCHEMA", "artifact_id must be a non-empty string")
            if not isinstance(manifest["artifact_sha256"], str) or not SHA256_RE.fullmatch(manifest["artifact_sha256"]):
                raise SimulationApiError("REJECTED_CHUNK_MANIFEST_SCHEMA", "artifact_sha256 must be lowercase SHA-256")
            chunks = manifest["chunks"]
            if not isinstance(chunks, list) or not chunks or len(chunks) > MAX_CHUNKS:
                raise SimulationApiError("REJECTED_CHUNK_MANIFEST_SCHEMA", "chunks must be a bounded non-empty list")
            normalized_chunks: list[dict[str, Any]] = []
            for expected_sequence, chunk in enumerate(chunks):
                if not isinstance(chunk, dict) or set(chunk) != {"sequence", "sha256", "size", "received"}:
                    raise SimulationApiError("REJECTED_CHUNK_MANIFEST_SCHEMA", "chunk fields are incomplete or unknown")
                if chunk["sequence"] != expected_sequence or not isinstance(chunk["sequence"], int) or isinstance(chunk["sequence"], bool):
                    raise SimulationApiError("REJECTED_CHUNK_SEQUENCE", "chunk sequence must be contiguous and zero-based")
                if not isinstance(chunk["sha256"], str) or not SHA256_RE.fullmatch(chunk["sha256"]):
                    raise SimulationApiError("REJECTED_CHUNK_HASH", "chunk sha256 must be lowercase SHA-256")
                if not isinstance(chunk["size"], int) or isinstance(chunk["size"], bool) or chunk["size"] < 0 or chunk["size"] > MAX_CHUNK_PAYLOAD_BYTES:
                    raise SimulationApiError("REJECTED_CHUNK_SIZE", "chunk size exceeds configured bound")
                if chunk["received"] is not True:
                    raise SimulationApiError("REJECTED_INCOMPLETE_ARTIFACT", "all chunks must be received before finalize")
                normalized_chunks.append({"sequence": chunk["sequence"], "sha256": chunk["sha256"], "size": chunk["size"], "received": True})
            canonical_manifest = {"artifact_id": manifest["artifact_id"], "artifact_sha256": manifest["artifact_sha256"], "chunks": normalized_chunks}
            computed_manifest_hash = self._hash(canonical_manifest)
            if manifest["manifest_sha256"] != computed_manifest_hash:
                raise SimulationApiError("REJECTED_CHUNK_MANIFEST_HASH", "chunk manifest hash does not match content")
            event = self._build_event("chunk_manifest_validated", "local_submitter", {"artifact_count": 1, "chunk_count": len(normalized_chunks), "manifest_hash": computed_manifest_hash}, occurred_at)
            self._commit(None, None, event)
            return {
                "artifact_id": manifest["artifact_id"],
                "chunk_count": len(normalized_chunks),
                "manifest_sha256": computed_manifest_hash,
                "complete": True,
                "audit_event_id": event["audit_event_id"],
                "simulation": True,
                "external_authority": "NONE",
                "clinical_validation_authorized": False,
                "production_authorized": False,
                "runtime_authority": "NONE",
                "pilot_gate_status": "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION",
                "contract_version": CONTRACT_VERSION,
            }

    def export_snapshot(self) -> dict[str, Any]:
        with self._lock:
            audit = self._audit_locked()
            body = {
                "snapshot_version": SNAPSHOT_VERSION,
                "package_id": self.package_id,
                "manifest_version": self.manifest_version,
                "manifest_sha256": self.manifest_sha256,
                "scope_id": self.scope_id,
                "window_id": self.window_id,
                "submissions": {key: asdict(value) for key, value in self._submissions.items()},
                "idempotency": copy.deepcopy(self._idempotency),
                "finding_ids": sorted(self._finding_ids),
                "audit_events": audit["events"],
                "cache_version": self._cache_version,
                "recovery_epoch": self._recovery_epoch,
                "incident": copy.deepcopy(self._incident),
                "integrity_valid": audit["chain_valid"],
                "simulation": True,
                "external_authority": "NONE",
            }
            return {**body, "snapshot_sha256": self._hash(body)}

    @classmethod
    def from_snapshot(cls, package: dict[str, Any], snapshot: dict[str, Any], *, clock: Callable[[], datetime] | None = None, allowed_clock_skew: timedelta | None = None) -> "SimulatedExternalAuthorizationApi":
        if not isinstance(snapshot, dict) or snapshot.get("snapshot_version") != SNAPSHOT_VERSION:
            raise SimulationApiError("REJECTED_SNAPSHOT_VERSION", "unsupported snapshot version")
        expected_hash = snapshot.get("snapshot_sha256")
        body = {key: value for key, value in snapshot.items() if key != "snapshot_sha256"}
        if not isinstance(expected_hash, str) or expected_hash != cls._hash(body):
            raise SimulationApiError("REJECTED_SNAPSHOT_HASH", "snapshot hash verification failed")
        api = cls(package, clock=clock, allowed_clock_skew=allowed_clock_skew)
        with api._lock:
            if body.get("package_id") != api.package_id or body.get("manifest_version") != api.manifest_version or body.get("manifest_sha256") != api.manifest_sha256 or body.get("scope_id") != api.scope_id or body.get("window_id") != api.window_id:
                raise SimulationApiError("REJECTED_SNAPSHOT_BINDING", "snapshot does not match frozen package")
            api._submissions = {}
            for submission_id, payload in body.get("submissions", {}).items():
                if not isinstance(payload, dict) or payload.get("submission_id") != submission_id or payload.get("status") not in STATUSES:
                    raise SimulationApiError("REJECTED_SNAPSHOT_STATE", "snapshot contains an invalid submission")
                api._submissions[submission_id] = Submission(**copy.deepcopy(payload))
            api._idempotency = {str(key): (str(value[0]), str(value[1])) for key, value in body.get("idempotency", {}).items()}
            if any(submission_id not in api._submissions for submission_id, _ in api._idempotency.values()):
                raise SimulationApiError("REJECTED_SNAPSHOT_STATE", "snapshot idempotency index references unknown submission")
            api._finding_ids = set(body.get("finding_ids", []))
            api._audit_store = AppendOnlyAuditStore(body.get("audit_events", []))
            api._cache_version = int(body.get("cache_version", 0))
            api._recovery_epoch = int(body.get("recovery_epoch", 0)) + 1
            api._incident = copy.deepcopy(body.get("incident"))
            api._integrity_failed = bool(api._incident)
            audit = api._audit_locked()
            if not audit["chain_valid"] or body.get("integrity_valid") is not True:
                api._activate_incident("SNAPSHOT_AUDIT_INVALID", audit["errors"])
                raise SimulationApiError("REJECTED_SNAPSHOT_INTEGRITY", "snapshot audit chain is not valid")
        return api

    def reconcile_submission(self, idempotency_key: str, request_hash: str, occurred_at: str) -> dict[str, Any]:
        with self._lock:
            self._assert_integrity()
            self._validate_client_time(occurred_at)
            if not isinstance(idempotency_key, str) or not idempotency_key.strip() or not isinstance(request_hash, str) or not SHA256_RE.fullmatch(request_hash):
                raise SimulationApiError("REJECTED_INVALID_RECONCILIATION", "invalid reconciliation key or hash")
            record = self._idempotency.get(idempotency_key)
            if record is None:
                raise SimulationApiError("SUBMISSION_RECONCILIATION_REQUIRED", "no committed submission found")
            submission_id, stored_hash = record
            if stored_hash != request_hash:
                raise SimulationApiError("REJECTED_IDEMPOTENCY_CONFLICT", "reconciliation hash conflicts with stored request")
            event = self._build_event("reconcile", "local_submitter", {"submission_id": submission_id, "request_hash": request_hash}, occurred_at)
            self._commit(self._submissions[submission_id], copy.deepcopy(self._submissions[submission_id]), event)
            return self._response(self._submissions[submission_id], event["audit_event_id"], reconciled=True)

    def poll(self, submission_id: str, occurred_at: str, *, known_revision: int | None = None, known_event_hash: str | None = None, known_cache_version: int | None = None) -> dict[str, Any]:
        with self._lock:
            self._assert_integrity()
            self._validate_client_time(occurred_at)
            submission = self._submissions.get(submission_id)
            if submission is None:
                raise SimulationApiError("REJECTED_UNKNOWN_SUBMISSION", "submission not found")
            self._apply_expiry_locked(submission, occurred_at)
            if known_revision is not None and (not isinstance(known_revision, int) or isinstance(known_revision, bool) or known_revision < 0):
                raise SimulationApiError("REJECTED_INVALID_REVISION", "known_revision must be a non-negative integer")
            if known_revision is not None and submission.revision < known_revision:
                raise SimulationApiError("STALE_RESPONSE_REJECTED", "source revision is older than caller revision")
            if known_event_hash is not None and submission.last_event_hash != known_event_hash and known_revision == submission.revision:
                raise SimulationApiError("STALE_RESPONSE_REJECTED", "event hash does not match caller revision")
            if known_cache_version is not None and (not isinstance(known_cache_version, int) or isinstance(known_cache_version, bool) or known_cache_version < 0):
                raise SimulationApiError("REJECTED_INVALID_CACHE_VERSION", "known_cache_version must be a non-negative integer")
            if known_cache_version is not None and self._cache_version < known_cache_version:
                raise SimulationApiError("STALE_RESPONSE_REJECTED", "source cache version is older than caller cache version")
            event = self._build_event("poll", "local_submitter", {"submission_id": submission_id, "status": submission.status, "revision": submission.revision}, occurred_at)
            self._commit(None, None, event)
            return self._response(self._submissions[submission_id], event["audit_event_id"])

    def start_review(self, submission_id: str, occurred_at: str) -> dict[str, Any]:
        with self._lock:
            self._assert_integrity()
            self._validate_client_time(occurred_at)
            submission = self._submissions.get(submission_id)
            if submission is None:
                raise SimulationApiError("REJECTED_UNKNOWN_SUBMISSION", "submission not found")
            self._transition_allowed(submission.status, "IN_SIMULATED_REVIEW")
            candidate = copy.deepcopy(submission)
            candidate.status = "IN_SIMULATED_REVIEW"
            event = self._build_event("review_start", "simulated_external_reviewer", {"submission_id": submission_id}, occurred_at)
            self._commit(submission, candidate, event)
            return self._response(self._submissions[submission_id], event["audit_event_id"])

    def resolve_clarification(self, submission_id: str, occurred_at: str) -> dict[str, Any]:
        with self._lock:
            self._assert_integrity()
            self._validate_client_time(occurred_at)
            submission = self._submissions.get(submission_id)
            if submission is None:
                raise SimulationApiError("REJECTED_UNKNOWN_SUBMISSION", "submission not found")
            self._transition_allowed(submission.status, "IN_SIMULATED_REVIEW")
            candidate = copy.deepcopy(submission)
            candidate.status = "IN_SIMULATED_REVIEW"
            event = self._build_event("clarification_resolved", "evidence_custodian", {"submission_id": submission_id}, occurred_at)
            self._commit(submission, candidate, event)
            return self._response(self._submissions[submission_id], event["audit_event_id"])

    def mark_decision_pending(self, submission_id: str, decision_id: str, expires_at: str, occurred_at: str) -> dict[str, Any]:
        with self._lock:
            self._assert_integrity()
            self._validate_client_time(occurred_at)
            expiry = self._aware(expires_at)
            if expiry <= self._server_now():
                raise SimulationApiError("REJECTED_EXPIRED_DECISION", "decision expiry must be in the future")
            if not isinstance(decision_id, str) or not decision_id.strip():
                raise SimulationApiError("REJECTED_INVALID_DECISION", "decision_id is required")
            self._scan_text(decision_id, "decision_id")
            submission = self._submissions.get(submission_id)
            if submission is None:
                raise SimulationApiError("REJECTED_UNKNOWN_SUBMISSION", "submission not found")
            self._transition_allowed(submission.status, "DECISION_PENDING_EXTERNAL_VERIFICATION")
            candidate = copy.deepcopy(submission)
            candidate.status = "DECISION_PENDING_EXTERNAL_VERIFICATION"
            candidate.decision = {
                "decision_id": decision_id,
                "expires_at": expires_at,
                "decision_status": "PENDING_EXTERNAL_VERIFICATION",
                "external_verification_status": "PENDING_EXTERNAL_VERIFICATION",
            }
            event = self._build_event("decision_pending", "simulated_external_reviewer", {"submission_id": submission_id, "decision_id": decision_id, "expires_at": expires_at}, occurred_at)
            self._commit(submission, candidate, event)
            return self._response(self._submissions[submission_id], event["audit_event_id"])

    def _apply_expiry_locked(self, submission: Submission, occurred_at: str) -> None:
        decision = submission.decision
        if not decision or submission.status != "DECISION_PENDING_EXTERNAL_VERIFICATION":
            return
        if self._server_now() < self._aware(decision["expires_at"]):
            return
        candidate = copy.deepcopy(submission)
        candidate.status = "DECISION_EXPIRED"
        candidate.decision = {**decision, "decision_status": "EXPIRED"}
        event = self._build_event("decision_expired", "simulated_external_reviewer", {"submission_id": submission.submission_id, "decision_id": decision["decision_id"]}, occurred_at)
        self._commit(submission, candidate, event)
        self._submissions[submission.submission_id] = candidate

    def revoke_decision(self, submission_id: str, decision_id: str, reason: str, occurred_at: str) -> dict[str, Any]:
        with self._lock:
            self._assert_integrity()
            self._validate_client_time(occurred_at)
            self._scan_text(reason, "revocation_reason")
            if not isinstance(reason, str) or not reason.strip():
                raise SimulationApiError("REJECTED_INVALID_REVOCATION", "revocation reason is required")
            submission = self._submissions.get(submission_id)
            if submission is None:
                raise SimulationApiError("REJECTED_UNKNOWN_SUBMISSION", "submission not found")
            if not submission.decision or submission.decision.get("decision_id") != decision_id:
                raise SimulationApiError("REJECTED_DECISION_MISMATCH", "decision does not match submission")
            self._transition_allowed(submission.status, "DECISION_REVOKED")
            candidate = copy.deepcopy(submission)
            candidate.status = "DECISION_REVOKED"
            candidate.decision = {**submission.decision, "decision_status": "REVOKED", "revocation_reason": reason, "revoked_at": occurred_at}
            event = self._build_event("decision_revoked", "simulated_external_reviewer", {"submission_id": submission_id, "decision_id": decision_id, "reason_hash": self._hash(reason)}, occurred_at)
            self._commit(submission, candidate, event)
            return self._response(self._submissions[submission_id], event["audit_event_id"])

    def issue_finding(self, submission_id: str, finding: dict[str, Any], occurred_at: str) -> dict[str, Any]:
        with self._lock:
            self._assert_integrity()
            self._validate_client_time(occurred_at)
            submission = self._submissions.get(submission_id)
            if submission is None:
                raise SimulationApiError("REJECTED_UNKNOWN_SUBMISSION", "submission not found")
            if submission.status not in {"IN_SIMULATED_REVIEW", "REQUIRES_CLARIFICATION"}:
                raise SimulationApiError("REJECTED_INVALID_STATE", "finding cannot be issued in current state")
            finding = self._require_dict(finding, "finding")
            required = ("finding_id", "severity", "category", "summary", "evidence_refs", "required_action", "reviewer_role", "reviewer_identity_ref", "external_verification_status")
            missing = [key for key in required if key not in finding]
            if missing:
                raise SimulationApiError("REJECTED_MISSING_FIELD", f"missing finding fields: {','.join(missing)}")
            self._scan_text(finding, "finding")
            string_fields = ("finding_id", "severity", "category", "summary", "required_action", "reviewer_role", "reviewer_identity_ref", "external_verification_status")
            if any(not isinstance(finding[field_name], str) or not finding[field_name].strip() for field_name in string_fields):
                raise SimulationApiError("REJECTED_INVALID_FINDING", "finding string fields must be non-empty strings")
            if finding["finding_id"] in self._finding_ids:
                raise SimulationApiError("DUPLICATE_FINDING", "finding_id already exists")
            if finding["severity"] not in SEVERITIES:
                raise SimulationApiError("REJECTED_INVALID_SEVERITY", "invalid finding severity")
            if finding["reviewer_role"] not in REVIEWER_ROLES:
                raise SimulationApiError("REJECTED_REVIEWER_ROLE", "reviewer role is not allowed")
            if not isinstance(finding["evidence_refs"], list) or not finding["evidence_refs"] or len(finding["evidence_refs"]) > self.MAX_ARTIFACT_REFS:
                raise SimulationApiError("REJECTED_INVALID_EVIDENCE_REFS", "evidence_refs must be a bounded non-empty list")
            for ref in finding["evidence_refs"]:
                if not isinstance(ref, str) or not ref.strip() or len(ref) > self.MAX_REF_LENGTH:
                    raise SimulationApiError("REJECTED_INVALID_EVIDENCE_REFS", "evidence_refs contain an invalid reference")
                if ref not in submission.artifact_refs:
                    raise SimulationApiError("REJECTED_UNTRACEABLE_EVIDENCE_REF", "finding evidence ref is not present in submitted artifact refs")
            if finding["external_verification_status"] != "PENDING_EXTERNAL_VERIFICATION":
                raise SimulationApiError("REJECTED_VERIFICATION_BYPASS", "simulated finding must remain externally unverified")
            candidate = copy.deepcopy(submission)
            finding_copy = copy.deepcopy(finding)
            finding_copy.update({
                "submission_id": submission_id,
                "manifest_sha256": submission.manifest_sha256,
                "scope_id": submission.scope_id,
                "window_id": submission.window_id,
                "simulation": True,
            })
            candidate.findings.append(finding_copy)
            candidate.status = "REQUIRES_CLARIFICATION"
            event = self._build_event("finding_issued", "simulated_external_reviewer", {"submission_id": submission_id, "finding_id": finding["finding_id"], "severity": finding["severity"]}, occurred_at)
            self._commit(submission, candidate, event)
            self._finding_ids.add(finding["finding_id"])
            return self._response(self._submissions[submission_id], event["audit_event_id"])

    def reopen(self, submission_id: str, reason: str, occurred_at: str) -> dict[str, Any]:
        with self._lock:
            self._assert_integrity()
            self._validate_client_time(occurred_at)
            self._scan_text(reason, "reopen_reason")
            if not isinstance(reason, str) or not reason.strip():
                raise SimulationApiError("REJECTED_INVALID_REOPEN", "reopen reason is required")
            submission = self._submissions.get(submission_id)
            if submission is None:
                raise SimulationApiError("REJECTED_UNKNOWN_SUBMISSION", "submission not found")
            self._transition_allowed(submission.status, "REOPENED_WITH_REASON")
            candidate = copy.deepcopy(submission)
            candidate.status = "REOPENED_WITH_REASON"
            event = self._build_event("reopen", "evidence_custodian", {"submission_id": submission_id, "reason_hash": self._hash(reason)}, occurred_at)
            self._commit(submission, candidate, event)
            return self._response(self._submissions[submission_id], event["audit_event_id"])

    @staticmethod
    def _transition_allowed(current: str, target: str) -> None:
        if target not in STATUSES or target not in TRANSITIONS.get(current, set()):
            raise SimulationApiError("REJECTED_INVALID_STATE", f"transition {current}->{target} is not allowed")

    def inject_audit_tamper_for_test(self, index: int = 0, field: str = "action", value: str = "tampered") -> None:
        with self._lock:
            self._audit_store.tamper_for_test(index, field, value)

    def _audit_locked(self) -> dict[str, Any]:
        previous = None
        errors: list[str] = []
        for position, event in enumerate(self._audit_store, start=1):
            if event.get("sequence") != position:
                errors.append(f"sequence mismatch: {event.get('audit_event_id')}")
            expected = self._hash({key: value for key, value in event.items() if key != "event_hash"})
            if event.get("previous_event_hash") != previous:
                errors.append(f"previous hash mismatch: {event.get('audit_event_id')}")
            if event.get("event_hash") != expected:
                errors.append(f"event hash mismatch: {event.get('audit_event_id')}")
            previous = event.get("event_hash")
        return {"chain_valid": not errors, "event_count": len(self._audit_store), "errors": errors, "events": self._audit_store.snapshot()}

    def audit(self) -> dict[str, Any]:
        with self._lock:
            result = self._audit_locked()
            if not result["chain_valid"] and self._incident is None:
                self._activate_incident("AUDIT_CHAIN_INVALID", result["errors"])
            return result


def load_wave0_package(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    root = Path(__file__).resolve().parent
    package_path = root / "evals/micro_rag/evidence/wave0-governance-handoff-20260820.json"
    package = load_wave0_package(package_path)
    package_id = package.get("package_id") or package["validation"]["package_id"]
    fixed_now = datetime(2026, 8, 20, 8, 0, tzinfo=UTC)
    api = SimulatedExternalAuthorizationApi(package, clock=lambda: fixed_now)
    request = {
        "submission_idempotency_key": "wave0-submit-20260820-v2",
        "package_id": package_id,
        "manifest_version": package["freeze"]["manifest_version"],
        "manifest_sha256": package["freeze"]["manifest_sha256"],
        "scope_id": package["freeze"]["scope_id"],
        "window_id": package["freeze"]["window_id"],
        "artifact_refs": ["repo://WAVE_0_GOVERNANCE_HANDOFF_REPORT.md", "repo://WAVE_0_GOVERNANCE_REVIEW_CHECKLIST.md"],
        "submitted_by_role": "evidence_custodian",
        "claim_boundary": "SOFTWARE_VERIFIED_AND_SIMULATION_ONLY; external authorization remains pending",
        "external_verification_required": True,
        "submitted_at": "2026-08-20T08:00:00+00:00",
        "contract_version": "external-auth-sim-v2",
        "request_correlation_id": "corr-wave0-20260820-v2",
    }
    received = api.submit(request)
    review = api.start_review(received["submission_id"], "2026-08-20T08:01:00+00:00")
    finding = api.issue_finding(
        received["submission_id"],
        {
            "finding_id": "sim-finding-gv01-002",
            "severity": "HIGH",
            "category": "MISSING_EXTERNAL_GOVERNANCE",
            "summary": "Clinical owner appointment and signed scope remain pending external verification.",
            "evidence_refs": ["repo://WAVE_0_GOVERNANCE_HANDOFF_REPORT.md"],
            "required_action": "Provide external appointment and signed scope with expiry and rollback.",
            "reviewer_role": "independent_reviewer",
            "reviewer_identity_ref": "external-reviewer-ref-002",
            "external_verification_status": "PENDING_EXTERNAL_VERIFICATION",
        },
        "2026-08-20T08:02:00+00:00",
    )
    resolved = api.resolve_clarification(received["submission_id"], "2026-08-20T08:03:00+00:00")
    pending = api.mark_decision_pending(received["submission_id"], "sim-decision-001", "2026-08-20T09:00:00+00:00", "2026-08-20T08:04:00+00:00")
    negative_cases: dict[str, str] = {}
    mutations = {
        "raw_identity": {**request, "submission_idempotency_key": "negative-raw-v2", "artifact_refs": ["repo://HN-1234.txt"]},
        "bad_manifest": {**request, "submission_idempotency_key": "negative-hash-v2", "manifest_sha256": "0" * 64},
        "authorization_escalation": {**request, "submission_idempotency_key": "negative-auth-v2", "clinical_validation_authorized": True},
        "timezone_missing": {**request, "submission_idempotency_key": "negative-time-v2", "submitted_at": "2026-08-20T08:00:00"},
        "verification_bypass": {**request, "submission_idempotency_key": "negative-verification-v2", "external_verification_required": False},
        "unknown_field": {**request, "submission_idempotency_key": "negative-field-v2", "unexpected": "nope"},
        "invalid_refs_type": {**request, "submission_idempotency_key": "negative-refs-v2", "artifact_refs": "repo://not-a-list"},
        "idempotency_conflict": {**request, "manifest_sha256": "f" * 64},
    }
    for name, mutation in mutations.items():
        try:
            api.submit(mutation)
        except SimulationApiError as exc:
            negative_cases[name] = exc.code
        else:
            negative_cases[name] = "UNEXPECTED_ACCEPT"
    chunk_body = {
        "artifact_id": "repo://WAVE_0_GOVERNANCE_HANDOFF_REPORT.md",
        "artifact_sha256": "a" * 64,
        "chunks": [{"sequence": 0, "sha256": "b" * 64, "size": 128, "received": True}],
    }
    chunk_manifest = {**chunk_body, "manifest_sha256": api._hash(chunk_body)}
    chunk_result = api.validate_chunk_manifest(chunk_manifest, "2026-08-20T08:05:30+00:00")
    response_authenticity = api.verify_external_response_contract({
        "contract_version": "external-auth-sim-v2",
        "simulation": True,
        "external_authority": "NONE",
        "clinical_validation_authorized": False,
        "production_authorized": False,
        "runtime_authority": "NONE",
        "status": "DECISION_PENDING_EXTERNAL_VERIFICATION",
    })
    snapshot = api.export_snapshot()
    report = {
        "report_type": "EXTERNAL_AUTHORIZATION_API_SIMULATION_V2",
        "hardening_version": "wave-a-d-v1",
        "simulation": True,
        "source_boundary": "offline in-memory simulator; no network or credential",
        "positive_lifecycle": {"received": received, "review": review, "finding": finding, "clarification_resolved": resolved, "decision_pending": pending, "final_poll": api.poll(received["submission_id"], "2026-08-20T08:05:00+00:00")},
        "negative_cases": negative_cases,
        "hardening_evidence": {
            "governance_binding": "LOCAL_WAVE0_VALIDATION_BOUND",
            "append_only_audit_store": "SOFTWARE_BASELINE",
            "audit_incident_fail_stop": "REGRESSION_TESTED",
            "concurrency_serialization": "REGRESSION_TESTED",
            "decision_cache_version": pending["cache_version"],
            "retry_advice": api.retry_advice("COMMIT_UNKNOWN", 1),
            "chunk_manifest": chunk_result,
            "response_authenticity": response_authenticity,
            "restart_snapshot": {
                "snapshot_version": snapshot["snapshot_version"],
                "snapshot_sha256": snapshot["snapshot_sha256"],
                "integrity_valid": snapshot["integrity_valid"],
                "recovery_epoch": snapshot["recovery_epoch"],
            },
        },
        "audit": api.audit(),
        "external_authority": "NONE",
        "clinical_validation_authorized": False,
        "production_authorized": False,
        "runtime_authority": "NONE",
        "pilot_gate_status": "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION",
    }
    output = root / "evals/micro_rag/evidence/external-authorization-api-simulation-20260820.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "final_status": report["positive_lifecycle"]["final_poll"]["status"], "negative_cases": negative_cases, "audit_chain_valid": report["audit"]["chain_valid"]}, ensure_ascii=False))
