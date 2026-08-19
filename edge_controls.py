from __future__ import annotations

from collections import defaultdict, deque
from contextvars import ContextVar
from datetime import datetime, timezone
import json
from pathlib import Path
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
    """Local append-only anchor adapter; an external WORM adapter can replace it."""

    def __init__(self, path: Path | None, fsync: bool = True) -> None:
        self.path = path
        self.fsync = fsync
        self._lock = threading.RLock()

    def anchor(self, *, block_hash: str, chain_tip: str, package_id: int) -> bool:
        if self.path is None:
            return False
        record = {
            "anchor_version": "1.0",
            "package_id": package_id,
            "block_hash": block_hash,
            "chain_tip": chain_tip,
            "anchored_at": datetime.now(timezone.utc).isoformat(),
            "anchor_type": "local_append_only_adapter",
        }
        with self._lock:
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
                handle.flush()
                if self.fsync:
                    import os
                    os.fsync(handle.fileno())
        return True
