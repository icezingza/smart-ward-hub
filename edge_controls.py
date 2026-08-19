from __future__ import annotations

from collections import defaultdict, deque
from contextvars import ContextVar
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import threading
import time
from typing import Any, Protocol
import hashlib


_request_id: ContextVar[str] = ContextVar("request_id", default="unknown")
SENSITIVE_KEYS = {
    "name",
    "patient_id",
    "patient_name",
    "patient_token",
    "hn",
    "national_id",
    "address",
    "phone",
}


def set_request_id(value: str):
    return _request_id.set(value)


def reset_request_id(token) -> None:
    _request_id.reset(token)


def current_request_id() -> str:
    return _request_id.get()


def _sanitize_actor(actor: dict[str, Any] | None) -> dict[str, Any]:
    source = _redact(actor or {})
    subject = source.pop("subject", None)
    if subject and subject != "[REDACTED]":
        source["subject_hash"] = hashlib.sha256(str(subject).encode("utf-8")).hexdigest()[:16]
    elif subject == "[REDACTED]":
        source["subject"] = subject
    return source


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "[REDACTED]" if key.lower() in SENSITIVE_KEYS else _redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value


class SlidingWindowRateLimiter:
    def __init__(self, limit: int, window_seconds: int = 60) -> None:
        self.limit = max(1, limit)
        self.window_seconds = max(1, window_seconds)
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.RLock()

    def allow(self, key: str, now: float | None = None) -> tuple[bool, int]:
        current = time.monotonic() if now is None else now
        cutoff = current - self.window_seconds
        with self._lock:
            events = self._events[key]
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= self.limit:
                retry_after = max(1, int(events[0] + self.window_seconds - current + 0.999))
                return False, retry_after
            events.append(current)
            return True, 0

    def clear(self) -> None:
        with self._lock:
            self._events.clear()


class AuditSink:
    def __init__(self, path: Path, fsync: bool = True) -> None:
        self.path = path
        self.fsync = fsync
        self._lock = threading.RLock()

    def record(
        self,
        event_type: str,
        outcome: str,
        *,
        actor: dict[str, Any] | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        event = {
            "event_version": "1.0",
            "event_type": event_type,
            "outcome": outcome,
            "request_id": current_request_id(),
            "occurred_at": datetime.now(timezone.utc).isoformat(),
            "actor": _sanitize_actor(actor),
            "resource_type": resource_type,
            "resource_id": resource_id,
            "details": _redact(details or {}),
        }
        line = json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n"
        with self._lock:
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(line)
                handle.flush()
                if self.fsync:
                    import os
                    os.fsync(handle.fileno())
        return event


class AnchorStore(Protocol):
    def anchor(self, *, block_hash: str, chain_tip: str, package_id: int) -> bool:
        """Persist an immutable reference to a forensic chain tip."""


class FileAnchorStore:
    """Local append-only anchor adapter; an external WORM adapter can replace it.

    This class improves local integrity and operational diagnostics only. It does
    not create an independent trust boundary or external immutability guarantee.
    """

    HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")

    def __init__(self, path: Path | None, fsync: bool = True, source_root: Path | None = None) -> None:
        self.path = path.resolve() if path is not None else None
        self.fsync = fsync
        self.source_root = source_root.resolve() if source_root is not None else None
        self._lock = threading.RLock()
        if self.path is not None and self.source_root is not None:
            try:
                self.path.relative_to(self.source_root)
            except ValueError:
                pass
            else:
                raise ValueError("anchor_path_must_be_outside_source_tree")

    @classmethod
    def _validate_request(cls, *, block_hash: str, chain_tip: str, package_id: int) -> None:
        if not isinstance(package_id, int) or isinstance(package_id, bool) or package_id <= 0:
            raise ValueError("invalid_anchor_package_id")
        if not isinstance(block_hash, str) or not cls.HASH_PATTERN.fullmatch(block_hash):
            raise ValueError("invalid_anchor_block_hash")
        if not isinstance(chain_tip, str) or not cls.HASH_PATTERN.fullmatch(chain_tip):
            raise ValueError("invalid_anchor_chain_tip")

    @staticmethod
    def _idempotency_key(*, block_hash: str, chain_tip: str, package_id: int) -> str:
        material = f"{package_id}|{block_hash}|{chain_tip}".encode("utf-8")
        return hashlib.sha256(material).hexdigest()

    @staticmethod
    def _record_hash(record: dict[str, Any]) -> str:
        canonical = json.dumps(record, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()

    def _read_records_locked(self) -> list[dict[str, Any]]:
        if self.path is None or not self.path.exists():
            return []
        records: list[dict[str, Any]] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(record, dict):
                continue
            record_hash = record.get("record_hash")
            unsigned = dict(record)
            unsigned.pop("record_hash", None)
            if record_hash and record_hash == self._record_hash(unsigned):
                records.append(record)
            elif not record_hash and record.get("anchor_type") == "local_append_only_adapter":
                # Preserve readback compatibility for pre-hardening local records.
                records.append(record)
        return records

    def anchor_with_receipt(self, *, block_hash: str, chain_tip: str, package_id: int) -> dict[str, Any] | None:
        if self.path is None:
            return None
        self._validate_request(block_hash=block_hash, chain_tip=chain_tip, package_id=package_id)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        idempotency_key = self._idempotency_key(block_hash=block_hash, chain_tip=chain_tip, package_id=package_id)
        with self._lock:
            for existing in self._read_records_locked():
                if existing.get("idempotency_key") == idempotency_key:
                    return existing
            record = {
                "anchor_version": "1.1",
                "package_id": package_id,
                "block_hash": block_hash,
                "chain_tip": chain_tip,
                "idempotency_key": idempotency_key,
                "anchor_id": f"local-{idempotency_key[:16]}",
                "anchored_at": datetime.now(timezone.utc).isoformat(),
                "anchor_type": "local_append_only_adapter",
                "evidence_class": "LOCAL_TAMPER_EVIDENT_UNVERIFIED",
            }
            record["record_hash"] = self._record_hash(record)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
                handle.flush()
                if self.fsync:
                    import os
                    os.fsync(handle.fileno())
            return record

    def anchor(self, *, block_hash: str, chain_tip: str, package_id: int) -> bool:
        return self.anchor_with_receipt(block_hash=block_hash, chain_tip=chain_tip, package_id=package_id) is not None

    def verify_receipt(self, receipt: dict[str, Any]) -> bool:
        if not isinstance(receipt, dict) or receipt.get("anchor_type") != "local_append_only_adapter":
            return False
        with self._lock:
            return any(record == receipt for record in self._read_records_locked())

    def read_records(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._read_records_locked())
