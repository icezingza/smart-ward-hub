from __future__ import annotations

import argparse
import json
from pathlib import Path
import tempfile
from typing import Any

from edge_runtime import EdgeTelemetryStore


def sample(sequence: int) -> dict[str, Any]:
    return {
        "sequence": sequence,
        "ppg": 70.0 + sequence,
        "accel_x": 0.0,
        "accel_y": 0.0,
        "accel_z": 1.0,
        "battery_pct": 90.0,
    }


def _scenario_committed_restart(root: Path) -> dict[str, Any]:
    state_path = root / "committed.json"
    store = EdgeTelemetryStore(max_samples=3, state_path=state_path, checkpoint_every=1)
    assert store.append("device-recovery", sample(1), 1).accepted
    assert store.append("device-recovery", sample(2), 2).accepted
    store.persist()
    recovered = EdgeTelemetryStore(max_samples=3, state_path=state_path, checkpoint_every=1)
    assert recovered.last_sequence("device-recovery") == 2
    assert [item["sequence"] for item in recovered.snapshot("device-recovery")] == [1, 2]
    return {"scenario": "committed_restart", "status": "PASS"}


def _scenario_stale_temp_does_not_replace(root: Path) -> dict[str, Any]:
    state_path = root / "stale-temp.json"
    store = EdgeTelemetryStore(max_samples=3, state_path=state_path, checkpoint_every=1)
    assert store.append("device-recovery", sample(1), 1).accepted
    store.persist()
    temp_path = state_path.with_suffix(state_path.suffix + ".tmp")
    temp_path.write_text(
        json.dumps(
            {
                "state_version": EdgeTelemetryStore.STATE_VERSION,
                "buffers": {"device-recovery": {"samples": [sample(99)], "last_sequence": 99}},
            }
        ),
        encoding="utf-8",
    )
    recovered = EdgeTelemetryStore(max_samples=3, state_path=state_path, checkpoint_every=1)
    assert recovered.last_sequence("device-recovery") == 1
    assert [item["sequence"] for item in recovered.snapshot("device-recovery")] == [1]
    assert temp_path.exists()
    return {"scenario": "stale_temp_does_not_replace", "status": "PASS"}


def _scenario_corrupt_json_fails_closed(root: Path) -> dict[str, Any]:
    state_path = root / "corrupt.json"
    state_path.write_text('{"state_version":1,"buffers":', encoding="utf-8")
    recovered = EdgeTelemetryStore(max_samples=3, state_path=state_path, checkpoint_every=1)
    assert recovered.stats()["buffered_samples"] == 0
    assert recovered.last_sequence("device-recovery") is None
    return {"scenario": "corrupt_json_fails_closed", "status": "PASS"}


def _scenario_unsupported_and_malformed_payloads(root: Path) -> dict[str, Any]:
    cases = [
        ("unsupported_version", {"state_version": 999, "buffers": {"device-recovery": {"samples": [sample(9)]}}}),
        ("buffers_wrong_type", {"state_version": 1, "buffers": []}),
        ("samples_wrong_type", {"state_version": 1, "buffers": {"device-recovery": {"samples": "not-a-list"}}}),
        (
            "malformed_metadata",
            {
                "state_version": 1,
                "buffers": {
                    "device-recovery": {
                        "samples": ["not-a-sample", sample(3)],
                        "last_sequence": True,
                        "dropped_samples": -1,
                    }
                },
            },
        ),
    ]
    for name, payload in cases:
        state_path = root / f"{name}.json"
        state_path.write_text(json.dumps(payload), encoding="utf-8")
        recovered = EdgeTelemetryStore(max_samples=3, state_path=state_path, checkpoint_every=1)
        assert recovered.stats()["buffered_samples"] <= 1
        assert recovered.last_sequence("device-recovery") in {None, 3}
    return {"scenario": "unsupported_and_malformed_payloads", "status": "PASS", "cases": len(cases)}


def _scenario_pii_checkpoint_rejected(root: Path) -> dict[str, Any]:
    state_path = root / "pii-checkpoint.json"
    state_path.write_text(
        json.dumps(
            {
                "state_version": EdgeTelemetryStore.STATE_VERSION,
                "buffers": {
                    "device-recovery": {
                        "samples": [{**sample(1), "patient_token": "must-not-restore"}],
                        "last_sequence": 1,
                        "dropped_samples": 0,
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    recovered = EdgeTelemetryStore(max_samples=3, state_path=state_path, checkpoint_every=1)
    assert recovered.snapshot("device-recovery") == []
    assert recovered.last_sequence("device-recovery") is None
    assert recovered.stats()["buffered_samples"] == 0
    return {"scenario": "pii_checkpoint_rejected", "status": "PASS"}


def _scenario_sequence_inconsistency_rejected(root: Path) -> dict[str, Any]:
    state_path = root / "sequence-inconsistency.json"
    state_path.write_text(
        json.dumps(
            {
                "state_version": EdgeTelemetryStore.STATE_VERSION,
                "buffers": {
                    "device-recovery": {
                        "samples": [sample(2), sample(2)],
                        "last_sequence": 2,
                        "dropped_samples": 0,
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    recovered = EdgeTelemetryStore(max_samples=3, state_path=state_path, checkpoint_every=1)
    assert recovered.snapshot("device-recovery") == []
    assert recovered.last_sequence("device-recovery") is None
    return {"scenario": "sequence_inconsistency_rejected", "status": "PASS"}


def _scenario_last_sequence_mismatch_rejected(root: Path) -> dict[str, Any]:
    state_path = root / "last-sequence-mismatch.json"
    state_path.write_text(
        json.dumps(
            {
                "state_version": EdgeTelemetryStore.STATE_VERSION,
                "buffers": {
                    "device-recovery": {
                        "samples": [sample(2)],
                        "last_sequence": 9,
                        "dropped_samples": 0,
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    recovered = EdgeTelemetryStore(max_samples=3, state_path=state_path, checkpoint_every=1)
    assert recovered.snapshot("device-recovery") == []
    assert recovered.last_sequence("device-recovery") is None
    return {"scenario": "last_sequence_mismatch_rejected", "status": "PASS"}


def run_harness(output: Path | None = None) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="smart-ward-recovery-") as directory:
        root = Path(directory)
        results = [
            _scenario_committed_restart(root),
            _scenario_stale_temp_does_not_replace(root),
            _scenario_corrupt_json_fails_closed(root),
            _scenario_unsupported_and_malformed_payloads(root),
            _scenario_pii_checkpoint_rejected(root),
            _scenario_sequence_inconsistency_rejected(root),
            _scenario_last_sequence_mismatch_rejected(root),
        ]
    report = {
        "suite": "smart-ward-power-loss-storage-recovery-harness",
        "mode": "software_fault_injection",
        "results": results,
        "all_passed": all(item["status"] == "PASS" for item in results),
        "physical_power_cut": "UNVERIFIED",
        "disk_full_drill": "UNVERIFIED",
        "filesystem_corruption_drill": "SOFTWARE_CORRUPTION_ONLY",
        "checkpoint_invariant_hardening": "SOFTWARE_VERIFIED",
        "patient_data_used": False,
        "raw_frames_recorded": False,
    }
    if output:
        output.write_text(json.dumps(report, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Run safe software-only Edge recovery fault scenarios")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    report = run_harness(args.output)
    print(json.dumps(report, ensure_ascii=True, sort_keys=True))
    print("POWER_LOSS_STORAGE_RECOVERY_SOFTWARE_HARNESS_PASSED")
    return 0 if report["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
