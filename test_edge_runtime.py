from pathlib import Path
import tempfile

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

    print("\nEDGE RUNTIME TESTS PASSED")


if __name__ == "__main__":
    run()
