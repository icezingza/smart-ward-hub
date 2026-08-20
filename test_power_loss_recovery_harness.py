from __future__ import annotations

from power_loss_recovery_harness import run_harness


def run() -> None:
    report = run_harness()
    assert report["all_passed"] is True
    assert report["physical_power_cut"] == "UNVERIFIED"
    assert report["disk_full_drill"] == "UNVERIFIED"
    assert report["filesystem_corruption_drill"] == "SOFTWARE_CORRUPTION_ONLY"
    assert report["checkpoint_invariant_hardening"] == "SOFTWARE_VERIFIED"
    assert {item["scenario"] for item in report["results"]} >= {
        "pii_checkpoint_rejected",
        "sequence_inconsistency_rejected",
        "last_sequence_mismatch_rejected",
    }
    assert report["patient_data_used"] is False
    print("[P0-004] Software recovery fault-injection scenarios: PASSED")
    print("[P0-004] Physical power cut, disk-full and real filesystem corruption remain UNVERIFIED")
    print("POWER_LOSS_STORAGE_RECOVERY_HARNESS_TESTS_PASSED")


if __name__ == "__main__":
    run()
