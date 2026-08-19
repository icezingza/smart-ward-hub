from __future__ import annotations

from network_pressure_simulation import PressureScenario, simulate


def run() -> None:
    burst = simulate(
        PressureScenario(
            name="test-burst",
            ticks=12,
            device_count=4,
            burst_ticks=4,
            burst_multiplier=8,
            queue_capacity=8,
            consumer_per_tick=1,
        )
    )
    assert burst["status"] == "PASSED"
    assert burst["backpressure_observed"] is True
    assert burst["queue_dropped"] > 0
    assert burst["max_queue_depth"] <= burst["parameters"]["queue_capacity"]
    assert burst["memory_bound_respected"] is True
    print("[Pressure] Burst saturation exposes bounded queue drops: PASSED")

    sustained = simulate(
        PressureScenario(
            name="test-sustained",
            ticks=20,
            device_count=2,
            burst_ticks=0,
            burst_multiplier=1,
            queue_capacity=16,
            consumer_per_tick=4,
            partial_chunk_pattern=(1, 2, 3, 5),
        )
    )
    assert sustained["status"] == "PASSED"
    assert sustained["queue_dropped"] == 0
    assert sustained["accepted_packets"] == sustained["produced_frames"]
    assert sustained["memory_bound_respected"] is True
    print("[Pressure] Sustained partial-read traffic drains without loss: PASSED")

    faults = simulate(
        PressureScenario(
            name="test-faults",
            ticks=20,
            device_count=2,
            queue_capacity=16,
            consumer_per_tick=8,
            crc_corruption_every=5,
            duplicate_every=7,
            disconnect_every=4,
            malformed_every=6,
            pii_every=9,
        )
    )
    assert faults["status"] == "PASSED"
    assert faults["crc_mismatch"] > 0
    assert faults["pii_rejections"] > 0
    assert faults["duplicate_rejections"] > 0
    assert faults["disconnects"] > 0
    assert faults["replay_guard_respected"] is True
    assert faults["memory_bound_respected"] is True
    print("[Pressure] Corruption, PII, reconnect and replay controls remain bounded: PASSED")

    for report in (burst, sustained, faults):
        assert report["evidence_boundary"] == "software_simulation_only"
        assert report["physical_hardware_validation"] if "physical_hardware_validation" in report else True
    print("NETWORK_PRESSURE_SIMULATION_TESTS_PASSED")


if __name__ == "__main__":
    run()
