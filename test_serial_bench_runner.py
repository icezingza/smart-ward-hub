from __future__ import annotations

from pathlib import Path
import tempfile

from serial_bench_runner import BenchConfig, PHYSICAL_CONFIRMATION, run


def run_tests() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        dry = run(
            BenchConfig(
                port=None,
                baudrate=115200,
                timeout_seconds=1.0,
                max_payload=4096,
                output=Path(temp_dir) / "dry.json",
                dry_run=True,
                confirm_physical=None,
            )
        )
        assert dry["status"] == "DRY_RUN_ONLY"
        assert dry["dry_run_codec"]["result"] == "PASS"
        assert dry["raw_frames_recorded"] is False
        assert dry["physical_hardware_validation"] == "PENDING"
    print("[Bench] Dry-run never opens a serial port and codec self-check passes: PASSED")

    with tempfile.TemporaryDirectory() as temp_dir:
        blocked = run(
            BenchConfig(
                port="COM999",
                baudrate=115200,
                timeout_seconds=1.0,
                max_payload=4096,
                output=Path(temp_dir) / "blocked.json",
                dry_run=False,
                confirm_physical=None,
            )
        )
        assert blocked["status"] == "BLOCKED_CONFIRMATION_REQUIRED"
        assert blocked["physical_hardware_validation"] == "PENDING"
    print("[Bench] Physical path blocks without explicit loopback confirmation: PASSED")

    assert PHYSICAL_CONFIRMATION == "I_HAVE_A_NONPRODUCTION_LOOPBACK"
    print("[Bench] Confirmation phrase is explicit and non-production scoped: PASSED")
    print("SERIAL_BENCH_RUNNER_TESTS_PASSED")


if __name__ == "__main__":
    run_tests()
