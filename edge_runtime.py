from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime
import json
import os
from pathlib import Path
import re
from threading import RLock
from typing import Any


@dataclass(frozen=True)
class AppendResult:
    accepted: bool
    reason: str | None
    buffered_samples: int
    dropped_samples: int
    last_sequence: int | None
    buffer_fill_ratio: float = 0.0
    memory_pressure: bool = False


class EdgeTelemetryStore:
    """Thread-safe, bounded, PII-free telemetry buffers for an offline Edge Hub.

    The store contains device telemetry only. Patient tokens and clinical identity
    mappings must remain outside this runtime component. Checkpoints are written
    atomically so a process restart can recover the most recent safe snapshot.
    """

    STATE_VERSION = 1
    DEFAULT_MAX_DEVICES = 256
    DEFAULT_MAX_SAMPLE_BYTES = 16_384
    DEFAULT_MEMORY_ALARM_RATIO = 0.90
    MAX_DEVICE_ID_LENGTH = 128
    DEVICE_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")
    FORBIDDEN_PII_KEYS = {"name", "patient_id", "patient_name", "patient_token", "hn", "hospital_number"}

    def __init__(
        self,
        max_samples: int,
        state_path: str | os.PathLike[str] | None = None,
        checkpoint_every: int = 128,
        max_devices: int = DEFAULT_MAX_DEVICES,
        max_sample_bytes: int = DEFAULT_MAX_SAMPLE_BYTES,
        memory_alarm_ratio: float = DEFAULT_MEMORY_ALARM_RATIO,
    ) -> None:
        if isinstance(max_samples, bool) or max_samples <= 0:
            raise ValueError("max_samples must be positive")
        if isinstance(checkpoint_every, bool) or checkpoint_every <= 0:
            raise ValueError("checkpoint_every must be positive")
        if isinstance(max_devices, bool) or max_devices <= 0:
            raise ValueError("max_devices must be positive")
        if isinstance(max_sample_bytes, bool) or max_sample_bytes <= 0:
            raise ValueError("max_sample_bytes must be positive")
        if isinstance(memory_alarm_ratio, bool) or not 0.5 <= memory_alarm_ratio <= 1.0:
            raise ValueError("memory_alarm_ratio must be between 0.5 and 1.0")
        self.max_samples = max_samples
        self.checkpoint_every = checkpoint_every
        self.max_devices = max_devices
        self.max_sample_bytes = max_sample_bytes
        self.memory_alarm_ratio = memory_alarm_ratio
        self.state_path = Path(state_path) if state_path else None
        self._buffers: dict[str, deque[dict[str, Any]]] = {}
        self._last_sequence: dict[str, int] = {}
        self._dropped_samples: dict[str, int] = {}
        self._lock = RLock()
        self._append_count = 0
        self.restore()

    @classmethod
    def _valid_device_id(cls, device_id: Any) -> bool:
        return isinstance(device_id, str) and cls.DEVICE_ID_PATTERN.fullmatch(device_id) is not None

    def _buffer(self, device_id: str) -> deque[dict[str, Any]]:
        return self._buffers.setdefault(device_id, deque(maxlen=self.max_samples))

    def _result(self, device_id: str, *, accepted: bool, reason: str | None, sequence: int | None = None) -> AppendResult:
        buffer = self._buffers.get(device_id)
        buffered_samples = len(buffer) if buffer is not None else 0
        ratio = buffered_samples / self.max_samples
        return AppendResult(
            accepted=accepted,
            reason=reason,
            buffered_samples=buffered_samples,
            dropped_samples=self._dropped_samples.get(device_id, 0),
            last_sequence=self._last_sequence.get(device_id) if sequence is None else sequence,
            buffer_fill_ratio=ratio,
            memory_pressure=ratio >= self.memory_alarm_ratio,
        )

    @staticmethod
    def _serialize(value: Any) -> Any:
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, dict):
            return {key: EdgeTelemetryStore._serialize(item) for key, item in value.items()}
        if isinstance(value, list):
            return [EdgeTelemetryStore._serialize(item) for item in value]
        return value

    def _sample_size(self, sample: dict[str, Any]) -> int | None:
        try:
            encoded = json.dumps(self._serialize(sample), separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        except (TypeError, ValueError, OverflowError):
            return None
        return len(encoded)

    def _restored_samples_are_safe(self, samples: list[Any]) -> bool:
        """Reject a device checkpoint when its persisted sample invariants fail.

        A checkpoint is untrusted input: it may be stale, partially written, or
        modified outside the process. Restoring no samples is safer than
        rehydrating PII-bearing or sequence-inconsistent state.
        """
        previous_sequence: int | None = None
        for sample in samples:
            if not isinstance(sample, dict):
                return False
            if self.FORBIDDEN_PII_KEYS.intersection(sample.keys()):
                return False
            if self._sample_size(sample) is None or self._sample_size(sample) > self.max_sample_bytes:
                return False
            sequence = sample.get("sequence")
            if sequence is not None:
                if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 0:
                    return False
                if previous_sequence is not None and sequence <= previous_sequence:
                    return False
                previous_sequence = sequence
        return True

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
            if not self._valid_device_id(device_id):
                return self._result(device_id if isinstance(device_id, str) else "", accepted=False, reason="invalid_device_id")
            if not isinstance(sample, dict):
                return self._result(device_id, accepted=False, reason="invalid_sample")
            if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 0:
                return self._result(device_id, accepted=False, reason="invalid_sequence")
            forbidden_keys = self.FORBIDDEN_PII_KEYS.intersection(sample.keys())
            if forbidden_keys:
                return self._result(device_id, accepted=False, reason="pii_field_not_allowed")
            sample_size = self._sample_size(sample)
            if sample_size is None:
                return self._result(device_id, accepted=False, reason="sample_not_serializable")
            if sample_size > self.max_sample_bytes:
                return self._result(device_id, accepted=False, reason="sample_too_large")
            if device_id not in self._buffers and len(self._buffers) >= self.max_devices:
                return self._result(device_id, accepted=False, reason="device_capacity_reached")
            last_sequence = self._last_sequence.get(device_id)
            if last_sequence is not None and sequence <= last_sequence:
                return self._result(device_id, accepted=False, reason="duplicate_or_out_of_order_sequence")

            buffer = self._buffer(device_id)
            was_full = len(buffer) == buffer.maxlen
            buffer.append(dict(sample))
            if was_full:
                self._dropped_samples[device_id] = self._dropped_samples.get(device_id, 0) + 1
            self._last_sequence[device_id] = sequence
            self._append_count += 1
            if self.state_path and self._append_count % self.checkpoint_every == 0:
                self._persist_locked()
            return self._result(device_id, accepted=True, reason=None, sequence=sequence)

    def ensure(self, device_id: str) -> None:
        with self._lock:
            if not self._valid_device_id(device_id):
                raise ValueError("invalid_device_id")
            if device_id not in self._buffers and len(self._buffers) >= self.max_devices:
                raise ValueError("device_capacity_reached")
            self._buffer(device_id)

    def snapshot(self, device_id: str) -> list[dict[str, Any]]:
        with self._lock:
            if not self._valid_device_id(device_id):
                return []
            buffer = self._buffers.get(device_id)
            return [dict(item) for item in buffer] if buffer is not None else []

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
            buffered_samples = sum(len(buffer) for buffer in self._buffers.values())
            per_device_ratio = max((len(buffer) / self.max_samples for buffer in self._buffers.values()), default=0.0)
            return {
                "device_count": len(self._buffers),
                "max_devices": self.max_devices,
                "device_capacity_used_ratio": len(self._buffers) / self.max_devices,
                "buffered_samples": buffered_samples,
                "dropped_samples": sum(self._dropped_samples.values()),
                "max_samples_per_device": self.max_samples,
                "max_sample_bytes": self.max_sample_bytes,
                "max_buffer_fill_ratio": per_device_ratio,
                "memory_pressure": per_device_ratio >= self.memory_alarm_ratio,
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
        with temp_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, separators=(",", ":"), ensure_ascii=False)
            handle.flush()
            os.fsync(handle.fileno())
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
                if not self._valid_device_id(device_id) or not isinstance(state, dict):
                    continue
                if device_id not in self._buffers and len(self._buffers) >= self.max_devices:
                    break
                samples = state.get("samples", [])
                if not isinstance(samples, list):
                    continue
                window = samples[-self.max_samples :]
                if not self._restored_samples_are_safe(window):
                    continue
                last_sequence = state.get("last_sequence")
                if last_sequence is not None and (isinstance(last_sequence, bool) or not isinstance(last_sequence, int) or last_sequence < 0):
                    continue
                sample_sequences = [sample.get("sequence") for sample in window if isinstance(sample, dict) and sample.get("sequence") is not None]
                if sample_sequences and last_sequence is not None and last_sequence != sample_sequences[-1]:
                    continue
                dropped_samples = state.get("dropped_samples", 0)
                if isinstance(dropped_samples, bool) or not isinstance(dropped_samples, int) or dropped_samples < 0:
                    continue
                buffer = self._buffer(device_id)
                for sample in window:
                    buffer.append(self._deserialize_sample(sample))
                if last_sequence is not None:
                    self._last_sequence[device_id] = last_sequence
                if dropped_samples:
                    self._dropped_samples[device_id] = dropped_samples
