from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime
import json
import os
from pathlib import Path
from threading import RLock
from typing import Any


@dataclass(frozen=True)
class AppendResult:
    accepted: bool
    reason: str | None
    buffered_samples: int
    dropped_samples: int
    last_sequence: int | None


class EdgeTelemetryStore:
    """Thread-safe, bounded, PII-free telemetry buffers for an offline Edge Hub.

    The store contains device telemetry only. Patient tokens and clinical identity
    mappings must remain outside this runtime component. Checkpoints are written
    atomically so a process restart can recover the most recent safe snapshot.
    """

    STATE_VERSION = 1
    FORBIDDEN_PII_KEYS = {"name", "patient_id", "patient_name", "patient_token", "hn", "hospital_number"}

    def __init__(
        self,
        max_samples: int,
        state_path: str | os.PathLike[str] | None = None,
        checkpoint_every: int = 128,
    ) -> None:
        if max_samples <= 0:
            raise ValueError("max_samples must be positive")
        if checkpoint_every <= 0:
            raise ValueError("checkpoint_every must be positive")
        self.max_samples = max_samples
        self.checkpoint_every = checkpoint_every
        self.state_path = Path(state_path) if state_path else None
        self._buffers: dict[str, deque[dict[str, Any]]] = {}
        self._last_sequence: dict[str, int] = {}
        self._dropped_samples: dict[str, int] = {}
        self._lock = RLock()
        self._append_count = 0
        self.restore()

    def _buffer(self, device_id: str) -> deque[dict[str, Any]]:
        return self._buffers.setdefault(device_id, deque(maxlen=self.max_samples))

    @staticmethod
    def _serialize(value: Any) -> Any:
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, dict):
            return {key: EdgeTelemetryStore._serialize(item) for key, item in value.items()}
        if isinstance(value, list):
            return [EdgeTelemetryStore._serialize(item) for item in value]
        return value

    @staticmethod
    def _deserialize_sample(sample: dict[str, Any]) -> dict[str, Any]:
        restored = dict(sample)
        for key in ("timestamp", "received_at"):
            value = restored.get(key)
            if isinstance(value, str):
                try:
                    parsed = datetime.fromisoformat(value)
                    restored[key] = parsed.replace(tzinfo=None) if parsed.tzinfo else parsed
                except ValueError:
                    pass
        return restored

    def append(self, device_id: str, sample: dict[str, Any], sequence: int) -> AppendResult:
        with self._lock:
            forbidden_keys = self.FORBIDDEN_PII_KEYS.intersection(sample.keys())
            if forbidden_keys:
                return AppendResult(
                    accepted=False,
                    reason="pii_field_not_allowed",
                    buffered_samples=len(self._buffer(device_id)),
                    dropped_samples=self._dropped_samples.get(device_id, 0),
                    last_sequence=self._last_sequence.get(device_id),
                )
            last_sequence = self._last_sequence.get(device_id)
            if last_sequence is not None and sequence <= last_sequence:
                return AppendResult(
                    accepted=False,
                    reason="duplicate_or_out_of_order_sequence",
                    buffered_samples=len(self._buffer(device_id)),
                    dropped_samples=self._dropped_samples.get(device_id, 0),
                    last_sequence=last_sequence,
                )

            buffer = self._buffer(device_id)
            was_full = len(buffer) == buffer.maxlen
            buffer.append(dict(sample))
            if was_full:
                self._dropped_samples[device_id] = self._dropped_samples.get(device_id, 0) + 1
            self._last_sequence[device_id] = sequence
            self._append_count += 1
            if self.state_path and self._append_count % self.checkpoint_every == 0:
                self._persist_locked()
            return AppendResult(
                accepted=True,
                reason=None,
                buffered_samples=len(buffer),
                dropped_samples=self._dropped_samples.get(device_id, 0),
                last_sequence=sequence,
            )

    def ensure(self, device_id: str) -> None:
        with self._lock:
            self._buffer(device_id)

    def snapshot(self, device_id: str) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(item) for item in self._buffer(device_id)]

    def clear_device(self, device_id: str, *, reset_sequence: bool = False) -> int:
        with self._lock:
            buffer = self._buffers.get(device_id)
            removed = len(buffer) if buffer is not None else 0
            if buffer is not None:
                buffer.clear()
            if reset_sequence:
                self._last_sequence.pop(device_id, None)
            self._persist_locked()
            return removed

    def pop(self, device_id: str) -> None:
        with self._lock:
            self._buffers.pop(device_id, None)
            self._last_sequence.pop(device_id, None)
            self._dropped_samples.pop(device_id, None)
            self._persist_locked()

    def clear(self) -> None:
        with self._lock:
            for buffer in self._buffers.values():
                buffer.clear()
            self._buffers.clear()
            self._last_sequence.clear()
            self._dropped_samples.clear()
            self._persist_locked()

    def last_sequence(self, device_id: str) -> int | None:
        with self._lock:
            return self._last_sequence.get(device_id)

    def stats(self) -> dict[str, Any]:
        with self._lock:
            return {
                "device_count": len(self._buffers),
                "buffered_samples": sum(len(buffer) for buffer in self._buffers.values()),
                "dropped_samples": sum(self._dropped_samples.values()),
                "max_samples_per_device": self.max_samples,
                "checkpoint_enabled": self.state_path is not None,
            }

    def __len__(self) -> int:
        return len(self._buffers)

    def _persist_locked(self) -> None:
        if self.state_path is None:
            return
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "state_version": self.STATE_VERSION,
            "buffers": {
                device_id: {
                    "samples": [self._serialize(sample) for sample in buffer],
                    "last_sequence": self._last_sequence.get(device_id),
                    "dropped_samples": self._dropped_samples.get(device_id, 0),
                }
                for device_id, buffer in self._buffers.items()
            },
        }
        temp_path = self.state_path.with_suffix(self.state_path.suffix + ".tmp")
        temp_path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
        os.replace(temp_path, self.state_path)

    def persist(self) -> None:
        with self._lock:
            self._persist_locked()

    def restore(self) -> None:
        if self.state_path is None or not self.state_path.exists():
            return
        with self._lock:
            try:
                payload = json.loads(self.state_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                return
            if not isinstance(payload, dict) or payload.get("state_version") != self.STATE_VERSION:
                return
            buffers = payload.get("buffers")
            if not isinstance(buffers, dict):
                return
            for device_id, state in buffers.items():
                if not isinstance(device_id, str) or not isinstance(state, dict):
                    continue
                buffer = self._buffer(device_id)
                samples = state.get("samples", [])
                if not isinstance(samples, list):
                    continue
                for sample in samples[-self.max_samples :]:
                    if isinstance(sample, dict):
                        buffer.append(self._deserialize_sample(sample))
                last_sequence = state.get("last_sequence")
                if isinstance(last_sequence, int) and not isinstance(last_sequence, bool):
                    self._last_sequence[device_id] = last_sequence
                dropped_samples = state.get("dropped_samples", 0)
                if isinstance(dropped_samples, int) and not isinstance(dropped_samples, bool) and dropped_samples >= 0:
                    self._dropped_samples[device_id] = dropped_samples
