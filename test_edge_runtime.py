from pathlib import Path
import tempfile
from unittest.mock import patch

from edge_runtime import EdgeTelemetryStore


def sample(sequence: int) -> dict:
    return {
        "sequence": sequence,
        "ppg": 70.0,
        "accel_x": 0.0,
        "accel_y": 0.0,
        "accel_z": 1.0,
        "battery_pct": 90.0,
    }


def run() -> None:
    with tempfile.TemporaryDirectory() as directory:
        state_path = Path(directory) / "edge-state.json"
        store = EdgeTelemetryStore(max_samples=2, state_path=state_path, checkpoint_every=1)
        assert store.append("device-1", sample(1), 1).accepted
        assert store.append("device-1", sample(2), 2).accepted
        third = store.append("device-1", sample(3), 3)
        assert third.accepted is True
        assert third.dropped_samples == 1
        assert [item["sequence"] for item in store.snapshot("device-1")] == [2, 3]
        print("[Edge] Bounded overflow and dropped counter: PASSED")

        duplicate = store.append("device-1", sample(3), 3)
        assert duplicate.accepted is False
        assert duplicate.reason == "duplicate_or_out_of_order_sequence"
        print("[Edge] Duplicate/out-of-order rejection: PASSED")

        pii = store.append("device-1", {**sample(4), "patient_token": "should-never-enter-edge-buffer"}, 4)
        assert pii.accepted is False
        assert pii.reason == "pii_field_not_allowed"
        print("[Edge] PII field rejection: PASSED")

        store.persist()
        recovered = EdgeTelemetryStore(max_samples=2, state_path=state_path, checkpoint_every=1)
        assert [item["sequence"] for item in recovered.snapshot("device-1")] == [2, 3]
        assert recovered.last_sequence("device-1") == 3
        print("[Edge] Checkpoint restart recovery: PASSED")

        bounded = EdgeTelemetryStore(max_samples=2, max_devices=1, max_sample_bytes=256, memory_alarm_ratio=0.5)
        assert bounded.append("device-1", sample(1), 1).accepted
        pressure = bounded.append("device-1", sample(2), 2)
        assert pressure.accepted is True
        assert pressure.memory_pressure is True
        assert pressure.buffer_fill_ratio == 1.0
        assert bounded.stats()["memory_pressure"] is True
        assert bounded.append("device-2", sample(1), 1).reason == "device_capacity_reached"
        print("[Edge] Global device bound and memory-pressure signal: PASSED")

        before_devices = len(bounded)
        assert bounded.snapshot("unknown-device") == []
        assert bounded.snapshot(" ") == []
        assert len(bounded) == before_devices
        assert bounded.append(" ", sample(3), 3).reason == "invalid_device_id"
        assert bounded.append("device-1", {"sequence": 3, "payload": "x" * 300}, 3).reason == "sample_too_large"
        assert bounded.append("device-1", sample(3), True).reason == "invalid_sequence"
        print("[Edge] Invalid identifier, oversized sample and boolean sequence rejection: PASSED")

        disk_full = EdgeTelemetryStore(max_samples=2, state_path=Path("/tmp/edge-disk-full-state.json"), checkpoint_every=1)
        with patch.object(disk_full, "_persist_locked", side_effect=OSError(28, "simulated disk full")):
            failed = disk_full.append("device-disk", sample(1), 1)
        assert failed.accepted is False
        assert failed.reason == "checkpoint_persist_failed"
        assert disk_full.snapshot("device-disk") == []
        assert disk_full.last_sequence("device-disk") is None
        print("[Edge] Checkpoint persistence failure rolls back accepted state: PASSED")

    print("\nEDGE RUNTIME TESTS PASSED")


if __name__ == "__main__":
    run()
