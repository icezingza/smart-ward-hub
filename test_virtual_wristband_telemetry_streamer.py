from datetime import datetime, timezone

from virtual_wristband_telemetry_streamer import build_stream, run_dry_run, scenario_for_bed


def run() -> None:
    streams = build_stream(bed_count=30, sample_count=8, start_time=datetime(2026, 8, 31, tzinfo=timezone.utc))
    assert len(streams) == 30
    assert all(len(stream) == 8 for stream in streams)
    assert len({event.device_id for stream in streams for event in stream}) == 30
    assert scenario_for_bed(0, "mixed") == "normal"
    assert scenario_for_bed(1, "mixed") == "cardiac_distress"
    assert scenario_for_bed(2, "mixed") == "silent_fall"
    cardiac = streams[1]
    assert any(event.heart_rate > 130 for event in cardiac)
    assert any(event.heart_rate < 45 for event in cardiac)
    fall = streams[2]
    assert fall[1].scenario_phase == "impact"
    assert fall[1].accel_z > 2.5
    assert [event.scenario_phase for event in fall[2:]] == ["motionless_after_impact"] * 6
    assert "gyro_x" not in fall[1].hub_payload()
    report = run_dry_run(streams)
    assert report["network_mode"] == "dry_run"
    assert report["total_samples"] == 240
    assert report["error_count"] == 0
    assert report["latency_ms"]["p95"] is None
    print("[Virtual Wristband Streamer] 30-bed mixed scenarios: PASSED")
    print("VIRTUAL_WRISTBAND_STREAMER_TESTS_PASSED")


if __name__ == "__main__":
    run()
